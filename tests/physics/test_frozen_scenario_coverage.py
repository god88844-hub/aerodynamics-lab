"""M29.6 synthetic final scenario data consistency, never real-aircraft release."""
from copy import deepcopy

import pytest

from physics.validation.frozen_scenario_coverage import assess_frozen_scenario_coverage


def fixture():
    return {
        "frozen_model_git_sha": "a"*40,
        "design_name": "synthetic_quad",
        "selected_channel": "voltage_v",
        "intended_envelope_id": "unverified_test_case",
        "original_clock_report": {
            "frozen_model_git_sha": "a"*40,
            "channel": "voltage_v",
            "status": "ORIGINAL_CLOCK_BUDGETS_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED",
            "all_claimed_holdout_and_clock_gates_passed": True,
            "runs": [
                {"group_id": f"holdout_{i}", "analytical_clock_residual_gate_passed": True,
                 "worst_conservative_absolute_residual_upper": .17} for i in range(2)
            ],
        },
        "obstacle_inventory_report": {
            "status": "DECLARED_OBSTACLE_INVENTORY_SCREENED_ANALYTICALLY_ONLY",
            "declared_inventory_exactly_covered": True,
            "analytical_screen_passed": True,
            "declared_inventory_digest_sha256": "c"*64,
            "geometry_report": {"design_name": "synthetic_quad", "analytical_screen_passed": True},
        },
        "solver_convergence_report": {
            "model_git_sha": "a"*40, "channel": "voltage_v",
            "status": "REPORTED_THREE_GRID_CONVERGENCE_CONSISTENT_UNVERIFIED",
            "analytical_convergence_gate_passed": True,
        },
        "decision_coverage_report": {
            "status": "OPERATOR_DECISION_COVERAGE_CONSISTENT_UNVERIFIED",
            "reported_software_coverage_consistent": True,
            "metric_reports": [
                {"channel": "voltage_v", "reported_worst_hard_error": .2,
                 "inside_declared_operating_envelope": True,
                 "holdout_group_count": 2, "declared_numeric_gate_passed": True}
            ],
        },
    }


def test_consistent_synthetic_reports_still_forbid_release():
    req = fixture()
    old = deepcopy(req)
    out = assess_frozen_scenario_coverage(**req)
    assert req == old
    assert out["status"] == "OPERATOR_FROZEN_SCENARIO_AUDIT_CONSISTENT_UNVERIFIED"
    assert out["reported_software_consistency_passed"]
    assert len(out["snapshot_sha256"]) == 64
    assert not out["physical_source_attestation_verified"]
    assert not out["real_assembled_aircraft_geometry_authenticated"]
    assert not out["real_world_predictive_accuracy_validated"]
    assert not out["engineering_airworthiness_established"]
    assert not out["production_or_flight_release_authorized"]


def test_decision_report_must_not_understate_original_clock_bounded_error():
    req = fixture()
    req["decision_coverage_report"]["metric_reports"][0]["reported_worst_hard_error"] = .15
    with pytest.raises(ValueError, match="understates"):
        assess_frozen_scenario_coverage(**req)


def test_unknown_or_reused_holdout_group_rejected():
    req = fixture()
    req["original_clock_report"]["runs"][1]["group_id"] = "holdout_0"
    with pytest.raises(ValueError, match="duplicated"):
        assess_frozen_scenario_coverage(**req)


def test_failing_obstacle_inventory_blocks_even_when_clock_and_solver_pass():
    req = fixture()
    req["obstacle_inventory_report"]["analytical_screen_passed"] = False
    out = assess_frozen_scenario_coverage(**req)
    assert out["status"] == "OPERATOR_FROZEN_SCENARIO_AUDIT_BLOCKED"
    assert any("obstacle" in b for b in out["blockers"])


def test_solver_and_decision_gates_are_independent_blockers():
    req = fixture()
    req["solver_convergence_report"]["analytical_convergence_gate_passed"] = False
    assert not assess_frozen_scenario_coverage(**req)["reported_software_consistency_passed"]
    req = fixture()
    req["decision_coverage_report"]["metric_reports"][0]["holdout_group_count"] = 1
    assert not assess_frozen_scenario_coverage(**req)["reported_software_consistency_passed"]


def test_cross_domain_model_and_design_identity_mismatch_refused():
    req = fixture()
    req["solver_convergence_report"]["model_git_sha"] = "b"*40
    with pytest.raises(ValueError, match="model mismatch"):
        assess_frozen_scenario_coverage(**req)
    req = fixture()
    req["obstacle_inventory_report"]["geometry_report"]["design_name"] = "wrong_design"
    with pytest.raises(ValueError, match="design identity"):
        assess_frozen_scenario_coverage(**req)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, 10**1000])
def test_invalid_reported_residual_rejected(value):
    req = fixture()
    req["decision_coverage_report"]["metric_reports"][0]["reported_worst_hard_error"] = value
    with pytest.raises(ValueError, match="finite"):
        assess_frozen_scenario_coverage(**req)


def test_fake_physical_approval_flags_are_never_promoted():
    req = fixture()
    req["original_clock_report"]["physical_source_attestation_verified"] = True
    req["solver_convergence_report"]["real_world_prediction_accuracy_established"] = True
    req["obstacle_inventory_report"]["aircraft_flightworthiness_established"] = True
    out = assess_frozen_scenario_coverage(**req)
    assert not out["production_or_flight_release_authorized"]
