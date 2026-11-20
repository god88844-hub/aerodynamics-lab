"""Exercise refusal, overage, completion binding and recovery with real workers."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

pytest.importorskip("cadquery")
from aeroforge_schemas.cad import BoxRecipe
from desktop_worker.client import WorkerClient, verify_approval
from desktop_worker.resources import GIB, MIB, ResourceBudget
from desktop_worker.supervision import read_record
from desktop_worker.metrics import ProcessTreeObserver

ROOT = Path(__file__).resolve().parents[2]


def test_impossible_allowance_is_refused_before_launch(tmp_path):
    with WorkerClient(ROOT, tmp_path, resources=ResourceBudget(memory_bytes=1024 * GIB)) as client:
        with pytest.raises(RuntimeError, match="insufficient_memory_headroom"):
            client.wait_ready()
        assert not (client.session / "engine-launcher.json").exists()
        assert read_record(client.session / "retired.json")["cleaned_up"]


def test_real_startup_resident_overage_stops_without_success(tmp_path):
    with WorkerClient(ROOT, tmp_path, resources=ResourceBudget(memory_bytes=16 * MIB)) as client:
        with pytest.raises(RuntimeError, match="memory_budget_exceeded"):
            client.wait_ready()
        retired = read_record(client.session / "retired.json")
        assert retired["cleaned_up"]
        usage = read_record(client.session / "resource-usage.json")
        assert usage["peak_resident_bytes"] > 16 * MIB
        assert not list(client.session.rglob("complete.json"))


def test_real_workspace_overage_preserves_completed_assets_and_recovers(tmp_path):
    with WorkerClient(ROOT, tmp_path, resources=ResourceBudget(workspace_bytes=MIB)) as client:
        client.wait_ready()
        built = client.request("build-body", BoxRecipe().model_dump(mode="json"))
        previous = client.last_job
        frozen = (previous / "result.json").read_bytes()
        receipt = read_record(previous / "complete.json")
        verify_approval(previous, receipt)
        # An authentic completion cannot be paired with changed resource approval.
        approved_path = previous / "approved.json"
        original_approval = approved_path.read_bytes()
        approved_path.write_bytes(original_approval + b" ")
        with pytest.raises(ValueError, match="approval"):
            verify_approval(previous, receipt)
        approved_path.write_bytes(original_approval)
        recipe = json.loads((ROOT / "data/cad/blade-example.json").read_bytes())
        recipe["profile_samples"] = 128
        recipe["mesh_deflection_m"] = 0.00001
        with pytest.raises(RuntimeError, match="workspace_budget_exceeded"):
            client.request("build-blade", recipe)
        assert not (client.last_job / "complete.json").exists()
        assert (previous / "result.json").read_bytes() == frozen
        for asset in built["project"]["assets"]:
            assert sha256((Path(built["project_path"]).parent / asset["path"]).read_bytes()).hexdigest() == asset["sha256"]
    with WorkerClient(ROOT, tmp_path) as recovered:
        recovered.wait_ready()
        assert recovered.request("build-body", BoxRecipe().model_dump(mode="json"))["project"]


def test_changed_session_budget_cannot_get_a_completion(tmp_path):
    with WorkerClient(ROOT, tmp_path) as client:
        client.wait_ready()
        client.resources = ResourceBudget(workspace_bytes=2 * MIB)
        with pytest.raises(RuntimeError, match="limits must match"):
            client.request("build-body", BoxRecipe().model_dump(mode="json"))
        assert not (client.last_job / "complete.json").exists()


def test_active_cad_cancel_records_cli_latency_and_owned_resident_reclamation(tmp_path):
    """Measure the same stop CLI invoked by Godot; no system-wide RAM claim."""
    with WorkerClient(ROOT, tmp_path) as client:
        ready = client.wait_ready()
        built = client.request("build-body", BoxRecipe(material_density_kg_m3=500).model_dump(mode="json"))
        previous_result = (client.last_job / "result.json").read_bytes()
        previous_directory = client.last_job
        payload = {"project": built["project"], "experiment": {
            "duration_s": 5.0, "step_s": .001, "torque_body_nm": [0, 0, .00001]}}
        errors = []

        def run():
            try:
                client.request("cad-torque", payload, asset_root=Path(built["project_path"]).parent)
            except RuntimeError as error:
                errors.append(str(error))

        observer = ProcessTreeObserver(client.process.pid)
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while client.last_job == previous_directory or not (client.last_job / "started.json").exists():
                if time.monotonic() > deadline:
                    pytest.fail("CAD cancellation did not reach an active job")
                observer.sample()
                time.sleep(.01)
            for _ in range(3):
                time.sleep(.1)
                before = observer.sample()
            assert not (client.last_job / "complete.json").exists(), "Job finished before cancellation"
            assert any(p["pid"] == ready["worker_pid"] for p in before["processes"])
            resident_before = sum(p["resident_bytes"] for p in before["processes"])
            started = time.perf_counter_ns()
            cancelled = subprocess.run([sys.executable, str(ROOT / "scripts/lab_worker.py"),
                "--session", str(client.session), "--session-id", client.session_id, "--stop"],
                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            latency_ns = time.perf_counter_ns() - started
            assert cancelled.returncode == 0, cancelled.stderr
            client.process.wait(timeout=5)
            after = observer.sample()
            resident_after = sum(p["resident_bytes"] for p in after["processes"])
            assert not any(ref.alive() for ref in observer.processes.values())
            assert not (client.last_job / "complete.json").exists()
            assert (previous_directory / "result.json").read_bytes() == previous_result
            assert latency_ns / 1e9 <= 5
            assert resident_before > 0 and resident_after == 0
            print("CAD_CANCEL_RECEIPT=" + json.dumps({"platform": sys.platform,
                "source_sha": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
                "method": "normal Godot stop CLI; perf_counter_ns around subprocess.run; 100 ms pre-action resident sampling",
                "active_worker_pid": ready["worker_pid"], "cancel_cli_return_ns": latency_ns,
                "pre_cancel_owned_resident_bytes": resident_before, "post_cancel_owned_resident_bytes": resident_after,
                "owned_resident_reclaimed_percent": 100.0, "cleanup_verified": True,
                "previous_result_preserved": True, "completion_published": False,
                "scope": "CI host process tree, not local graphical timing or system/GPU physical RAM"}, sort_keys=True))
        finally:
            client.close()
            thread.join(timeout=5)
            observer.close()
        assert errors and not thread.is_alive()
