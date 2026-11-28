"""Exhaustive End-to-End Feature Test: All Native Presets, All CLI Worker Commands, All CAD Part Kinds."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
NATIVE_EXE = ROOT / "apps" / "native" / "build" / "AerodynamicsLab.exe"


def test_all_python_worker_cli_commands_succeed(tmp_path: Path) -> None:
    out_draw = tmp_path / "draw"
    out_part = tmp_path / "part"
    out_draw.mkdir()
    out_part.mkdir()

    base_proj = {
        "name": "FeatureSweepQuad",
        "aircraft_family": "multirotor",
        "mass_kg": 3.1,
        "wingspan_m": 1.65,
        "root_chord_m": 0.28,
        "tip_chord_m": 0.16,
        "airfoil_code": "2412",
        "motor_id": "tmotor_mn3508_kv380",
        "propeller_id": "tmotor_p15x5_cf",
        "esc_id": "generic_esc_20a",
        "battery_id": "generic_6s_lipo_16000mah",
        "rain_mm_h": 15.0,
        "oat_c": -3.0,
        "frame_parts": [
            {"name": "center_plate", "material_id": "cfrp_quasi_iso", "dimensions_m": [0.14, 0.16, 0.02], "shape": "box", "position_m": [0.0, 0.0, 0.0]}
        ],
        "rotors": [
            {"position_m": [0.21, 0.21, 0.015], "spin_direction": 1},
            {"position_m": [-0.21, 0.21, 0.015], "spin_direction": -1},
            {"position_m": [-0.21, -0.21, 0.015], "spin_direction": 1},
            {"position_m": [0.21, -0.21, 0.015], "spin_direction": -1},
        ],
    }

    commands = [
        ("fixed-wing-sim", base_proj),
        ("layout-bom", base_proj),
        ("6dof-fixed-wing", base_proj),
        ("vtol-transition", base_proj),
        ("autorotation-sim", base_proj),
        ("adverse-weather", base_proj),
        ("bounded-sweep", {}),
        ("phase1-eval", {}),
        ("failure-atlas", {}),
        (
            "load-powerpack",
            {
                "component_id": "ep_check_4s",
                "cells_series": 4,
                "capacity_ah": 5.0,
                "internal_resistance_ohm": 0.014,
                "mass_kg": 0.48,
                "max_continuous_current_a": 95.0,
                "cutoff_cell_voltage_v": 3.25,
                "max_temperature_c": 65.0,
                "ocv_curve": [{"soc_pct": 0.0, "cell_voltage_v": 3.25}, {"soc_pct": 100.0, "cell_voltage_v": 4.20}],
                "validation_origin": "electrophysics_lab_v1",
            },
        ),
        (
            "export-drawing",
            {
                "name": "SweepWing",
                "wingspan_m": 1.65,
                "root_chord_m": 0.28,
                "tip_chord_m": 0.16,
                "airfoil_code": "2412",
                "svg_path": str(out_draw / "w.svg"),
                "dxf_path": str(out_draw / "w.dxf"),
            },
        ),
        (
            "build-custom-part",
            {
                "part_name": "PropTest",
                "sketch_kind": "custom_propeller",
                "width_m": 0.048,
                "length_m": 0.24,
                "thickness_m": 0.012,
                "hole_radius_m": 0.008,
                "revolve_360": False,
                "circular_pattern_count": 2,
                "density_kg_m3": 1580.0,
                "density_source": "builtin_material_library",
                "airfoil_code": "2412",
                "export_dir": str(out_part),
            },
        ),
    ]
    for cmd, payload in commands:
        inf = tmp_path / f"{cmd}_in.json"
        outf = tmp_path / f"{cmd}_out.json"
        inf.write_text(json.dumps(payload), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "lab_project.py"), cmd, str(inf), str(outf)], capture_output=True, text=True)
        assert proc.returncode == 0, f"{cmd} failed: {proc.stderr}"
        assert outf.is_file()


@pytest.mark.skipif(not NATIVE_EXE.is_file(), reason="Native binary not built in headless environment")
def test_native_exe_renders_every_preset_cleanly(tmp_path: Path) -> None:
    presets = [
        ("multirotor", []),
        ("fixed-wing", ["--cp-view"]),
        ("helicopter", []),
        ("vtol", []),
        ("seaplane", []),
        ("jet", []),
        ("insect", ["--cp-view"]),
        ("morphing", ["--four-view"]),
        ("cargo", ["--rc-hud"]),
        ("tailsitter", []),
        ("flying-wing", []),
        ("part", []),
    ]
    for preset, flags in presets:
        png = tmp_path / f"{preset}.png"
        proc = subprocess.run(
            [str(NATIVE_EXE), "--smoke-test", "--preset", preset, "--screenshot", str(png), *flags],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, f"preset {preset} failed: {proc.stderr}"
        assert png.is_file() and png.stat().st_size > 10_000
