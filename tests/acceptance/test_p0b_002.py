"""P0B-002: Author exact wings, airfoils, blades, lofts, analytic volume/mass fixtures, explicit unsupported rejection."""

from __future__ import annotations

import math

import pytest

from geometry.fixed_wing_cad import (
    ParametricWingSpec,
    compute_wing_geometry_properties,
    naca4_airfoil_coordinates,
)


def test_p0b_002_naca_wing_analytic_geometry_and_declared_density():
    coords = naca4_airfoil_coordinates("2412", n_points_per_surface=20)
    assert len(coords) == 39
    wing = ParametricWingSpec(
        name="ExactWing-2412",
        wingspan_m=2.0,
        root_chord_m=0.30,
        tip_chord_m=0.15,
        sweep_le_deg=6.0,
        dihedral_deg=2.5,
        twist_tip_deg=-2.0,
        airfoil_code="2412",
        material_density_kg_m3=120.0,
        density_source="PUBLISHED_FOAM_CORE",
    )
    props = compute_wing_geometry_properties(wing)
    assert props["planform_area_m2"] == pytest.approx(0.45)
    assert props["taper_ratio"] == pytest.approx(0.5)
    assert props["aspect_ratio"] == pytest.approx((2.0 * 2.0) / 0.45)
    lam = 0.5
    expected_mac = (2.0 / 3.0) * 0.30 * (1.0 + lam + lam * lam) / (1.0 + lam)
    assert props["mean_aerodynamic_chord_m"] == pytest.approx(expected_mac)
    assert math.isclose(props["mass_kg"], props["solid_volume_m3"] * 120.0, rel_tol=1e-9)
    assert props["physical_validation_status"] == "UNVALIDATED"


def test_p0b_002_unsupported_surfaces_rejected_explicitly():
    with pytest.raises(ValueError, match="4-digit NACA"):
        naca4_airfoil_coordinates("24125")
    with pytest.raises(ValueError, match="thickness ratio"):
        naca4_airfoil_coordinates("0000")
    with pytest.raises(ValueError, match="structural geometry range"):
        ParametricWingSpec(name="TooSwept", wingspan_m=1.2, root_chord_m=0.2, tip_chord_m=0.1, sweep_le_deg=82.0)
