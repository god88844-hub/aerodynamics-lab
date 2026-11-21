"""One reusable, isolated CAD engine. Imported only in the supervised child."""

from hashlib import sha256
import json
import os
from pathlib import Path
import time

from aeroforge_schemas.cad import BladeRecipe, BoxRecipe, CadTorqueRequest
from desktop_worker.io import read_control_bytes, unlink_control_record, write_result
from desktop_worker.protocol import MAX_REQUEST_BYTES, PROTOCOL, WorkerRequest
from desktop_worker.resources import ResourceBudget, admission, capacity_snapshot, workspace_size
from desktop_worker.supervision import IDENTIFIER, ProcessRef, read_record, source_identity
from geometry.cad_backend import build_blade_project, build_box_project, constrained_rectangle
from geometry.cad_dynamics import _identity, run_cad_torque


def environment_identity() -> dict:
    bootstrap = Path(__file__).resolve().parents[2] / "scripts/lab_worker.py"
    return {"model": _identity(), "bootstrap_sha256": sha256(bootstrap.read_bytes()).hexdigest()}


def serve(session: Path, session_id: str) -> int:
    session_admission = read_record(session / "resource-admission.json")
    budget = ResourceBudget.from_dict(session_admission["requested"])
    if source_identity(Path(__file__).resolve().parents[2]) != read_record(session / "supervisor.json")["source_sha256"]:
        raise ValueError("Source changed while starting the worker engine")
    baseline = environment_identity()
    import cadquery  # noqa: F401 - load native dependencies before advertising readiness
    constrained_rectangle(0.01, 0.01)
    if environment_identity() != baseline:
        raise ValueError("Model environment changed while warming the worker")
    process = ProcessRef(os.getpid())
    write_result(session / "ready.json", {"protocol": PROTOCOL, "session_id": session_id,
                 "worker_pid": os.getpid(), "process": process.record(), "environment": baseline})
    process.close()
    while True:
        pending = session / "pending.json"
        if not pending.is_file():
            time.sleep(0.01)
            continue
        claimed = session / "inflight.json"
        pending.replace(claimed)
        with claimed.open("rb") as source:
            raw = source.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError("Worker request exceeds 16 MiB")
        document = json.loads(raw)
        job_id = document.get("job_id")
        if not isinstance(job_id, str) or not IDENTIFIER.fullmatch(job_id):
            raise ValueError("Invalid job ID; retiring the session")
        directory = session / "jobs" / job_id
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "request.json").write_bytes(raw)
        context = {"protocol": PROTOCOL, "session_id": session_id, "job_id": job_id,
                   "request_sha256": sha256(raw).hexdigest(), "worker_pid": os.getpid()}
        write_result(directory / "started.json", context)
        write_result(session / "active.json", {"job_id": job_id})
        try:
            request = WorkerRequest.model_validate(document)
            if request.session_id != session_id:
                raise ValueError("Request belongs to a different worker session")
            if ResourceBudget.from_dict(request.resources) != budget:
                raise ValueError("Request limits must match the session; restart it to change limits")
            usage = read_record(session / "resource-usage.json")
            admitted = admission(budget, capacity_snapshot(session),
                        resident_bytes=usage["latest_resident_bytes"], workspace_bytes=workspace_size(session),
                        wall_limit_s=session_admission["effective"]["wall_time_s"])
            write_result(directory / "resource-admission.json", admitted)
            if admitted["status"] != "admitted":
                raise ValueError("resource_admission_refused: " + ", ".join(admitted["reasons"]))
            if environment_identity() != baseline:
                raise ValueError("Model environment changed; restart the worker before running another job")
            if request.operation == "build-body":
                result = build_box_project(BoxRecipe.model_validate(request.payload), directory / "result-cad")
            elif request.operation == "build-blade":
                result = build_blade_project(BladeRecipe.model_validate(request.payload), directory / "result-cad")
            else:
                root = Path(request.asset_root)
                if not root.is_absolute():
                    raise ValueError("CAD asset root must be absolute")
                result = run_cad_torque(CadTorqueRequest.model_validate(request.payload), root)
            if environment_identity() != baseline:
                raise ValueError("Model environment changed during the worker job")
            output = directory / "result.json"
            write_result(output, result)
            prepared = {**context, "output_sha256": sha256(output.read_bytes()).hexdigest()}
            write_result(directory / "prepared.json", prepared)
            # The supervisor remains responsive while native CAD is busy. It checks
            # current resources before allowing this prepared output to become success.
            while not (directory / "approved.json").is_file():
                time.sleep(0.01)
            approved_raw = read_control_bytes(directory / "approved.json")
            approved = json.loads(approved_raw)
            if any(approved.get(key) != prepared[key] for key in ("protocol", "session_id", "job_id", "request_sha256", "output_sha256")):
                raise ValueError("Resource approval does not match this frozen result")
            if sha256(output.read_bytes()).hexdigest() != prepared["output_sha256"]:
                raise ValueError("Prepared output changed before completion")
            write_result(directory / "complete.json", {**prepared, "resource_approval_sha256":
                         sha256(approved_raw).hexdigest()})
        except Exception as error:
            write_result(directory / "error.json", {**context, "status": "failed", "error": str(error)})
            return 2  # conservatively discard native state after any failed request
        finally:
            unlink_control_record(session / "active.json")
            unlink_control_record(claimed)
