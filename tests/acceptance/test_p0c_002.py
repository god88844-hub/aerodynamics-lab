"""P0C-002: Qualified rotor BEMT + Pitt-Peters dynamic inflow convergence and tip-Mach/VRS envelopes."""

from __future__ import annotations

import pytest

from physics.aerodynamics.pitt_peters_inflow import run_pitt_peters_step_response
from physics.aerodynamics.rotorcraft_vtol import solve_helicopter_bemt_rotor, verify_rotorcraft_convergence_and_inflow


def test_p0c_002_bemt_pitt_peters_convergence_and_limits():
    conv = verify_rotorcraft_convergence_and_inflow()
    assert conv["refinement_monotone"] is True
    assert conv["pitt_peters_final_lambda0"] > 0.0

    inflow = run_pitt_peters_step_response(ct_step=0.008, omega_rad_s=170.0, duration_s=0.15)
    assert len(inflow["history"]) > 10

    with pytest.raises(ValueError, match="tip Mach"):
        solve_helicopter_bemt_rotor(radius_m=0.72, root_cutout_m=0.1, chord_m=0.055, n_blades=2, omega_rad_s=400.0, collective_deg=8.0)

    with pytest.raises(ValueError, match="vortex-ring"):
        solve_helicopter_bemt_rotor(radius_m=0.72, root_cutout_m=0.1, chord_m=0.055, n_blades=2, omega_rad_s=170.0, collective_deg=8.0, climb_speed_m_s=-10.0)
