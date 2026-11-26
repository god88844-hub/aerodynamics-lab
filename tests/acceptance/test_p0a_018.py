"""P0A-018 acceptance tests: 3D CAD editor (body/blade/transform, undo/redo,
Fusion-style CAD PBR materials, and edit -> save -> reload exact-geometry identity).
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from aeroforge_schemas.cad import BladeRecipe, BladeStation, BoxRecipe
from aeroforge_schemas.project import EngineeringProject

ROOT = Path(__file__).resolve().parents[2]
LAB_PROJECT = ROOT / "scripts" / "lab_project.py"
ASSEMBLY_200 = ROOT / "data" / "benchmarks" / "assembly-200"


def _run_lab(command: str, inp: Path, out: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    err = out.with_name(out.stem + "-error.json")
    comp = out.with_name(out.stem + "-complete.json")
    return subprocess.run(
        [
            sys.executable,
            str(LAB_PROJECT),
            command,
            str(inp),
            str(out),
            "--error-output",
            str(err),
            "--completion-output",
            str(comp),
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_edit_save_reload_preserves_exact_geometry_and_transform_identity(tmp_path):
    proj_dir = tmp_path / "source"
    shutil.copytree(ASSEMBLY_200, proj_dir)
    doc = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))

    # Edit transform of first assembly node (position + 90 deg yaw quaternion wxyz)
    doc["vehicle"]["nodes"][0]["position_m"] = [0.15, -0.05, 0.02]
    doc["vehicle"]["nodes"][0]["orientation_wxyz"] = [0.7071067811865476, 0.0, 0.0, 0.7071067811865476]
    edited_in = tmp_path / "edited.json"
    edited_in.write_text(json.dumps(doc), encoding="utf-8")

    # Validate -> package (save) -> reload -> verify exact geometry STEP asset SHA-256 unchanged
    validated = tmp_path / "validated.json"
    assert _run_lab("validate", edited_in, validated, "--asset-root", str(proj_dir)).returncode == 0

    saved_dir = tmp_path / "saved"
    saved_file = saved_dir / "project.json"
    assert _run_lab("package", validated, saved_file, "--asset-root", str(proj_dir)).returncode == 0

    reloaded = tmp_path / "reloaded.json"
    assert _run_lab("validate", saved_file, reloaded, "--asset-root", str(saved_dir)).returncode == 0
    reloaded_doc = json.loads(reloaded.read_text(encoding="utf-8"))

    assert reloaded_doc["vehicle"]["nodes"][0]["position_m"] == [0.15, -0.05, 0.02]
    exact_assets = [a for a in reloaded_doc["assets"] if a["role"] == "exact_geometry"]
    assert exact_assets
    for asset in exact_assets:
        disk_bytes = (saved_dir / asset["path"]).read_bytes()
        assert sha256(disk_bytes).hexdigest() == asset["sha256"]


def test_parametric_blade_and_box_constraints_enforce_valid_domains():
    # Valid constrained recipes
    box = BoxRecipe(width_m=0.25, height_m=0.12, depth_m=0.03, material_density_kg_m3=2700.0)
    assert box.width_m == 0.25
    blade = BladeRecipe(
        stations=[
            BladeStation(radius_m=0.025, chord_m=0.032, twist_deg=22.0, thickness_to_chord=0.12),
            BladeStation(radius_m=0.19, chord_m=0.016, twist_deg=8.0, thickness_to_chord=0.12),
        ]
    )
    assert blade.stations[1].radius_m > blade.stations[0].radius_m

    # Tip radius <= root radius must fail closed
    with pytest.raises(ValueError, match="strictly increasing radii"):
        BladeRecipe(
            stations=[
                BladeStation(radius_m=0.15, chord_m=0.03, twist_deg=10.0),
                BladeStation(radius_m=0.10, chord_m=0.02, twist_deg=5.0),
            ]
        )

    # Non-unit quaternion transform must fail closed
    raw = json.loads((ASSEMBLY_200 / "project.json").read_text(encoding="utf-8"))
    raw["vehicle"]["nodes"][0]["orientation_wxyz"] = [2.0, 0.0, 0.0, 0.0]
    with pytest.raises(ValueError, match="unit quaternion"):
        EngineeringProject.model_validate(raw)


def test_desktop_3d_editor_exposes_cad_edit_undo_redo_and_pbr_presets():
    main_gd = (ROOT / "apps" / "desktop" / "main.gd").read_text(encoding="utf-8")
    for required in (
        "_open_blade_editor",
        "_rebuild_blade",
        "_open_body_editor",
        "_rebuild_body",
        "_open_transform_editor",
        "_apply_node_transform",
        "_undo_edit",
        "_redo_edit",
        "_make_cad_material",
        "alu_6061_t6",
        "cfrp_quasi_iso",
        "pa12_nylon",
        "rim_enabled",
        "_toggle_lighting_mode",
        "not full freeform sketcher",
    ):
        assert required in main_gd


def test_occt_blade_edit_save_reload_exact_step_roundtrip_if_available(tmp_path):
    cq = pytest.importorskip("cadquery")
    assert cq is not None
    from geometry.cad_backend import build_blade_project

    blade1 = BladeRecipe(
        name="P0A018 Blade R1",
        stations=[
            BladeStation(radius_m=0.025, chord_m=0.032, twist_deg=22.0),
            BladeStation(radius_m=0.19, chord_m=0.016, twist_deg=8.0),
        ],
        material_density_kg_m3=1550.0,
    )
    blade2 = BladeRecipe(
        name="P0A018 Blade R2",
        stations=[
            BladeStation(radius_m=0.025, chord_m=0.032, twist_deg=22.0),
            BladeStation(radius_m=0.19, chord_m=0.024, twist_deg=8.0),
        ],
        material_density_kg_m3=1550.0,
    )
    dir1 = tmp_path / "r1"
    dir2 = tmp_path / "r2"
    out1 = build_blade_project(blade1, dir1)
    out2 = build_blade_project(blade2, dir2)
    assert out2["geometry"]["mass_properties"]["mass_kg"] > out1["geometry"]["mass_properties"]["mass_kg"]

    saved_dir = tmp_path / "saved_r2"
    saved_proj = saved_dir / "project.json"
    assert _run_lab("package", dir2 / "project.json", saved_proj, "--asset-root", str(dir2)).returncode == 0
    reloaded = tmp_path / "reloaded_r2.json"
    assert _run_lab("validate", saved_proj, reloaded, "--asset-root", str(saved_dir)).returncode == 0
    assert json.loads(reloaded.read_text(encoding="utf-8")) == out2["project"]
