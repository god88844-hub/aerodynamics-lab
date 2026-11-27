"""P0B-006: Section/polar and lifting-line aerodynamic models, Re/Mach/AoA support & failure guards."""

from __future__ import annotations

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.airfoil_polars import generate_airfoil_polar
from physics.aerodynamics.fixed_wing import solve_lifting_line_wing


def test_p0b_006_reynolds_polar_and_signed_lifting_line():
    polar_low = generate_airfoil_polar("2412", reynolds=8.0e4)
    polar_high = generate_airfoil_polar("2412", reynolds=8.0e5)
    assert polar_low["cd_min"] > polar_high["cd_min"]
    assert polar_high["physical_validation_status"] == "UNVALIDATED"

    sym_wing = ParametricWingSpec(name="Sym0012", wingspan_m=1.6, root_chord_m=0.2, tip_chord_m=0.2, twist_tip_deg=0.0, airfoil_code="0012")
    pos = solve_lifting_line_wing(sym_wing, alpha_deg=5.0, airspeed_m_s=18.0)
    neg = solve_lifting_line_wing(sym_wing, alpha_deg=-5.0, airspeed_m_s=18.0)
    assert pos["lift_n"] > 0.0
    assert neg["lift_n"] == pytest.approx(-pos["lift_n"], rel=1e-6)
    assert pos["drag_n"] > 0.0 and neg["drag_n"] > 0.0


def test_p0b_006_unsupported_mach_reynolds_and_stall_rejected():
    wing = ParametricWingSpec(name="LimitWing", wingspan_m=1.5, root_chord_m=0.2, tip_chord_m=0.2)
    with pytest.raises(ValueError, match="Compressible flow regime unsupported"):
        solve_lifting_line_wing(wing, alpha_deg=3.0, airspeed_m_s=150.0)
    with pytest.raises(ValueError, match="Post-stall angle of attack"):
        solve_lifting_line_wing(wing, alpha_deg=18.0, airspeed_m_s=18.0)
    with pytest.raises(ValueError, match="Reynolds number"):
        generate_airfoil_polar("2412", reynolds=5.0e3)
