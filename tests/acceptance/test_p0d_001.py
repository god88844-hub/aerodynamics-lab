"""P0D-001: Supported CAD part design, redesign, swap, 4-quadrant native workbench, and STEP/STL/DXF/SVG exchange."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from geometry.fixed_wing_cad import ParametricWingSpec, export_2d_engineering_drawing_svg_dxf, export_cad_exchange_manifest
from geometry.part_designer import CustomPartRecipe, build_custom_part, swap_assembly_part

ROOT = Path(__file__).resolve().parents[2]


def test_p0d_001_custom_part_redesign_swap_and_drawings(tmp_path):
    recipe = CustomPartRecipe(
        part_name="CustomCarbonArm",
        sketch_kind="rounded_plate",
        width_m=0.045,
        length_m=0.22,
        thickness_m=0.010,
        hole_radius_m=0.008,
        density_kg_m3=1580.0,
        density_source="CFRP_T300_SPEC",
    )
    built = build_custom_part(recipe, export_dir=tmp_path / "arm_out")
    assert built["mass_kg"] > 0.0
    assert Path(built["exports"]["dxf"]).is_file()
    assert Path(built["exports"]["stl"]).is_file()

    parts = [
        {"name": "FuselageHub", "mass_kg": 0.90, "position_m": [0.0, 0.0, 0.0]},
        {"name": "Arm-1", "mass_kg": 0.12, "position_m": [0.18, 0.0, 0.0]},
    ]
    swapped = swap_assembly_part(parts, target_part_name="Arm-1", replacement=recipe, replacement_position_m=(0.24, 0.0, 0.0))
    assert swapped["replaced_part"] == "Arm-1"
    assert swapped["physical_validation_status"] == "UNVALIDATED_CUSTOM"
    assert swapped["total_mass_kg"] > 0.90

    in_p = tmp_path / "part_in.json"
    out_p = tmp_path / "part_out.json"
    in_p.write_text(json.dumps({"part_name": "CliArm", "density_source": "CFRP_SPEC", "export_dir": str(tmp_path / "cli_part")}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "build-custom-part", str(in_p), str(out_p)], check=True, cwd=ROOT)
    assert json.loads(out_p.read_text(encoding="utf-8"))["mass_kg"] > 0.0

    wing = ParametricWingSpec(name="DrawWing", wingspan_m=1.6, root_chord_m=0.24, tip_chord_m=0.14)
    assert export_cad_exchange_manifest(wing)["authoritative_exact"] is True
    drw = export_2d_engineering_drawing_svg_dxf(wing, svg_path=tmp_path / "d.svg", dxf_path=tmp_path / "d.dxf")
    assert len(drw["outputs"]["svg"]["sha256"]) == 64

    assert (ROOT / "apps" / "native" / "CMakeLists.txt").is_file()
    assert (ROOT / "apps" / "native" / "src" / "viewport_gl.cpp").is_file()
