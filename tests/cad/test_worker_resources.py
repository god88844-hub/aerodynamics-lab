"""Exercise refusal, overage, completion binding and recovery with real workers."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

pytest.importorskip("cadquery")
from aeroforge_schemas.cad import BoxRecipe
from desktop_worker.client import WorkerClient, verify_approval
from desktop_worker.resources import GIB, MIB, ResourceBudget
from desktop_worker.supervision import read_record

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
