"""M27.8 synthetic per-regime holdout checks, not physical source validation."""
from copy import deepcopy
from hashlib import sha256
import pytest

from physics.validation.regime_holdout_audit import audit_per_regime_holdouts


def fixture():
    runs = []
    labels = []
    for k in range(2):
        observed = ["sample_id,t_s,observed,measurement_hard_bound"]
        predictions = ["sample_id,t_s,prediction,lower,upper"]
        assignment = []
        for j in range(10):
            t = j / 10
            sid = f"s{j}"
            prediction = 10 + k / 10
            observed.append(f"{sid},{t:.1f},{prediction+.1:.2f},0.05")
            predictions.append(f"{sid},{t:.1f},{prediction:.2f},{prediction-.4:.2f},{prediction+.4:.2f}")
            assignment.append({"sample_id": sid, "regime_id": "hover" if j < 5 else "climb"})
        obs, pred = "\n".join(observed) + "\n", "\n".join(predictions) + "\n"
        runs.append({
            "run_id": f"run{k}", "group_id": f"hardware_group{k}",
            "dataset_kind": "reported_physical_measurements",  # spoofed synthetic label
            "hardware_match": True, "unused_for_calibration": True,
            "observed_csv": obs, "prediction_csv": pred,
            "observed_sha256": sha256(obs.encode()).hexdigest(),
            "prediction_sha256": sha256(pred.encode()).hexdigest(),
        })
        labels.append({"run_id": f"run{k}", "sample_regimes": assignment})
    return {
        "frozen_model_git_sha": "a"*40,
        "frozen_protocol_sha256": "b"*64,
        "channel": "terminal_voltage_v",
        "maximum_absolute_error": .2,
        "minimum_robust_coverage_fraction": 1.,
        "calibration_group_ids": ["calibration_unused"],
        "runs": runs,
        "regime_ids": ["hover", "climb"],
        "regime_labels": labels,
    }


def audit(req=None):
    return audit_per_regime_holdouts(**(fixture() if req is None else req))


def test_every_cell_must_pass_and_no_physical_origin_is_authenticated():
    req = fixture()
    old = deepcopy(req)
    result = audit(req)
    assert req == old
    assert result["status"] == "ORIGINAL_REGIME_AUDIT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    assert result["every_regime_and_run_cell_passed"]
    assert len(result["regimes"]) == 2
    assert all(len(r["run_cells"]) == 2 and r["regime_analytical_gate_passed"] for r in result["regimes"])
    assert not result["regime_partition_authentically_predeclared"]
    assert not result["real_physical_origin_independently_verified"]
    assert not result["future_prediction_success_probability_established"]
    assert not result["flight_release_authorized"]


def test_one_failed_regime_prevents_positive_campaign_approval():
    req = fixture()
    run = req["runs"][1]
    run["observed_csv"] = run["observed_csv"].replace("s5,0.5,10.20,0.05", "s5,0.5,11.00,0.05")
    run["observed_sha256"] = sha256(run["observed_csv"].encode()).hexdigest()
    r = audit(req)
    assert r["status"] == "ORIGINAL_REGIME_AUDIT_BLOCKED"
    assert any(not x["regime_analytical_gate_passed"] for x in r["regimes"])


def test_one_regime_missing_in_second_group_cannot_hide_under_pooled_data():
    req = fixture()
    for entry in req["regime_labels"][1]["sample_regimes"]:
        entry["regime_id"] = "hover"
    r = audit(req)
    assert r["status"] == "ORIGINAL_REGIME_AUDIT_BLOCKED"
    assert next(x for x in r["regimes"] if x["regime_id"] == "climb")["holdout_group_count"] == 1


def test_missing_or_duplicate_sample_label_is_refused():
    req = fixture()
    req["regime_labels"][0]["sample_regimes"].pop()
    with pytest.raises(ValueError, match="every original sample"):
        audit(req)
    req = fixture()
    req["regime_labels"][0]["sample_regimes"][1]["sample_id"] = "s0"
    with pytest.raises(ValueError, match="duplicate labeled"):
        audit(req)


def test_regime_for_one_sample_with_insufficient_count_fails_closed():
    req = fixture()
    req["regime_ids"].append("tiny")
    req["regime_labels"][0]["sample_regimes"][0]["regime_id"] = "tiny"
    with pytest.raises(ValueError, match="at least five"):
        audit(req)


def test_source_tamper_and_calibration_overlap_rejected():
    req = fixture()
    req["runs"][0]["prediction_csv"] += " "
    with pytest.raises(ValueError, match="digest mismatch"):
        audit(req)
    req = fixture()
    req["runs"][1]["group_id"] = "calibration_unused"
    with pytest.raises(ValueError, match="leakage"):
        audit(req)


def test_unregistered_regimes_and_duplicate_run_mapping_are_errors():
    req = fixture()
    req["regime_labels"][0]["sample_regimes"][0]["regime_id"] = "secret"
    with pytest.raises(ValueError, match="unregistered"):
        audit(req)
    req = fixture()
    req["regime_labels"][1]["run_id"] = "run0"
    with pytest.raises(ValueError, match="duplicate regime run"):
        audit(req)
