"""P0C-008: Installed rotor ground effect (Cheeseman-Bennett) and coaxial wake interference."""

from __future__ import annotations

import pytest

from physics.aerodynamics.rotorcraft_vtol import evaluate_coaxial_and_ground_interaction, solve_helicopter_bemt_rotor


def test_p0c_008_installed_ige_and_coaxial_interaction():
    res = evaluate_coaxial_and_ground_interaction(radius_m=0.72, altitude_agl_m=0.80, axial_spacing_ratio=0.20)
    assert res["ige_thrust_n"] > res["oge_thrust_n"]
    assert res["ige_gain_ratio"] > 1.04
    assert 0.70 < res["coaxial_interference_efficiency"] < 0.90
    assert res["physical_validation_status"] == "UNVALIDATED"

    with pytest.raises(ValueError, match="Cheeseman-Bennett"):
        solve_helicopter_bemt_rotor(radius_m=0.72, root_cutout_m=0.1, chord_m=0.055, n_blades=2, omega_rad_s=170.0, collective_deg=8.0, altitude_agl_m=0.15)
    with pytest.raises(ValueError, match="Coaxial rotor spacing"):
        evaluate_coaxial_and_ground_interaction(axial_spacing_ratio=0.02)
