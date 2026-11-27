"""P0B-011: Fixed-wing numerical convergence, geometry perturbation, trim, and frame consistency."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import compute_fixed_wing_cruise_trim, verify_fixed_wing_convergence
from physics.aerodynamics.sixdof_fixed_wing import build_derivatives_from_wing, simulate_6dof_fixed_wing

ROOT = Path(__file__).resolve().parents[2]


def test_p0b_011_convergence_perturbation_and_6dof_reproducibility(tmp_path):
    wing = ParametricWingSpec(name="VerifyWing", wingspan_m=1.9, root_chord_m=0.26, tip_chord_m=0.14)
    conv = verify_fixed_wing_convergence(wing, alpha_deg=4.0, airspeed_m_s=18.0)
    assert conv["refinement_monotone"] is True
    assert conv["span_sensitivity_ld_delta"] > 0.0

    trim = compute_fixed_wing_cruise_trim(wing, mass_kg=2.0, airspeed_m_s=18.0)
    assert trim["trim_feasible"] is True

    derivs = build_derivatives_from_wing(wing)
    direct = simulate_6dof_fixed_wing(aero=derivs, mass_kg=2.2, thrust_n=3.5, duration_s=1.0, dt_s=0.01)

    in_path = tmp_path / "sixdof_in.json"
    out_path = tmp_path / "sixdof_out.json"
    in_path.write_text(json.dumps({"wingspan_m": 1.9, "root_chord_m": 0.26, "tip_chord_m": 0.14, "mass_kg": 2.2, "thrust_n": 3.5, "duration_s": 1.0}), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "6dof-fixed-wing", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    cli_6dof = json.loads(out_path.read_text(encoding="utf-8"))
    assert cli_6dof["final_position_m"][0] == pytest.approx(direct["final_position_m"][0], abs=1e-4)
