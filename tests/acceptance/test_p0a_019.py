"""P0A-019 acceptance tests: arbitrary rotor layouts, component selection, BOM,
analytic CoG/inertia verification, and fail-closed missing density/source refusal.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from physics.dynamics.assembly_layout import build_multirotor_layout_and_bom
from physics.propulsion.loader import ComponentLibrary

ROOT = Path(__file__).resolve().parents[2]
LAB_PROJECT = ROOT / "scripts" / "lab_project.py"
DATA_COMPONENTS = ROOT / "data" / "components"


def test_arbitrary_layouts_and_analytic_cog_inertia():
    library = ComponentLibrary(DATA_COMPONENTS)

    # 1. Symmetric quadrotor (4 rotors at +-0.3 m on X/Y axes) -> CoG = [0, 0, 0]
    quad_spec = {
        "rotors": [
            {"position_m": [0.3, 0.0, 0.0], "spin_direction": 1},
            {"position_m": [0.0, 0.3, 0.0], "spin_direction": -1},
            {"position_m": [-0.3, 0.0, 0.0], "spin_direction": 1},
            {"position_m": [0.0, -0.3, 0.0], "spin_direction": -1},
        ],
        "motor_id": "tmotor_mn3508_kv380",
        "propeller_id": "tmotor_p15x5_cf",
        "esc_id": "generic_esc_20a",
        "battery_id": "generic_6s_lipo_16000mah",
        "wiring_id": "silicone_awg12_bus",
        "wiring_length_m": 0.5,
        "sensor_ids": ["icm42688p_imu"],
        "frame_parts": [
            {"name": "center_hub", "material_id": "alu_6061_t6", "shape": "box", "dimensions_m": [0.2, 0.2, 0.01], "position_m": [0.0, 0.0, 0.0]}
        ],
    }
    quad_out = build_multirotor_layout_and_bom(quad_spec, library)
    assert quad_out["n_rotors"] == 4
    mp = quad_out["mass_properties"]

    # Analytic hand calculation:
    # hub mass = 0.2*0.2*0.01 * 2700 = 1.08 kg
    # per rotor: motor 0.103 + prop 0.019 = 0.122 kg at r=0.3; esc 0.03 kg at r=0.15
    # battery = 1.55 kg at [0,0,0]; wiring = 0.042*0.5 = 0.021 kg at [0,0,0]; sensor = 0.002 kg at [0,0,0.02]
    expected_mass = 1.08 + 4 * (0.103 + 0.019 + 0.03) + 1.55 + 0.021 + 0.002
    assert mp["mass_kg"] == pytest.approx(expected_mass, rel=1e-12)
    assert mp["cog_m"][0] == pytest.approx(0.0, abs=1e-12)
    assert mp["cog_m"][1] == pytest.approx(0.0, abs=1e-12)
    assert mp["cog_m"][2] == pytest.approx(0.002 * 0.02 / expected_mass, rel=1e-12)

    # Analytic Izz: hub (1.08/12*(0.04+0.04) = 0.0072) + 2*0.122*0.3^2 (X) + 2*0.122*0.3^2 (Y) + 4*0.03*0.15^2
    expected_izz = (1.08 / 12.0) * (0.2**2 + 0.2**2) + 4 * 0.122 * (0.3**2) + 4 * 0.03 * (0.15**2)
    assert mp["inertia_about_cog_kg_m2"][2][2] == pytest.approx(expected_izz, rel=1e-10)

    # 2. Hexacopter (6 rotors) updates BOM quantities and total mass
    hex_rotors = [
        {"position_m": [0.4 * np.cos(k * np.pi / 3.0), 0.4 * np.sin(k * np.pi / 3.0), 0.0], "spin_direction": 1 if k % 2 == 0 else -1}
        for k in range(6)
    ]
    hex_spec = {**quad_spec, "rotors": hex_rotors, "battery_position_m": [0.05, 0.0, -0.04]}
    hex_out = build_multirotor_layout_and_bom(hex_spec, library)
    assert hex_out["n_rotors"] == 6
    assert hex_out["mass_properties"]["mass_kg"] > quad_out["mass_properties"]["mass_kg"]
    assert hex_out["mass_properties"]["cog_m"][0] > 0.0
    motor_bom = next(b for b in hex_out["bom"] if b["kind"] == "motor")
    assert motor_bom["quantity"] == 6
    assert "generic_6s_lipo_16000mah" in hex_out["unverified_bom_items"]


def test_layout_bom_worker_cli_and_missing_density_refusal(tmp_path):
    good_spec = {
        "rotors": [
            {"position_m": [0.25, 0.25, 0.0], "spin_direction": 1},
            {"position_m": [-0.25, 0.25, 0.0], "spin_direction": -1},
            {"position_m": [-0.25, -0.25, 0.0], "spin_direction": 1},
            {"position_m": [0.25, -0.25, 0.0], "spin_direction": -1},
        ],
        "motor_id": "tmotor_mn3508_kv380",
        "propeller_id": "tmotor_p15x5_cf",
        "esc_id": "generic_esc_20a",
        "battery_id": "generic_6s_lipo_16000mah",
        "frame_parts": [
            {"name": "frame", "material_id": "cfrp_quasi_iso", "shape": "box", "dimensions_m": [0.2, 0.2, 0.01], "position_m": [0.0, 0.0, 0.0]}
        ],
    }
    in_good = tmp_path / "good.json"
    out_good = tmp_path / "good_out.json"
    in_good.write_text(json.dumps(good_spec), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(LAB_PROJECT), "layout-bom", str(in_good), str(out_good)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    res = json.loads(out_good.read_text(encoding="utf-8"))
    assert res["n_rotors"] == 4
    assert res["physical_validation_status"] == "unvalidated"

    # Missing density -> fail closed
    bad_no_density = {
        **good_spec,
        "frame_parts": [{"name": "unknown_plate", "shape": "box", "dimensions_m": [0.2, 0.2, 0.01], "position_m": [0.0, 0.0, 0.0]}],
    }
    in_bad = tmp_path / "bad_density.json"
    out_bad = tmp_path / "bad_out.json"
    err_bad = tmp_path / "bad_err.json"
    in_bad.write_text(json.dumps(bad_no_density), encoding="utf-8")
    proc_bad = subprocess.run(
        [sys.executable, str(LAB_PROJECT), "layout-bom", str(in_bad), str(out_bad), "--error-output", str(err_bad)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc_bad.returncode == 2
    assert "density" in json.loads(err_bad.read_text(encoding="utf-8"))["error"].lower()

    # Missing density source -> fail closed
    bad_no_src = {
        **good_spec,
        "frame_parts": [{"name": "unsourced_plate", "density_kg_m3": 1500.0, "shape": "box", "dimensions_m": [0.2, 0.2, 0.01], "position_m": [0.0, 0.0, 0.0]}],
    }
    with pytest.raises(ValueError, match="density source is missing"):
        build_multirotor_layout_and_bom(bad_no_src, ComponentLibrary(DATA_COMPONENTS))


def test_desktop_ui_wires_layout_bom_and_mass_controls():
    main_gd = (ROOT / "apps" / "desktop" / "main.gd").read_text(encoding="utf-8")
    for sym in ("_open_layout_editor", "_apply_layout_bom", "layout-bom", "Layout / BOM"):
        assert sym in main_gd
