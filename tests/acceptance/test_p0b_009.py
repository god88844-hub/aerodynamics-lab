"""P0B-009: Fixed-wing takeoff, cruise, maneuver, landing mission & CLI/desktop reproduction."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import run_fixed_wing_mission

ROOT = Path(__file__).resolve().parents[2]


def test_p0b_009_takeoff_cruise_maneuver_landing_and_cli_reproduction(tmp_path):
    wing = ParametricWingSpec(name="MissionWing", wingspan_m=1.8, root_chord_m=0.28, tip_chord_m=0.16, airfoil_code="2412")
    direct = run_fixed_wing_mission(wing, mass_kg=2.2, duration_s=8.0, mission_profile="takeoff_cruise_landing")
    assert direct["status"] == "completed"
    assert direct["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert direct["phases_executed"] == ["takeoff", "cruise", "maneuver", "landing_approach"]

    in_path = tmp_path / "fw_in.json"
    out_path = tmp_path / "fw_out.json"
    in_path.write_text(json.dumps({"name": "MissionWing", "wingspan_m": 1.8, "root_chord_m": 0.28, "tip_chord_m": 0.16, "mass_kg": 2.2, "duration_s": 8.0}), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "fixed-wing-sim", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    cli_res = json.loads(out_path.read_text(encoding="utf-8"))["mission"]
    assert cli_res["range_m"] == pytest.approx(direct["range_m"], rel=1e-9)
    assert cli_res["final_airspeed_m_s"] == pytest.approx(direct["final_airspeed_m_s"], rel=1e-9)
