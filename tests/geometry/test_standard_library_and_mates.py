"""Tests for the Expanded Standard Part & Propulsion Library and Multi-Body Mechanical Mates."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from geometry.mechanical_mates import solve_mechanical_mates
from geometry.standard_library import build_standard_bom_summary, get_standard_part, list_standard_library, load_standard_library

ROOT = Path(__file__).resolve().parents[2]


def test_standard_library_catalog_completeness_and_bom() -> None:
    cat = load_standard_library()
    items = cat["items"]
    assert len(items) >= 75
    assert len(cat["categories"]) >= 8
    motors = list_standard_library("Motors")
    bearings = list_standard_library("Bearings & Guides")
    fasteners = list_standard_library("Fasteners")
    tubes = list_standard_library("Tubes & Structures")
    assert len(motors) >= 10 and len(bearings) >= 8 and len(fasteners) >= 10 and len(tubes) >= 6
    m4 = get_standard_part("bolt_iso4762_m4")
    assert m4["shear_capacity_n"] == 6320.0
    bom = build_standard_bom_summary(["motor_mn3508_kv380", "bearing_608zz", "bolt_iso4762_m4", "tube_cf_16x14_400"])
    assert bom["count"] == 4
    assert abs(bom["total_mass_kg"] - (0.103 + 0.012 + 0.0023 + 0.0294)) < 1e-6


def test_multi_body_mechanical_mates_all_joint_types_and_limits() -> None:
    spec = {
        "animate": False,
        "external_load_scale": 1.2,
        "bodies": [
            {"id": "chassis", "name": "Airframe", "mass_kg": 1.2, "grounded": True, "half_extents_m": [0.1, 0.1, 0.04]},
            {"id": "nacelle_l", "name": "Left Tilt Nacelle", "mass_kg": 0.3, "half_extents_m": [0.04, 0.04, 0.04]},
            {"id": "nacelle_r", "name": "Right Tilt Nacelle", "mass_kg": 0.3, "half_extents_m": [0.04, 0.04, 0.04]},
            {"id": "rotor_l", "name": "Left Rotor", "mass_kg": 0.08, "half_extents_m": [0.15, 0.03, 0.01]},
            {"id": "winch_load", "name": "Slider Mount", "mass_kg": 0.25, "half_extents_m": [0.03, 0.03, 0.03]},
            {"id": "gimbal", "name": "Camera Gimbal", "mass_kg": 0.22, "half_extents_m": [0.04, 0.04, 0.04]},
        ],
        "mates": [
            {"id": "tilt_l", "kind": "revolute", "parent_body": "chassis", "child_body": "nacelle_l", "anchor_parent_m": [0.0, 0.45, 0.0], "axis_local": [0.0, 1.0, 0.0], "drive_value": 45.0, "limit_min": 0.0, "limit_max": 90.0, "load_capacity_n": 3350.0},
            {"id": "tilt_r", "kind": "gear", "parent_body": "chassis", "child_body": "nacelle_r", "coupled_mate_id": "tilt_l", "gear_ratio": 1.0, "anchor_parent_m": [0.0, -0.45, 0.0], "axis_local": [0.0, 1.0, 0.0]},
            {"id": "spin_l", "kind": "cylindrical", "parent_body": "nacelle_l", "child_body": "rotor_l", "anchor_parent_m": [0.0, 0.0, 0.08], "axis_local": [0.0, 0.0, 1.0], "drive_value": 0.02, "secondary_value": 90.0, "limit_min": 0.0, "limit_max": 0.1},
            {"id": "rack_slide", "kind": "rack_pinion", "parent_body": "chassis", "child_body": "winch_load", "coupled_mate_id": "tilt_l", "pitch_radius_m": 0.05, "anchor_parent_m": [-0.2, 0.0, -0.1], "axis_local": [0.0, 0.0, -1.0]},
            {"id": "ball_cam", "kind": "spherical", "parent_body": "winch_load", "child_body": "gimbal", "anchor_parent_m": [0.0, 0.0, -0.05], "drive_value": 15.0, "secondary_value": -10.0, "limit_min": -45.0, "limit_max": 45.0},
        ],
    }
    res = solve_mechanical_mates(spec)
    assert res["active_mates"] == 5
    assert not res["any_limit_violated"]
    assert not res["any_interference"]
    poses = {p["body_id"]: p for p in res["body_poses"]}
    assert poses["nacelle_l"]["quat_wxyz"] == poses["nacelle_r"]["quat_wxyz"]
    assert abs(poses["winch_load"]["world_pos_m"][0] - (-0.2)) < 1e-5
    # Verify pitch_radius * radians(45) downward travel on Z
    expected_z = -0.1 - (0.05 * 3.141592653589793 / 4.0)
    assert abs(poses["winch_load"]["world_pos_m"][2] - expected_z) < 1e-4

    # Limit violation test
    spec_bad = json.loads(json.dumps(spec))
    spec_bad["mates"][0]["drive_value"] = 125.0
    res_bad = solve_mechanical_mates(spec_bad)
    assert res_bad["any_limit_violated"]


def test_cli_standard_library_and_solve_mates(tmp_path: Path) -> None:
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps({"category": "Fasteners", "bom_part_ids": ["bolt_iso4762_m4"]}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "standard-library", str(inp), str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["items"]) >= 10
    assert data["bom"]["total_mass_kg"] == 0.0023
