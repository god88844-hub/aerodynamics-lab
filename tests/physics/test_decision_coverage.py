"""M29.4 synthetic, operator-declared decision gates; never flightworthiness."""
from copy import deepcopy

import pytest
from physics.validation.decision_coverage import assess_decision_metric_coverage


def fixture():
    return {
        "frozen_model_git_sha": "a"*40,
        "timeline_report": {
            "frozen_model_git_sha": "a"*40,
            "status": "DECLARED_SEQUENCE_CONSISTENT_UNAUTHENTICATED",
            "reported_temporal_order_consistent": True,
        },
        "rotor_sphere_report": {
            "status": "ANALYTICAL_ORIENTATION_INDEPENDENT_SPHERE_SEPARATION_ONLY",
            "analytical_screen_passed": True,
            "design_name": "synthetic_quad",
        },
        "prior_release_preflight": {
            "status": "REPORTED_SOFTWARE_GATES_CONSISTENT_EXTERNAL_VERIFICATION_REQUIRED",
            "software_preflight_consistency_operator_reported": True,
            "snapshot": {
                "frozen_model_git_sha": "a"*40,
                "geometry_design_name": "synthetic_quad",
            },
        },
        "critical_decisions": ["voltage_v", "altitude_m"],
        "declared_metric_reports": [
            {"channel": channel, "predeclared_max_hard_error": .5,
             "reported_worst_hard_error": .2, "holdout_group_count": 2,
             "inside_declared_operating_envelope": True,
             "measurement_source": "synthetic unverified reported measurement"}
            for channel in ["voltage_v", "altitude_m"]
        ],
    }


def test_all_claimed_gates_consistent_but_not_physically_validated():
    req = fixture()
    original = deepcopy(req)
    report = assess_decision_metric_coverage(**req)
    assert req == original
    assert report["status"] == "OPERATOR_DECISION_COVERAGE_CONSISTENT_UNVERIFIED"
    assert report["reported_software_coverage_consistent"]
    assert report["declared_critical_decision_count"] == 2
    assert not report["independent_physical_metric_coverage_authenticated"]
    assert not report["real_world_equivalence_demonstrated"]
    assert not report["design_airworthiness_established"]
    assert not report["production_or_flight_release_authorized"]


def test_unsatisfied_metric_must_fail_regardless_of_others():
    req = fixture()
    req["declared_metric_reports"][0]["reported_worst_hard_error"] = .7
    result = assess_decision_metric_coverage(**req)
    assert result["status"] == "OPERATOR_DECISION_COVERAGE_BLOCKED"
    assert any("voltage_v" in b for b in result["blockers"])


def test_outside_operating_envelope_and_insufficient_holdouts_block():
    req = fixture()
    req["declared_metric_reports"][0]["inside_declared_operating_envelope"] = False
    assert not assess_decision_metric_coverage(**req)["reported_software_coverage_consistent"]
    req = fixture()
    req["declared_metric_reports"][0]["holdout_group_count"] = 1
    assert not assess_decision_metric_coverage(**req)["reported_software_coverage_consistent"]


def test_failure_in_prior_screen_blocks_claimed_software_coverage():
    req = fixture()
    req["rotor_sphere_report"]["analytical_screen_passed"] = False
    assert not assess_decision_metric_coverage(**req)["reported_software_coverage_consistent"]
    req = fixture()
    req["timeline_report"]["status"] = "DECLARED_SEQUENCE_REJECTED"
    assert not assess_decision_metric_coverage(**req)["reported_software_coverage_consistent"]


def test_frozen_model_and_design_must_match_across_reports():
    req = fixture()
    req["prior_release_preflight"]["snapshot"]["frozen_model_git_sha"] = "b"*40
    with pytest.raises(ValueError, match="snapshot model"):
        assess_decision_metric_coverage(**req)
    req = fixture()
    req["rotor_sphere_report"]["design_name"] = "other_design"
    with pytest.raises(ValueError, match="design identity"):
        assess_decision_metric_coverage(**req)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True, 10**999])
def test_bad_frozen_or_reported_numeric_bounds_refused(bad):
    req = fixture()
    req["declared_metric_reports"][0]["reported_worst_hard_error"] = bad
    with pytest.raises(ValueError, match="finite"):
        assess_decision_metric_coverage(**req)


def test_missing_decision_and_duplicate_reports_are_errors():
    req = fixture()
    req["declared_metric_reports"].pop()
    with pytest.raises(ValueError, match="exactly one metric"):
        assess_decision_metric_coverage(**req)
    req = fixture()
    req["declared_metric_reports"][1]["channel"] = "voltage_v"
    with pytest.raises(ValueError, match="duplicate"):
        assess_decision_metric_coverage(**req)


def test_input_order_cannot_change_report_digest():
    req = fixture()
    result = assess_decision_metric_coverage(**req)
    req["critical_decisions"].reverse()
    req["declared_metric_reports"].reverse()
    second = assess_decision_metric_coverage(**req)
    assert result["canonical_report_sha256"] == second["canonical_report_sha256"]


def test_forged_real_world_flag_cannot_authorize_release():
    req = fixture()
    req["prior_release_preflight"]["release_authorized"] = True
    req["timeline_report"]["actual_physical_validation_established"] = True
    report = assess_decision_metric_coverage(**req)
    assert report["status"] == "OPERATOR_DECISION_COVERAGE_CONSISTENT_UNVERIFIED"
    assert not report["production_or_flight_release_authorized"]
