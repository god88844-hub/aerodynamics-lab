"""M29.5 synthetic three-grid samples, not verified running solver or hardware."""
from copy import deepcopy

import pytest
from physics.validation.three_grid_convergence import audit_three_resolution_convergence


def fixture():
    return {
        "frozen_model_git_sha": "a"*40, "channel": "voltage_v",
        "expected_solver_order": 2, "coarse_step_s": .08,
        "fixed_time_step_ratio": 2,
        "maximum_estimated_fine_grid_error": .005,
        "maximum_relative_order_ratio_error": .1,
        "solver_source": "hypothetical second-order solver not independently executed",
        "convergence_protocol_source": "synthetic three-grid comparison",
        "samples": [
            {"sample_id":f"s{i}", "time_s":i*.1,
             "coarse":10.0 + .05, "medium":10.0 + .0125, "fine":10.0 + .003125}
            for i in range(5)
        ],
    }


def test_ideal_refinement_ratio_passes_analytically_but_not_physically():
    req = fixture()
    original = deepcopy(req)
    r = audit_three_resolution_convergence(**req)
    assert req == original
    assert r["status"] == "REPORTED_THREE_GRID_CONVERGENCE_CONSISTENT_UNVERIFIED"
    assert r["expected_difference_ratio"] == 4
    assert r["analytical_convergence_gate_passed"]
    assert r["maximum_conditional_fine_grid_error_estimate"] == pytest.approx(.003125)
    assert not r["three_grid_runs_independently_authenticated"]
    assert not r["asymptotic_regime_physically_proven"]
    assert not r["real_world_prediction_accuracy_established"]
    assert not r["flight_release_authorized"]


def test_false_convergence_with_zero_delta_is_inconclusive():
    req = fixture()
    for row in req["samples"]:
        row["coarse"] = row["medium"] = row["fine"]
    r = audit_three_resolution_convergence(**req)
    assert not r["analytical_convergence_gate_passed"]
    assert r["samples_failed_or_inconclusive"] == 5


def test_wrong_order_ratio_does_not_pass_from_tiny_absolute_delta():
    req = fixture()
    for row in req["samples"]:
        row["coarse"] = 10.0001
        row["medium"] = 10.00005
        row["fine"] = 10.000025
    r = audit_three_resolution_convergence(**req)
    assert r["status"] == "REPORTED_THREE_GRID_CONVERGENCE_NOT_ESTABLISHED"
    assert not r["analytical_convergence_gate_passed"]


def test_expected_order_can_match_but_residual_bound_is_too_large():
    req = fixture()
    req["maximum_estimated_fine_grid_error"] = .001
    assert not audit_three_resolution_convergence(**req)["analytical_convergence_gate_passed"]


def test_unknown_or_invalid_step_ratio_fails():
    req = fixture()
    req["fixed_time_step_ratio"] = 1
    with pytest.raises(ValueError, match="ratio"):
        audit_three_resolution_convergence(**req)


@pytest.mark.parametrize("key,bad", [
    ("fine", float("nan")), ("coarse", float("inf")),
    ("medium", True), ("time_s", -1), ("fine", 10**1000),
])
def test_invalid_sample_data_cannot_pass(key,bad):
    req = fixture()
    req["samples"][0][key] = bad
    with pytest.raises(ValueError, match="finite|positive|nonnegative"):
        audit_three_resolution_convergence(**req)


def test_duplicate_time_and_missing_grid_level_refused():
    req = fixture()
    req["samples"][1]["time_s"] = 0
    with pytest.raises(ValueError, match="strictly increase"):
        audit_three_resolution_convergence(**req)
    req = fixture()
    del req["samples"][1]["medium"]
    with pytest.raises(ValueError, match="exact"):
        audit_three_resolution_convergence(**req)


def test_very_large_finite_grid_differences_overflow_fail_closed():
    req = fixture()
    req["samples"][0]["coarse"] = 1e308
    req["samples"][0]["medium"] = -1e308
    with pytest.raises(ValueError, match="overflow"):
        audit_three_resolution_convergence(**req)
