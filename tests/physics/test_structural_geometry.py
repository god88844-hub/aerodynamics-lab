"""M10.6: static per-arm bending conservatism and failure semantics.

These are analytic model-verification tests; they are not physical validation
of clamps, fasteners, composite layups, or fatigue.
"""
import math
import numpy as np
import pytest

from physics.scenarios.runner import check_structure
from physics.structures.beam import (
    bending_stress_pa, check_arm, effective_arm_spans_m,
)
from physics.structures.materials import MaterialProps


@pytest.fixture
def material():
    return MaterialProps(
        id="test", name="test isotropic material", density_kg_m3=1000,
        youngs_modulus_pa=10e9, yield_strength_pa=100e6,
        ultimate_tensile_strength_pa=120e6, source="analytic test fixture",
        uncertainty_pct=0, notes="verification only",
    )


def test_diagonal_quad_geometry_uses_true_planar_radius():
    points = [(0.25, 0.25, 0.02), (-0.25, 0.25, 0.02),
              (-0.25, -0.25, 0.02), (0.25, -0.25, 0.02)]
    spans = effective_arm_spans_m(0.25, points)
    assert spans == pytest.approx([math.sqrt(2) * .25] * 4)


def test_overdeclared_span_remains_conservative():
    spans = effective_arm_spans_m(.6, [(.2, 0, 0), (0, -.1, .7)])
    assert spans == pytest.approx([.6, .6])


def test_z_offset_does_not_change_bending_lever():
    assert effective_arm_spans_m(.1, [(3, 4, 0)])[0] == pytest.approx(5)
    assert effective_arm_spans_m(.1, [(3, 4, 10)])[0] == pytest.approx(5)


def test_worst_rotor_selected_by_force_times_span_not_max_force(material):
    # Rotor 0 has lower force but longer arm (2 N * 2 m = 4 N m).
    # Rotor 1 has higher force but short arm (8 N * .2 m = 1.6 N m).
    lengths = effective_arm_spans_m(.2, [(2, 0, 0), (.2, 0, 0)])
    event, minimum = check_structure(
        np.array([2., 8.]), 1.0, lengths, .012, .010, material,
    )
    expected = check_arm(2, 2, .012, .010, material).margin
    assert minimum == pytest.approx(expected)
    assert minimum < check_arm(8, .2, .012, .010, material).margin
    if event is not None:
        assert "rotor 0" in event.message


def test_mismatch_does_not_report_optimistic_legacy_margin(material):
    span = effective_arm_spans_m(.25, [(.25, .25, 0)])
    _, minimum = check_structure(
        np.array([9.09]), 0.0, span, .012, .010, material,
    )
    old = check_arm(9.09, .25, .012, .010, material).margin
    assert minimum < old
    assert minimum == pytest.approx(
        material.yield_strength_pa /
        bending_stress_pa(9.09, math.sqrt(.125), .012, .010)
    )


def test_critical_yield_names_responsible_rotor(material):
    lengths = effective_arm_spans_m(.2, [(.2, 0, 0), (.8, 0, 0)])
    event, margin = check_structure(
        np.array([10., 10.]), 1.2, lengths, .005, .0045, material,
    )
    assert margin < 1.0
    assert event is not None
    assert event.kind == "structure_yield"
    assert event.critical and event.t_s == pytest.approx(1.2)
    assert "rotor 1" in event.message
    assert "0.8000 m" in event.message


@pytest.mark.parametrize("declared, locations", [
    (0, [(.2, 0, 0)]),
    (float("nan"), [(.2, 0, 0)]),
    (.2, [(0, 0, .1)]),
    (.2, [(float("nan"), 0, 0)]),
    (.2, []),
])
def test_invalid_structure_geometry_rejected(declared, locations):
    with pytest.raises(ValueError):
        effective_arm_spans_m(declared, locations)


@pytest.mark.parametrize("forces, spans", [
    ([1., 2.], [.3]),
    ([-1.], [.3]),
    ([float("nan")], [.3]),
    ([1.], [-.3]),
    ([], []),
])
def test_malformed_load_case_rejected(forces, spans, material):
    with pytest.raises(ValueError, match="matching finite"):
        check_structure(np.asarray(forces), 0.0, spans, .012, .010, material)
