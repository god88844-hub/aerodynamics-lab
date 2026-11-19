"""Kernel tests also run as a required desktop CI step with CAD installed."""

from hashlib import sha256
import json
from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")

from aeroforge_schemas.cad import BladeRecipe
from aeroforge_schemas.project import EngineeringProject
from app.services.project_assets import copy_assets, verify_assets
from app.services.project_service import run_project
from geometry.cad_backend import build_blade_project, constrained_rectangle

ROOT = Path(__file__).resolve().parents[2]


def test_constrained_geometry_blade_step_mesh_and_portable_project(tmp_path):
    recipe = BladeRecipe.model_validate_json((ROOT / "data/cad/blade-example.json").read_bytes())
    built = build_blade_project(recipe, tmp_path / "blade")
    project_path = Path(built["project_path"])
    project = EngineeringProject.model_validate_json(project_path.read_bytes())
    paths = {asset.id: project_path.parent / asset.path for asset in project.assets}
    verify_assets(project, project_path.parent)
    exact = cq.importers.importStep(str(paths["blade_exact"])).val()
    assert exact.isValid() and len(exact.Solids()) == 1
    assert exact.Volume() * 1e-9 == pytest.approx(built["geometry"]["volume_m3"], rel=1e-7)
    assert exact.BoundingBox().xlen / 1000 == pytest.approx(0.19, abs=1e-6)
    assert built["geometry"]["uniform_density_mass_estimate_kg"] is None
    assert built["geometry"]["physical_validation_status"] == "unvalidated"
    assert built["geometry"]["constraint_check"]["area_m2"] == pytest.approx(0.045 * 0.018, rel=1e-7)
    mesh = json.loads(paths["blade_mesh"].read_text(encoding="utf-8"))
    assert mesh["units"] == "m" and mesh["triangles"]
    assert max(vertex[0] for vertex in mesh["vertices_m"]) == pytest.approx(0.22, abs=1e-6)
    destination = tmp_path / "copy"
    destination.mkdir()
    copy_assets(project, project_path.parent, destination / "project.json")
    verify_assets(project, destination)
    exact_relative = next(asset.path for asset in project.assets if asset.id == "blade_exact")
    assert (destination / exact_relative).read_bytes() == paths["blade_exact"].read_bytes()
    with pytest.raises(ValueError, match="no implemented simulation backend"):
        run_project(project)


def test_recipe_edits_change_the_constructed_geometry(tmp_path):
    source = json.loads((ROOT / "data/cad/blade-example.json").read_text(encoding="utf-8"))
    original = build_blade_project(BladeRecipe.model_validate(source), tmp_path / "a")
    source["stations"][1]["chord_m"] = 0.05
    source["material_density_kg_m3"] = 1500
    changed = build_blade_project(BladeRecipe.model_validate(source), tmp_path / "b")
    assert changed["geometry"]["volume_m3"] != pytest.approx(original["geometry"]["volume_m3"], rel=1e-4)
    assert changed["geometry"]["uniform_density_mass_estimate_kg"] == pytest.approx(
        changed["geometry"]["volume_m3"] * 1500)
    assert changed["project"]["assets"][0]["sha256"] != original["project"]["assets"][0]["sha256"]


def test_bad_station_order_and_sketch_dimensions_are_refused():
    with pytest.raises(ValueError):
        BladeRecipe(stations=[
            {"radius_m": 0.1, "chord_m": 0.03, "twist_deg": 5},
            {"radius_m": 0.05, "chord_m": 0.03, "twist_deg": 5}])
    with pytest.raises(ValueError):
        constrained_rectangle(-0.1, 0.02)
