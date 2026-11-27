"""P0C-011: Structural-thermal-aerodynamic coupling, datum/clock consistency, and missing material refusal."""

from __future__ import annotations

import pytest

from physics.aerodynamics.rotorcraft_vtol import run_coupled_aero_thermo_structural


def test_p0c_011_coupled_aero_thermo_structural_pass_and_refusal():
    coupled = run_coupled_aero_thermo_structural(vtol_architecture="tilt_rotor", max_tip_deflection_mm=25.0)
    assert coupled["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert coupled["boom_tip_deflection_mm"] > 0.0
    assert coupled["mode_1_hz"] > 10.0

    flex_fail = run_coupled_aero_thermo_structural(vtol_architecture="lift_plus_cruise", max_tip_deflection_mm=0.2)
    assert flex_fail["verdict"] == "FAIL"

    with pytest.raises(ValueError, match="must be positive"):
        run_coupled_aero_thermo_structural(youngs_modulus_pa=0.0)
