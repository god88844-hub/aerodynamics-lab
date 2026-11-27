"""P0C-004: Helicopter autorotation missions, flare recovery, RPM decay FAIL, and CLI reproducibility."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from physics.aerodynamics.rotorcraft_vtol import run_helicopter_autorotation_mission

ROOT = Path(__file__).resolve().parents[2]


def test_p0c_004_autorotation_flare_rpm_guard_and_cli_match(tmp_path):
    ok = run_helicopter_autorotation_mission(flare_altitude_m=8.0, min_safe_rpm=950.0)
    assert ok["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert ok["aircraft_family"] == "helicopter"

    rpm_fail = run_helicopter_autorotation_mission(initial_rpm=1100.0, min_safe_rpm=1080.0, flare_altitude_m=2.0)
    assert rpm_fail["verdict"] == "FAIL"

    in_p = tmp_path / "auto_in.json"
    out_p = tmp_path / "auto_out.json"
    in_p.write_text(json.dumps({"flare_altitude_m": 8.0, "min_safe_rpm": 950.0}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "autorotation-sim", str(in_p), str(out_p)], check=True, cwd=ROOT)
    cli_res = json.loads(out_p.read_text(encoding="utf-8"))
    assert cli_res["touchdown_sink_m_s"] == pytest.approx(ok["touchdown_sink_m_s"], abs=1e-6)
