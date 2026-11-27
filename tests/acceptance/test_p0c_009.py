"""P0C-009: Geometry-dependent structural stress, Euler-Bernoulli modal vibration, and screening disclaimer."""

from __future__ import annotations

import pytest

from physics.aerodynamics.rotorcraft_vtol import run_structural_modal_screening


def test_p0c_009_modal_and_structural_screening():
    res = run_structural_modal_screening(boom_length_m=0.55, tip_load_n=20.0)
    assert res["mode_2_hz"] > res["mode_1_hz"] > 10.0
    assert res["yield_safety_factor"] > 1.5
    assert res["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert res["qualification_disclaimer"] == "SCREENING_ONLY_NOT_STRENGTH_QUALIFICATION"

    overloaded = run_structural_modal_screening(boom_length_m=1.2, tip_load_n=120.0)
    assert overloaded["verdict"] == "FAIL"

    with pytest.raises(ValueError, match="must be positive"):
        run_structural_modal_screening(youngs_modulus_pa=-1.0)
