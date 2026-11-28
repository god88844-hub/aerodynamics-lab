"""Tests for custom part design, STL/DXF export, provenance refusal, and assembly part swap."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from geometry.part_designer import CustomPartRecipe, build_custom_part, swap_assembly_part

ROOT = Path(__file__).resolve().parents[2]


def test_custom_part_requires_density_provenance() -> None:
    with pytest.raises(ValueError, match="density_source provenance"):
        CustomPartRecipe(part_name="Arm", density_kg_m3=1580.0, density_source="")


def test_build_custom_part_exports_dxf_and_stl_and_preserves_mass(tmp_path: Path) -> None:
    recipe = CustomPartRecipe(
        part_name="Carbon Arm V2",
        sketch_kind="rounded_plate",
        width_m=0.04,
        length_m=0.25,
        thickness_m=0.01,
        hole_radius_m=0.005,
        circular_pattern_count=4,
        density_kg_m3=1600.0,
        density_source="toray_t300_datasheet",
    )
    out = build_custom_part(recipe, export_dir=tmp_path)
    assert out["mass_kg"] > 0.0
    assert out["physical_validation_status"] == "UNVALIDATED_CUSTOM"
    assert Path(out["exports"]["dxf"]).is_file()
    assert Path(out["exports"]["stl"]).is_file()
    assert "CircularPattern_x4" in out["feature_history"]


def test_swap_assembly_part_updates_total_mass_and_cog() -> None:
    parts = [
        {"name": "center_frame", "mass_kg": 1.0, "position_m": [0.0, 0.0, 0.0]},
        {"name": "old_arm", "mass_kg": 0.2, "position_m": [0.3, 0.0, 0.0]},
    ]
    replacement = CustomPartRecipe(
        part_name="Heavy Ducted Arm",
        sketch_kind="ring_duct",
        width_m=0.08,
        length_m=0.20,
        thickness_m=0.012,
        density_kg_m3=1580.0,
        density_source="builtin_cfrp",
    )
    res = swap_assembly_part(parts, target_part_name="old_arm", replacement=replacement, replacement_position_m=(0.4, 0.0, 0.0))
    assert res["new_part"] == "Heavy Ducted Arm"
    assert res["total_mass_kg"] > 1.0
    assert res["center_of_mass_m"][0] > 0.0


def test_cli_build_custom_part_roundtrip(tmp_path: Path) -> None:
    in_path = tmp_path / "part_in.json"
    out_path = tmp_path / "part_out.json"
    for sk in ("airfoil_section", "custom_propeller", "custom_body_shell"):
        in_path.write_text(
            json.dumps(
                {
                    "part_name": f"Custom {sk}",
                    "sketch_kind": sk,
                    "length_m": 0.22,
                    "width_m": 0.04,
                    "thickness_m": 0.012,
                    "circular_pattern_count": 3,
                    "density_kg_m3": 450.0,
                    "density_source": "aircraft_spruce_spec",
                    "export_dir": str(tmp_path / "cad_out"),
                }
            ),
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/lab_project.py"), "build-custom-part", str(in_path), str(out_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        assert proc.returncode == 0
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload["sketch_kind"] == sk
        assert payload["mass_kg"] > 0.0
        assert Path(payload["exports"]["dxf"]).is_file()
        assert Path(payload["exports"]["stl"]).is_file()
