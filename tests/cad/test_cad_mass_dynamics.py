"""Exact solid properties and dynamics must agree with independent analytic cases."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

cq = pytest.importorskip("cadquery")

from aeroforge_schemas.cad import BoxRecipe, CadTorqueRequest, TorqueExperiment
from aeroforge_schemas.project import EngineeringProject
from app.services.project_assets import copy_assets
from geometry.cad_backend import build_box_project, solid_mass_properties
from geometry import cad_dynamics

ROOT = Path(__file__).resolve().parents[2]


def request_for(built, duration=0.2):
    return CadTorqueRequest(project=built["project"], experiment=TorqueExperiment(duration_s=duration))


def asset_path(root, built, identity):
    return root / next(asset["path"] for asset in built["project"]["assets"] if asset["id"] == identity)


def test_solved_sketch_solid_tensor_and_torque_agree_with_analytic_box(tmp_path):
    built = build_box_project(BoxRecipe(material_density_kg_m3=500), tmp_path / "body")
    mass = 500 * 0.2 * 0.1 * 0.02
    expected = mass / 12 * np.diag([0.1**2 + 0.02**2, 0.2**2 + 0.02**2, 0.2**2 + 0.1**2])
    properties = built["geometry"]["mass_properties"]
    assert properties["mass_kg"] == pytest.approx(mass, rel=1e-7)
    assert properties["center_of_mass_m"] == pytest.approx([0.1, 0.05, 0.01], abs=1e-8)
    np.testing.assert_allclose(properties["inertia_about_cog_kg_m2"], expected, rtol=1e-7, atol=2e-11)
    request = request_for(built)
    report = cad_dynamics.run_cad_torque(request, tmp_path / "body")
    trajectory = report["result"]["telemetry"]
    assert trajectory["omega_body_rad_s"][-1] == pytest.approx([0, 0, 0.001 * 0.2 / expected[2, 2]], abs=1e-8)
    theta = 0.001 * 0.2**2 / (2 * expected[2, 2])
    assert trajectory["q_wxyz"][-1] == pytest.approx([np.cos(theta / 2), 0, 0, np.sin(theta / 2)], abs=1e-8)
    assert report["physical_validation_status"] == "unvalidated"
    assert report["numerical_check"]["quaternion_component_l2_delta"] < 1e-6
    assert report == cad_dynamics.run_cad_torque(request, tmp_path / "body")


def test_tensor_units_origin_independence_and_rotation_covariance():
    shape = cq.Workplane("XY").box(200, 100, 20).val()
    original = solid_mass_properties(shape, 500)
    transformed = shape.rotate((0, 0, 0), (0, 0, 1), 30).translate((1000, -2000, 500))
    properties = solid_mass_properties(transformed, 500)
    angle = np.deg2rad(30)
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])
    expected = rotation @ np.asarray(original["inertia_about_cog_kg_m2"]) @ rotation.T
    np.testing.assert_allclose(properties["inertia_about_cog_kg_m2"], expected, rtol=1e-9, atol=1e-12)
    assert properties["center_of_mass_m"] == pytest.approx([1, -2, 0.5])
    assert properties["mass_kg"] == pytest.approx(0.2)


def test_edit_rebuild_package_and_placed_solid_change_actual_response(tmp_path):
    original = build_box_project(BoxRecipe(material_density_kg_m3=500), tmp_path / "original")
    edited = build_box_project(BoxRecipe(width_m=0.3, material_density_kg_m3=500), tmp_path / "edited")
    destination = tmp_path / "portable"
    destination.mkdir()
    project = EngineeringProject.model_validate(edited["project"])
    copy_assets(project, tmp_path / "edited", destination / "project.json")
    before = cad_dynamics.run_cad_torque(request_for(original), tmp_path / "original")
    after = cad_dynamics.run_cad_torque(request_for(edited), destination)
    assert after["mass_properties"]["mass_kg"] == pytest.approx(0.3, rel=1e-7)
    assert after["result"]["telemetry"]["omega_body_rad_s"][-1][2] < before["result"]["telemetry"]["omega_body_rad_s"][-1][2]
    # Rotate the placed node 90 degrees, so its X and Y inertia swap.
    request = request_for(edited)
    request.project.vehicle.nodes[0].position_m = (1, 2, 3)
    request.project.vehicle.nodes[0].orientation_wxyz = (np.sqrt(0.5), 0, 0, np.sqrt(0.5))
    placed = cad_dynamics.run_cad_torque(request, destination)
    tensor = np.asarray(after["mass_properties"]["inertia_about_cog_kg_m2"])
    assert placed["mass_properties"]["inertia_about_cog_kg_m2"][0][0] == pytest.approx(tensor[1, 1])
    assert placed["mass_properties"]["center_of_mass_m"] == pytest.approx([0.95, 2.15, 3.01], abs=1e-8)


def test_unknown_density_and_unsupported_environment_do_not_become_success(tmp_path):
    built = build_box_project(BoxRecipe(), tmp_path / "body")
    request = request_for(built)
    report = cad_dynamics.run_cad_torque(request, tmp_path / "body")
    assert report["result"]["status"] == "inconclusive"
    assert report["mass_properties"]["inertia_about_cog_kg_m2"] is None
    request.project.environment.wind_world_m_s = (3, 0, 0)
    with pytest.raises(ValueError, match="default environment"):
        cad_dynamics.run_cad_torque(request, tmp_path / "body")
    with pytest.raises(ValueError):
        TorqueExperiment(duration_s=10, step_s=0.0001)


def test_cached_mass_is_ignored_tampering_is_refused_and_model_change_is_detected(tmp_path, monkeypatch):
    built = build_box_project(BoxRecipe(material_density_kg_m3=500), tmp_path / "body")
    request = request_for(built)
    metadata_path = asset_path(tmp_path / "body", built, "body_recipe")
    metadata = json.loads(metadata_path.read_bytes())
    metadata["mass_properties"]["mass_kg"] = 999
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    request.project.assets[2].sha256 = sha256(metadata_path.read_bytes()).hexdigest()
    assert cad_dynamics.run_cad_torque(request, tmp_path / "body")["mass_properties"]["mass_kg"] == pytest.approx(0.2)
    calls = iter([{"version": "a"}, {"version": "b"}])
    monkeypatch.setattr(cad_dynamics, "_identity", lambda: next(calls))
    with pytest.raises(ValueError, match="changed during"):
        cad_dynamics.run_cad_torque(request, tmp_path / "body")
    asset_path(tmp_path / "body", built, "body_exact").write_bytes(b"changed exact solid")
    monkeypatch.setattr(cad_dynamics, "_identity", lambda: {})
    with pytest.raises(ValueError, match="SHA-256"):
        cad_dynamics.run_cad_torque(request, tmp_path / "body")


def test_analysis_cli_receipt_and_failure_preserve_previous_output(tmp_path):
    built = build_box_project(BoxRecipe(material_density_kg_m3=500), tmp_path / "body")
    source, output, receipt, error = [tmp_path / name for name in ("request.json", "report.json", "complete.json", "error.json")]
    source.write_text(request_for(built).model_dump_json(), encoding="utf-8")
    command = [sys.executable, str(ROOT / "scripts/lab_cad_analysis.py"), str(source), str(output),
               "--asset-root", str(tmp_path / "body"), "--completion-output", str(receipt), "--error-output", str(error)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
    previous = output.read_bytes()
    assert json.loads(receipt.read_bytes())["output_sha256"] == sha256(previous).hexdigest()
    receipt.unlink()
    exact_path = asset_path(tmp_path / "body", built, "body_exact")
    original_solid = exact_path.read_bytes()
    colliding = command.copy()
    colliding[3] = str(exact_path)
    collision = subprocess.run(colliding, capture_output=True, text=True, timeout=45)
    assert collision.returncode == 2 and exact_path.read_bytes() == original_solid
    exact_path.write_bytes(b"broken source")
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    assert result.returncode == 2 and "SHA-256" in error.read_text()
    assert output.read_bytes() == previous and not receipt.exists()


def test_edited_project_versions_save_into_one_folder_without_losing_previous_assets(tmp_path):
    original = build_box_project(BoxRecipe(material_density_kg_m3=500), tmp_path / "first")
    edited = build_box_project(BoxRecipe(width_m=0.3, material_density_kg_m3=500), tmp_path / "second")
    saved = tmp_path / "saved"
    saved.mkdir()
    script = str(ROOT / "scripts/lab_project.py")
    for built, name in ((original, "v0.json"), (original, "v1.json"), (edited, "v2.json"), (edited, "v1.json")):
        result = subprocess.run([sys.executable, script, "package", built["project_path"], str(saved / name)],
                                capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stderr
    assert EngineeringProject.model_validate_json((saved / "v1.json").read_bytes()).fingerprint() == edited["project_sha256"]
    for built in (original, edited):
        for asset in built["project"]["assets"]:
            assert Path(asset["path"]).parent.name == asset["sha256"]
            assert sha256((saved / asset["path"]).read_bytes()).hexdigest() == asset["sha256"]
        report = cad_dynamics.run_cad_torque(request_for(built), saved)
        assert report["result"]["status"] == "completed"
    # Open the earlier saved snapshot alongside the edited one.
    restored = EngineeringProject.model_validate_json((saved / "v0.json").read_bytes())
    assert cad_dynamics.run_cad_torque(CadTorqueRequest(project=restored), saved)["mass_properties"]["mass_kg"] == pytest.approx(0.2)


def test_legacy_flat_asset_paths_still_run(tmp_path):
    built = build_box_project(BoxRecipe(material_density_kg_m3=500), tmp_path / "body")
    request = request_for(built)
    legacy = tmp_path / "legacy"
    (legacy / "assets").mkdir(parents=True)
    for asset in request.project.assets:
        source = tmp_path / "body" / asset.path
        target = legacy / "assets" / source.name
        target.write_bytes(source.read_bytes())
        asset.path = target.relative_to(legacy).as_posix()
    report = cad_dynamics.run_cad_torque(request, legacy)
    assert report["mass_properties"]["mass_kg"] == pytest.approx(0.2)
