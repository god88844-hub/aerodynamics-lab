"""P0B-005: Geometry-to-aerodynamics loading, datum/polar hashes, and geometry perturbation sensitivity."""

from __future__ import annotations

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import solve_lifting_line_wing
from physics.aerodynamics.sixdof_fixed_wing import build_derivatives_from_wing


def test_p0b_005_geometry_to_aeroloads_datum_and_hash_provenance():
    wing = ParametricWingSpec(name="AeroWing", wingspan_m=1.8, root_chord_m=0.25, tip_chord_m=0.15, airfoil_code="2412")
    loads_cog = solve_lifting_line_wing(
        wing, alpha_deg=4.0, airspeed_m_s=18.0, use_reynolds_polar=True, moment_datum_m=(0.0, 0.0, 0.0), wing_attachment_m=(0.10, 0.0, 0.02)
    )
    loads_aft = solve_lifting_line_wing(
        wing, alpha_deg=4.0, airspeed_m_s=18.0, use_reynolds_polar=True, moment_datum_m=(0.0, 0.0, 0.0), wing_attachment_m=(-0.10, 0.0, 0.02)
    )
    assert len(loads_cog["geometry_sha256"]) == 64
    assert len(loads_cog["polar_sha256"]) == 64
    assert loads_cog["pitching_moment_about_datum_n_m"] > loads_aft["pitching_moment_about_datum_n_m"]

    wider = ParametricWingSpec(name="AeroWingWide", wingspan_m=2.4, root_chord_m=0.25, tip_chord_m=0.15, airfoil_code="2412")
    loads_wider = solve_lifting_line_wing(wider, alpha_deg=4.0, airspeed_m_s=18.0, use_reynolds_polar=True)
    assert loads_wider["geometry_sha256"] != loads_cog["geometry_sha256"]
    assert loads_wider["lift_to_drag"] > loads_cog["lift_to_drag"]

    d1 = build_derivatives_from_wing(wing)
    d2 = build_derivatives_from_wing(wider)
    assert d2.wingspan_m > d1.wingspan_m
    assert d2.k_induced < d1.k_induced
