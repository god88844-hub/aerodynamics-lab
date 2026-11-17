"""Synthetic M29.7 hard margins are not physical measurement or flight evidence."""
from copy import deepcopy
import pytest

from physics.validation.decision_hard_margins import audit_hard_bound_decision_margins


def decision(name, *, direction="exceed_max", predicted=10., threshold=11.):
    return {
        "decision_id": name,
        "channel": "voltage_v",
        "metric_unit": "V",
        "failure_direction": direction,
        "predicted_value": predicted,
        "failure_limit": threshold,
        "threshold_source": "synthetic and not manufacturer rated",
        "prediction_source": "unverified synthetic design calculation",
        "model_form_hard_bound": .1,
        "numerical_hard_bound": .1,
        "input_parameter_hard_bound": .1,
        "geometry_hard_bound": .1,
        "measurement_hard_bound": .1,
    }


def fixture():
    return {
        "frozen_model_git_sha": "a"*40,
        "frozen_protocol_sha256": "b"*64,
        "design_name": "synthetic_quad",
        "hard_bound_source": "hypothetical hard enclosures, not physically proven",
        "frozen_scenario_report": {
            "status": "OPERATOR_FROZEN_SCENARIO_AUDIT_CONSISTENT_UNVERIFIED",
            "reported_software_consistency_passed": True,
            "snapshot_sha256": "c"*64,
            "snapshot": {
                "model_git_sha": "a"*40,
                "design_name": "synthetic_quad",
                "selected_channel": "voltage_v",
            },
        },
        "critical_decisions": [
            decision("high_terminal_voltage"),
            decision("low_terminal_voltage", direction="fall_below_min", threshold=9.),
        ],
    }


def audit(req=None):
    return audit_hard_bound_decision_margins(**(fixture() if req is None else req))


def test_nominal_hard_margins_pass_without_claiming_physical_validation():
    req = fixture()
    original = deepcopy(req)
    out = audit(req)
    assert req == original
    assert out["status"] == "OPERATOR_HARD_MARGIN_CONSISTENT_BOUNDS_UNVERIFIED"
    assert out["all_declared_hard_margin_gates_passed"]
    assert out["declared_decision_count"] == 2
    assert len(out["canonical_hard_margin_report_sha256"]) == 64
    for row in out["decisions"]:
        assert row["combined_worst_case_hard_bound"] == pytest.approx(.5)
        assert row["remaining_conservative_hard_margin"] == pytest.approx(.5)
    assert not out["model_form_hard_error_independently_validated"]
    assert not out["complete_physical_failure_modes_covered"]
    assert not out["future_failure_probability_established"]
    assert not out["manufacturing_or_flight_release_authorized"]


def test_one_insufficient_margin_blocks_all_reported_decisions():
    req = fixture()
    req["critical_decisions"][0]["failure_limit"] = 10.4
    out = audit(req)
    assert out["status"] == "OPERATOR_HARD_MARGIN_GATE_BLOCKED"
    assert out["decisions"][0]["remaining_conservative_hard_margin"] < 0


def test_exactly_touching_failure_boundary_does_not_pass():
    req = fixture()
    req["critical_decisions"][0]["failure_limit"] = 10.5
    assert not audit(req)["all_declared_hard_margin_gates_passed"]


def test_failure_in_previous_cross_domain_gates_blocks_release():
    req = fixture()
    req["frozen_scenario_report"]["reported_software_consistency_passed"] = False
    assert audit(req)["status"] == "OPERATOR_HARD_MARGIN_GATE_BLOCKED"


def test_foreign_design_or_model_identity_rejected():
    req = fixture()
    req["frozen_scenario_report"]["snapshot"]["design_name"] = "different"
    with pytest.raises(ValueError, match="identity mismatch"):
        audit(req)
    req = fixture()
    req["frozen_scenario_report"]["snapshot"]["model_git_sha"] = "d"*40
    with pytest.raises(ValueError, match="identity mismatch"):
        audit(req)


def test_duplicate_decision_or_unrelated_channel_rejected():
    req = fixture()
    req["critical_decisions"][1]["decision_id"] = "high_terminal_voltage"
    with pytest.raises(ValueError, match="duplicate decision"):
        audit(req)
    req = fixture()
    req["critical_decisions"][0]["channel"] = "current_a"
    with pytest.raises(ValueError, match="match frozen scenario"):
        audit(req)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, 10**1000])
def test_bad_uncertainty_budget_cannot_produce_positive_margin(value):
    req = fixture()
    req["critical_decisions"][0]["model_form_hard_bound"] = value
    with pytest.raises(ValueError, match="finite"):
        audit(req)


def test_sum_overflow_refused_and_not_assumed_to_be_a_huge_margin():
    req = fixture()
    for name in (
        "model_form_hard_bound", "numerical_hard_bound",
        "input_parameter_hard_bound", "geometry_hard_bound",
        "measurement_hard_bound",
    ):
        req["critical_decisions"][0][name] = 1e308
    with pytest.raises(ValueError, match="overflow"):
        audit(req)


def test_unknown_claim_to_physical_approval_is_disallowed():
    req = fixture()
    req["critical_decisions"][0]["physically_validated"] = True
    with pytest.raises(ValueError, match="exact"):
        audit(req)


def test_input_decision_order_does_not_change_digest():
    req = fixture()
    first = audit(req)
    req["critical_decisions"].reverse()
    second = audit(req)
    assert first["canonical_hard_margin_report_sha256"] == second["canonical_hard_margin_report_sha256"]
