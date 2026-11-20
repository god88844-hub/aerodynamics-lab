"""Run the real supervisor/engine processes and verify lifecycle and frozen jobs."""

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

pytest.importorskip("cadquery")

from aeroforge_schemas.cad import BoxRecipe, CadTorqueRequest, TorqueExperiment
from desktop_worker.client import WorkerClient
from desktop_worker.io import write_result
from desktop_worker.supervision import ProcessRef, read_record, stop_session, terminate_record
from geometry.cad_dynamics import run_cad_torque

ROOT = Path(__file__).resolve().parents[2]


def wait_until(predicate, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.025)
    pytest.fail("Worker lifecycle condition did not complete within its deadline")


def test_reuses_one_engine_and_matches_direct_frozen_dynamics(tmp_path):
    with WorkerClient(ROOT, tmp_path) as client:
        ready = client.wait_ready()
        first = client.request("build-body", BoxRecipe(material_density_kg_m3=500).model_dump(mode="json"))
        first_started = json.loads((client.last_job / "started.json").read_bytes())
        assert first_started["worker_pid"] == ready["worker_pid"]
        edited = client.request("build-body", BoxRecipe(width_m=0.3, material_density_kg_m3=500).model_dump(mode="json"))
        assert edited["geometry"]["volume_m3"] > first["geometry"]["volume_m3"]
        request = CadTorqueRequest(project=edited["project"], experiment=TorqueExperiment(duration_s=0.2))
        root = Path(edited["project_path"]).parent
        report = client.request("cad-torque", request.model_dump(mode="json"), asset_root=root)
        assert report == run_cad_torque(request, root)
        assert json.loads((client.last_job / "started.json").read_bytes())["worker_pid"] == ready["worker_pid"]
        receipt = json.loads((client.last_job / "complete.json").read_bytes())
        assert receipt["request_sha256"] == sha256((client.last_job / "request.json").read_bytes()).hexdigest()
        assert report["physical_validation_status"] == "unvalidated"
        with ProcessProbe(ready["worker_pid"]) as probe:
            assert probe.alive()
            client.close()
            wait_until(lambda: not probe.alive())


class ProcessProbe:
    def __init__(self, pid):
        self.reference = ProcessRef(pid)

    def alive(self):
        return self.reference.alive()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.reference.close()


def test_bad_request_retires_engine_without_poisoning_a_new_session(tmp_path):
    with WorkerClient(ROOT, tmp_path) as client:
        client.wait_ready()
        with pytest.raises(RuntimeError):
            client.request("build-body", {"width_m": -1})
        wait_until(lambda: client.process.poll() is not None)
        assert (client.last_job / "error.json").exists()
        assert not (client.last_job / "complete.json").exists()
    with WorkerClient(ROOT, tmp_path) as recovered:
        recovered.wait_ready()
        built = recovered.request("build-body", BoxRecipe().model_dump(mode="json"))
        report = recovered.request("cad-torque", CadTorqueRequest(project=built["project"]).model_dump(mode="json"),
                                   asset_root=Path(built["project_path"]).parent)
        assert report["result"]["status"] == "inconclusive"


def test_owner_exit_stops_engine_and_preserves_completed_assets(tmp_path):
    owner = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "import time; time.sleep(90)"],
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        with WorkerClient(ROOT, tmp_path, owner_pid=owner.pid) as client:
            ready = client.wait_ready()
            built = client.request("build-body", BoxRecipe().model_dump(mode="json"))
            with ProcessProbe(ready["worker_pid"]) as probe:
                owner.kill()
                owner.wait(timeout=5)
                wait_until(lambda: client.process.poll() is not None)
                wait_until(lambda: not probe.alive())
            assert json.loads((client.session / "retired.json").read_bytes())["reason"] == "owner_exited"
            for asset in built["project"]["assets"]:
                assert sha256((Path(built["project_path"]).parent / asset["path"]).read_bytes()).hexdigest() == asset["sha256"]
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.wait(timeout=5)


def test_deadline_stops_busy_native_engine_without_completion(tmp_path):
    with WorkerClient(ROOT, tmp_path, job_timeout=0.01) as client:
        ready = client.wait_ready()
        recipe = {"stations": [{"radius_m": 0.02 + i * 0.01, "chord_m": 0.03,
                                  "twist_deg": 20 - i / 2} for i in range(16)], "profile_samples": 128}
        with ProcessProbe(ready["worker_pid"]) as probe:
            with pytest.raises(RuntimeError):
                client.request("build-blade", recipe)
            wait_until(lambda: client.process.poll() is not None)
            assert json.loads((client.session / "retired.json").read_bytes())["reason"] == "job_timeout"
            assert not (client.last_job / "complete.json").exists()
            assert not probe.alive()


def test_source_change_between_requests_is_refused(tmp_path):
    environment = tmp_path / "environment"
    environment.mkdir()
    shutil.copytree(ROOT / "packages", environment / "packages", ignore=shutil.ignore_patterns("__pycache__", "build*"))
    shutil.copytree(ROOT / "apps/api/app", environment / "apps/api/app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "data/components", environment / "data/components")
    (environment / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/lab_worker.py", environment / "scripts/lab_worker.py")
    for relative in ("apps/api/requirements.lock", "apps/desktop/requirements-cad.lock"):
        target = environment / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    with WorkerClient(environment, tmp_path / "sessions") as client:
        client.wait_ready()
        changed = environment / "packages/physics/constants.py"
        changed.write_bytes(changed.read_bytes() + b"\n# changed after engine initialization\n")
        with pytest.raises(RuntimeError, match="changed"):
            client.request("build-body", BoxRecipe().model_dump(mode="json"))
        assert not (client.last_job / "complete.json").exists()


def test_duplicate_job_identity_never_replaces_a_prior_result(tmp_path):
    with WorkerClient(ROOT, tmp_path) as client:
        client.wait_ready()
        client.request("build-body", BoxRecipe().model_dump(mode="json"))
        previous = (client.last_job / "result.json").read_bytes()
        packet = json.loads((client.last_job / "request.json").read_bytes())
        write_result(client.session / "pending.json", packet)
        wait_until(lambda: client.process.poll() is not None)
        assert (client.last_job / "result.json").read_bytes() == previous


def test_idle_expiry_starts_after_warmup_and_releases_engine(tmp_path):
    with WorkerClient(ROOT, tmp_path, idle_timeout=0.2) as client:
        ready = client.wait_ready()
        with ProcessProbe(ready["worker_pid"]) as probe:
            wait_until(lambda: client.process.poll() is not None)
            assert not probe.alive()
        retired = read_record(client.session / "retired.json")
        assert retired["reason"] == "idle_timeout" and retired["cleaned_up"]


def test_abrupt_engine_exit_is_detected_and_never_overwrites_completed_job(tmp_path):
    with WorkerClient(ROOT, tmp_path) as client:
        client.wait_ready()
        built = client.request("build-body", BoxRecipe().model_dump(mode="json"))
        previous = (client.last_job / "result.json").read_bytes()
        terminate_record(read_record(client.session / "engine-launcher.json")["process"], group=True)
        wait_until(lambda: client.process.poll() is not None)
        assert (client.last_job / "result.json").read_bytes() == previous
        assert not (client.last_job / "error.json").exists()
        assert Path(built["project_path"]).is_file()


def test_wrong_session_identity_cannot_cancel_another_worker(tmp_path):
    with WorkerClient(ROOT, tmp_path) as client:
        client.wait_ready()
        with pytest.raises(ValueError, match="identity"):
            stop_session(client.session, "0" * 32)
        assert not (client.session / "stop.json").exists()
        assert client.request("build-body", BoxRecipe().model_dump(mode="json"))["geometry"]["volume_m3"] > 0
