"""Exercise project compatibility and backend refusal through normal entry points."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from aeroforge_schemas.project import EngineeringProject, import_legacy_project
from app.main import app
from app.services.project_service import run_project

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def legacy():
    return json.loads((ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8"))


def test_legacy_import_round_trip_and_real_solver(legacy):
    imported = import_legacy_project(legacy)
    with TestClient(app) as client:
        response = client.post("/api/projects/import-legacy", json={"snapshot": legacy})
        schema = client.get("/api/projects/schema")
    assert response.status_code == 200
    assert response.json()["project_sha256"] == imported.fingerprint()
    assert schema.status_code == 200 and schema.json()["title"] == "EngineeringProject"
    assert imported == import_legacy_project(legacy)
    restored = EngineeringProject.model_validate_json(imported.canonical_bytes())
    assert restored.canonical_bytes() == imported.canonical_bytes()
    assert restored.vehicle.snapshot.model_dump(mode="json") == imported.vehicle.snapshot.model_dump(mode="json")
    restored.experiment.parameters = {"duration_s": 0.02}
    report = run_project(restored)
    assert report["result"]["status"] == "completed"
    assert report["project_sha256"] == sha256(restored.canonical_bytes()).hexdigest()
    assert report["physical_validation_status"] == "unvalidated"
    assert report["result"]["telemetry"]["t"]


@pytest.mark.parametrize("family", ["multirotor", "fixed_wing", "helicopter", "vtol"])
def test_project_api_handles_each_family_without_inventing_a_backend(family):
    document = {"id": str(uuid4()), "name": "New design", "aircraft_family": family,
                "vehicle": {"format": "assembly_1", "nodes": [{"id": "body", "name": "Body"}]}}
    with TestClient(app) as client:
        response = client.post("/api/projects/validate", json=document)
    assert response.status_code == 200, response.text
    normalized = response.json()["project"]
    project = EngineeringProject.model_validate(normalized)
    assert response.json()["project_sha256"] == project.fingerprint()
    with pytest.raises(ValueError, match="no implemented simulation backend"):
        run_project(project)


def test_invalid_hierarchy_frames_and_nonfinite_values_are_rejected(legacy):
    source = import_legacy_project(legacy).model_dump(mode="json")
    source["aircraft_family"] = "fixed_wing"
    with pytest.raises(ValidationError, match="legacy snapshots describe multirotors"):
        EngineeringProject.model_validate(source)
    source = {"id": str(uuid4()), "name": "bad", "aircraft_family": "vtol",
              "vehicle": {"format": "assembly_1", "nodes": [
                  {"id": "a", "name": "A", "parent_id": "b"},
                  {"id": "b", "name": "B", "parent_id": "a"}]}}
    with pytest.raises(ValidationError, match="cycle"):
        EngineeringProject.model_validate(source)
    source["vehicle"]["nodes"][1]["parent_id"] = "missing"
    with pytest.raises(ValidationError, match="missing parent"):
        EngineeringProject.model_validate(source)
    source["vehicle"]["nodes"] = [{"id": "a", "name": "A", "orientation_wxyz": [2, 0, 0, 0]}]
    with pytest.raises(ValidationError, match="unit quaternion"):
        EngineeringProject.model_validate(source)
    source = import_legacy_project(legacy).model_dump(mode="json")
    source["environment"]["wind_world_m_s"] = [float("nan"), 0, 0]
    with pytest.raises(ValidationError):
        EngineeringProject.model_validate(source)
    source["environment"] = {"world_frame": "NED"}
    with pytest.raises(ValidationError):
        EngineeringProject.model_validate(source)


def test_nondefault_environment_is_stored_and_explicitly_refused(legacy):
    project = import_legacy_project(legacy)
    project.environment.wind_world_m_s = (4.0, 0.0, 0.0)
    restored = EngineeringProject.model_validate_json(project.canonical_bytes())
    assert restored.environment.wind_world_m_s == (4.0, 0.0, 0.0)
    with pytest.raises(ValueError, match="fixed default environment"):
        run_project(restored)


@pytest.mark.parametrize("path", ["../part.step", "/part.step", "C:/part.step", "part\\file.step"])
def test_asset_paths_cannot_escape_project(path):
    document = {"id": str(uuid4()), "name": "geometry", "aircraft_family": "fixed_wing",
                "vehicle": {"format": "assembly_1"},
                "assets": [{"id": "wing", "path": path, "sha256": "a" * 64, "role": "exact_geometry"}]}
    with pytest.raises(ValidationError, match="project-relative"):
        EngineeringProject.model_validate(document)


def test_cli_import_validate_and_run_without_changing_source(tmp_path, legacy):
    source = tmp_path / "legacy.json"
    source.write_text(json.dumps(legacy), encoding="utf-8")
    original = source.read_bytes()
    project_path, checked, result = (tmp_path / name for name in ("project.json", "checked.json", "run.json"))
    script = str(ROOT / "scripts/lab_project.py")
    def invoke(command, input_path, output_path):
        return subprocess.run([sys.executable, script, command, str(input_path), str(output_path)],
                              capture_output=True, text=True, timeout=45)
    imported = invoke("import-legacy", source, project_path)
    assert imported.returncode == 0, imported.stderr
    document = json.loads(project_path.read_text(encoding="utf-8"))
    document["experiment"]["parameters"] = {"duration_s": 0.02}
    project_path.write_text(json.dumps(document), encoding="utf-8")
    validated = invoke("validate", project_path, checked)
    assert validated.returncode == 0, validated.stderr
    simulated = invoke("run", checked, result)
    assert simulated.returncode == 0, simulated.stderr
    assert json.loads(result.read_text(encoding="utf-8"))["result"]["status"] == "completed"
    assert source.read_bytes() == original
    before = checked.read_bytes()
    assert invoke("validate", checked, checked).returncode != 0
    assert checked.read_bytes() == before
