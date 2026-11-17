"""M27.1 synthetic analytical diagnostics; never physical validation evidence."""
from copy import deepcopy

import pytest

from physics.validation.holdout_intervals import audit_heldout_intervals


def campaign():
    def run(name, group):
        return {
            "run_id": name, "group_id": group, "source_sha256": ("a" if name == "run-A" else "d") * 64,
            "dataset_kind": "reported_physical_measurements",
            "hardware_match": True, "unused_for_calibration": True,
            "samples": [
                {"sample_id": f"{name}-{i}", "prediction": 10.0,
                 "lower": 9.0, "upper": 11.0, "observed": 10.2,
                 "measurement_hard_bound": 0.2}
                for i in range(5)
            ],
        }
    return dict(
        frozen_model_git_sha="b" * 40,
        frozen_protocol_sha256="c" * 64,
        channel="terminal_voltage_v",
        maximum_absolute_error=0.5,
        minimum_robust_coverage_fraction=0.8,
        calibration_group_ids=["calibration-experiment-1"],
        holdout_runs=[run("run-A", "group-A"), run("run-B", "group-B")],
    )


def test_robust_enclosure_pass_does_not_establish_physical_validity():
    c = campaign()
    original = deepcopy(c)
    result = audit_heldout_intervals(**c)
    assert c == original
    assert result["status"] == "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    assert result["actual_independent_physical_validation_established"] is False
    assert result["decision_equivalent_to_physical_testing"] is False
    assert len(result["runs"]) == 2
    assert all(r["robustly_enclosed"] == 5 for r in result["runs"])
    assert all(r["worst_conservative_absolute_residual"] == pytest.approx(0.4) for r in result["runs"])


def test_hard_bound_can_make_point_in_interval_nonrobust():
    c = campaign()
    for row in c["holdout_runs"][0]["samples"]:
        row["measurement_hard_bound"] = 1.0
    report = audit_heldout_intervals(**c)
    run = report["runs"][0]
    assert run["point_estimate_inside"] == 5
    assert run["robustly_enclosed"] == 0
    assert report["status"] == "REPORTED_HOLDOUT_REJECTED"


def test_one_bad_run_cannot_be_hidden_by_pooled_coverage():
    c = campaign()
    c["holdout_runs"][1]["samples"][0]["observed"] = 12.0
    report = audit_heldout_intervals(**c)
    assert report["runs"][0]["error_gate_passed"] is True
    assert report["runs"][1]["error_gate_passed"] is False
    assert report["status"] == "REPORTED_HOLDOUT_REJECTED"


@pytest.mark.parametrize("field,value", [
    ("hardware_match", False),
    ("unused_for_calibration", False),
    ("dataset_kind", "synthetic_fixture"),
])
def test_operator_flags_prevent_false_pass(field, value):
    c = campaign()
    c["holdout_runs"][0][field] = value
    report = audit_heldout_intervals(**c)
    assert report["status"] == "REPORTED_HOLDOUT_REJECTED"
    assert report["actual_independent_physical_validation_established"] is False


def test_duplicate_or_leaked_groups_rejected():
    c = campaign()
    c["holdout_runs"][0]["group_id"] = "calibration-experiment-1"
    with pytest.raises(ValueError, match="leakage"):
        audit_heldout_intervals(**c)
    c = campaign()
    c["holdout_runs"][1]["group_id"] = "group-A"
    with pytest.raises(ValueError, match="duplicate"):
        audit_heldout_intervals(**c)


def test_identical_source_bytes_cannot_count_as_two_independent_runs():
    c = campaign()
    c["holdout_runs"][1]["source_sha256"] = c["holdout_runs"][0]["source_sha256"]
    with pytest.raises(ValueError, match="duplicate original source digest"):
        audit_heldout_intervals(**c)


def test_duplicate_sample_ids_rejected_across_runs():
    c = campaign()
    c["holdout_runs"][1]["samples"][0]["sample_id"] = "run-A-0"
    with pytest.raises(ValueError, match="unique"):
        audit_heldout_intervals(**c)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1, True])
def test_invalid_hard_bound_rejected(bad):
    c = campaign()
    c["holdout_runs"][0]["samples"][0]["measurement_hard_bound"] = bad
    with pytest.raises(ValueError, match="measurement_hard_bound"):
        audit_heldout_intervals(**c)


def test_nonfinite_overflow_rejected():
    c = campaign()
    s = c["holdout_runs"][0]["samples"][0]
    s.update(prediction=1e308, lower=1e308, upper=1e308,
             observed=-1e308, measurement_hard_bound=1e308)
    with pytest.raises(ValueError, match="overflow"):
        audit_heldout_intervals(**c)


def test_unbounded_integer_rejected_cleanly():
    c = campaign()
    c['holdout_runs'][0]['samples'][0]['observed'] = 10 ** 500
    with pytest.raises(ValueError, match='finite'):
        audit_heldout_intervals(**c)


def test_invalid_prediction_band_rejected():
    c = campaign()
    c["holdout_runs"][0]["samples"][0]["lower"] = 11.0
    with pytest.raises(ValueError, match="prediction"):
        audit_heldout_intervals(**c)


def test_minimum_independent_runs_required():
    c = campaign()
    c["holdout_runs"].pop()
    with pytest.raises(ValueError, match="two"):
        audit_heldout_intervals(**c)


def test_digest_and_threshold_format_enforced():
    c = campaign()
    c["frozen_model_git_sha"] = "unknown"
    with pytest.raises(ValueError, match="40-hex"):
        audit_heldout_intervals(**c)
    c = campaign()
    c["minimum_robust_coverage_fraction"] = 1.5
    with pytest.raises(ValueError, match="threshold"):
        audit_heldout_intervals(**c)
