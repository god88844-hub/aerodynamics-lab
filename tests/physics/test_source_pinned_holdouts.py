"""Synthetic M27.2 source bytes may spoof 'physical' metadata: NEVER evidence."""
from copy import deepcopy
from hashlib import sha256

import pytest

from physics.validation.source_pinned_holdouts import audit_source_pinned_holdouts


def fixture():
    runs = []
    for run_index in range(2):
        obs = ["sample_id,t_s,observed,measurement_hard_bound"]
        pred = ["sample_id,t_s,prediction,lower,upper"]
        base = 10 + .1 * run_index
        for j in range(6):
            t = j * .1
            obs.append(f"s{j},{t:.1f},{base+.1:.3f},0.05")
            pred.append(f"s{j},{t:.1f},{base:.3f},{base-.3:.3f},{base+.3:.3f}")
        o = "\n".join(obs) + "\n"
        p = "\n".join(pred) + "\n"
        runs.append({
            "run_id": f"synthetic_run_{run_index}", "group_id": f"synthetic_group_{run_index}",
            "dataset_kind": "reported_physical_measurements",  # deliberately spoofed label
            "hardware_match": True, "unused_for_calibration": True,
            "observed_csv": o, "observed_sha256": sha256(o.encode()).hexdigest(),
            "prediction_csv": p, "prediction_sha256": sha256(p.encode()).hexdigest(),
        })
    return {
        "frozen_model_git_sha": "a"*40,
        "frozen_protocol_sha256": "b"*64,
        "channel": "terminal_voltage_v",
        "maximum_absolute_error": .2,
        "minimum_robust_coverage_fraction": 1.0,
        "calibration_group_ids": ["synthetic_calibration"],
        "runs": runs,
    }


def audit(body=None):
    return audit_source_pinned_holdouts(**(body if body is not None else fixture()))


def test_exact_bytes_and_aligned_samples_consistent_but_unauthenticated():
    req = fixture()
    original = deepcopy(req)
    report = audit(req)
    assert req == original
    assert report["status"] == "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    assert report["source_bytes_integrity_verified_against_operator_supplied_digests"] is True
    assert report["source_identity_or_preregistration_externally_authenticated"] is False
    assert report["actual_independent_physical_validation_established"] is False
    assert report["decision_equivalent_to_physical_testing"] is False
    assert all(run["sample_count"] == 6 for run in report["runs"])
    assert all(run["robustly_enclosed"] == 6 for run in report["runs"])


def test_observation_tamper_rejected_by_original_digest():
    req = fixture()
    req["runs"][0]["observed_csv"] = req["runs"][0]["observed_csv"].replace("10.100", "10.800", 1)
    with pytest.raises(ValueError, match="digest mismatch"):
        audit(req)


def test_prediction_tamper_rejected_by_original_digest():
    req = fixture()
    req["runs"][0]["prediction_csv"] += " "
    with pytest.raises(ValueError, match="digest mismatch"):
        audit(req)


def test_paired_timestamp_grid_must_match_without_imputation():
    req = fixture()
    entry = req["runs"][0]
    entry["prediction_csv"] = entry["prediction_csv"].replace("s1,0.1", "s1,0.15", 1)
    entry["prediction_sha256"] = sha256(entry["prediction_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="time grids differ"):
        audit(req)


def test_missing_or_reordered_samples_rejected():
    req = fixture()
    entry = req["runs"][0]
    entry["prediction_csv"] = entry["prediction_csv"].replace("s1,0.1", "other,0.1", 1)
    entry["prediction_sha256"] = sha256(entry["prediction_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="sample IDs/time grids differ"):
        audit(req)


def test_bad_channel_header_and_duplicate_original_sources_fail():
    req = fixture()
    entry = req["runs"][0]
    entry["observed_csv"] = entry["observed_csv"].replace("observed,", "value,", 1)
    entry["observed_sha256"] = sha256(entry["observed_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="exact original CSV header"):
        audit(req)
    req = fixture()
    req["runs"][1]["observed_csv"] = req["runs"][0]["observed_csv"]
    req["runs"][1]["observed_sha256"] = req["runs"][0]["observed_sha256"]
    with pytest.raises(ValueError, match="reused or identical"):
        audit(req)


def test_reused_calibration_group_does_not_count_as_independent():
    req = fixture()
    req["runs"][0]["group_id"] = "synthetic_calibration"
    with pytest.raises(ValueError, match="leakage"):
        audit(req)


def test_synthetic_label_rejected_even_with_math_agreement():
    req = fixture()
    req["runs"][0]["dataset_kind"] = "synthetic_fixture"
    report = audit(req)
    assert report["status"] == "REPORTED_HOLDOUT_REJECTED"
    assert report["actual_independent_physical_validation_established"] is False


def test_heldout_prediction_outside_tolerance_rejects_entire_campaign():
    req = fixture()
    entry = req["runs"][0]
    entry["observed_csv"] = entry["observed_csv"].replace("10.100", "11.000", 1)
    entry["observed_sha256"] = sha256(entry["observed_csv"].encode()).hexdigest()
    report = audit(req)
    assert report["status"] == "REPORTED_HOLDOUT_REJECTED"
    assert not report["runs"][0]["error_gate_passed"]


@pytest.mark.parametrize("text,reason", [
    ("s0,0.0,10.100,NaN", "nonfinite"),
    ("s0,0.0,10.100,-0.01", "negative"),
    ("s0,0.0,10.100,", "empty"),
])
def test_nonphysical_measurement_error_budget_rejected(text, reason):
    req = fixture()
    entry = req["runs"][0]
    entry["observed_csv"] = entry["observed_csv"].replace("s0,0.0,10.100,0.05", text, 1)
    entry["observed_sha256"] = sha256(entry["observed_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match=reason):
        audit(req)


def test_limit_original_bytes_and_disallow_extra_columns():
    req = fixture()
    entry = req["runs"][0]
    entry["observed_csv"] += "x" * 1_000_000
    entry["observed_sha256"] = sha256(entry["observed_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="byte limit"):
        audit(req)
    req = fixture()
    entry = req["runs"][0]
    entry["observed_csv"] = entry["observed_csv"].replace("s0,0.0,10.100,0.05",
                                                           "s0,0.0,10.100,0.05,extra", 1)
    entry["observed_sha256"] = sha256(entry["observed_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="wrong column count"):
        audit(req)
