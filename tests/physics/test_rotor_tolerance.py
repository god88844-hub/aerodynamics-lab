"""M28.3 synthetic algebraic assertions, never real assembly clearance evidence."""
from pathlib import Path
import copy

import pytest
from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_tolerance import evaluate_bounded_rotor_clearance

ROOT = Path(__file__).resolve().parents[2]


def design():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def run(*, center=0.01, diameter=0.005, minimum=0.02):
    d = design()
    snapshot = copy.deepcopy(d.model_dump())
    r = evaluate_bounded_rotor_clearance(
        d, [0.381] * 4, [center] * 4, [diameter] * 4,
        geometry_source="unmeasured synthetic rotor model",
        hard_bound_source="synthetic input bounds, not experimentally proven",
        minimum_declared_tip_clearance_m=minimum,
    )
    assert d.model_dump() == snapshot
    assert not r["source_hard_bounds_independently_authenticated"]
    assert not r["actual_3d_interference_validated"]
    assert not r["flightworthiness_established"]
    return r


def test_bounded_separation_subtracts_position_and_diameter_errors():
    result = run()
    assert result["status"] == "ANALYTICAL_HARD_BOUND_PROJECTED_CLEARANCE_ONLY"
    assert result["analytical_screen_passed"] is True
    assert result["minimum_worst_case_projected_tip_clearance_m"] == pytest.approx(0.094)
    pair = min(result["pairs"], key=lambda p: p["worst_case_lower_projected_tip_clearance_m"])
    assert pair["nominal_projected_tip_clearance_m"] == pytest.approx(0.119)
    assert pair["declared_xy_position_error_sum_m"] == pytest.approx(0.02)


def test_nominal_positive_can_fail_under_declared_bounds():
    r = run(center=0.06, diameter=0.01)
    assert r["status"] == "HARD_BOUND_PROJECTED_CLEARANCE_NOT_ESTABLISHED"
    assert r["analytical_screen_passed"] is False


def test_zero_bounds_preserve_nominal_geometry_screen():
    r = run(center=0, diameter=0)
    assert r["minimum_worst_case_projected_tip_clearance_m"] == pytest.approx(0.119)
    assert r["analytical_screen_passed"] is True


def test_contact_is_not_pass_even_with_zero_user_threshold():
    r = run(center=0.1, diameter=0, minimum=0)
    assert not r["analytical_screen_passed"]


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, None, 10**1000])
def test_unsupported_hard_bounds_fail_closed(bad):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        run(center=bad)


def test_bound_count_and_source_are_required():
    d = design()
    opts = dict(geometry_source="synthetic", hard_bound_source="synthetic", minimum_declared_tip_clearance_m=.02)
    with pytest.raises(ValueError, match="one bound per rotor"):
        evaluate_bounded_rotor_clearance(d, [.381] * 4, [.01], [.005] * 4, **opts)
    opts["hard_bound_source"] = ""
    with pytest.raises(ValueError, match="hard_bound_source"):
        evaluate_bounded_rotor_clearance(d, [.381] * 4, [.01] * 4, [.005] * 4, **opts)


def test_overflowed_cumulative_bounds_rejected():
    with pytest.raises(ValueError, match="overflow"):
        run(center=1e308, diameter=1e308)


def test_tight_requirement_can_make_analytical_clearance_inadequate():
    r = run(minimum=.1)
    assert r["status"] == "HARD_BOUND_PROJECTED_CLEARANCE_NOT_ESTABLISHED"
    assert not r["analytical_screen_passed"]
