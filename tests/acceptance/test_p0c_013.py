"""P0C-013: Verify helicopter & VTOL coupled missions and preserve four-family regression checks."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import run_fixed_wing_mission
from physics.aerodynamics.rotorcraft_vtol import (
    run_coupled_electro_thermal_rotor_transient,
    run_coupled_aero_thermo_structural,
    run_helicopter_autorotation_mission,
    verify_rotorcraft_convergence_and_inflow,
)

ROOT = Path(__file__).resolve().parents[2]


def test_p0c_013_four_family_verification_and_vtol_cli_reproduction(tmp_path):
    assert verify_rotorcraft_convergence_and_inflow()["refinement_monotone"] is True
    assert run_helicopter_autorotation_mission(flare_altitude_m=8.0)["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert run_coupled_aero_thermo_structural(vtol_architecture="tilt_rotor")["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert run_coupled_electro_thermal_rotor_transient()["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    fw = run_fixed_wing_mission(ParametricWingSpec(name="FW-Check", wingspan_m=1.8, root_chord_m=0.26, tip_chord_m=0.14), mass_kg=2.0, duration_s=4.0)
    assert fw["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    in_p = tmp_path / "vtol_in.json"
    out_p = tmp_path / "vtol_out.json"
    in_p.write_text(json.dumps({"mass_kg": 3.0, "wing_area_m2": 0.45}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "vtol-transition", str(in_p), str(out_p)], check=True, cwd=ROOT)
    assert json.loads(out_p.read_text(encoding="utf-8"))["verdict"] == "NO_MODELED_LIMIT_BREACHED"
