"""M27.7 synthetic original-byte and clock-budget consistency regression."""
from copy import deepcopy
from hashlib import sha256

import pytest

from physics.validation.original_clock_budgets import audit_original_holdout_clock_budgets


def fixture():
    records, clocks = [], []
    for run_index in range(2):
        obs = ["sample_id,t_s,observed,measurement_hard_bound"]
        pred = ["sample_id,t_s,prediction,lower,upper"]
        budgets = []
        for k in range(5):
            t = round(k * .1, 1)
            observed = 10.1 + .1 * run_index
            predicted = 10 + .1 * run_index
            obs.append(f"s{k},{t:.1f},{observed:.2f},0.05")
            pred.append(f"s{k},{t:.1f},{predicted:.2f},{predicted-.4:.2f},{predicted+.4:.2f}")
            budgets.append({
                "sample_id": f"s{k}", "time_s": t,
                "clock_time_hard_bound_s": .02, "signal_slew_hard_bound_per_s": 1.,
            })
        obs_text, pred_text = "\n".join(obs) + "\n", "\n".join(pred) + "\n"
        records.append({
            "run_id": f"run{run_index}", "group_id": f"group{run_index}",
            "dataset_kind": "reported_physical_measurements",  # unverified synthetic label
            "hardware_match": True, "unused_for_calibration": True,
            "observed_csv": obs_text, "prediction_csv": pred_text,
            "observed_sha256": sha256(obs_text.encode()).hexdigest(),
            "prediction_sha256": sha256(pred_text.encode()).hexdigest(),
        })
        clocks.append({"run_id": f"run{run_index}", "samples": budgets})
    return {
        "frozen_model_git_sha": "a"*40, "frozen_protocol_sha256": "b"*64,
        "channel": "voltage_v", "maximum_absolute_error": .2,
        "minimum_robust_coverage_fraction": 1.0,
        "calibration_group_ids": ["calibration_only"],
        "runs": records, "clock_bound_runs": clocks,
        "clock_bound_source": "assumed not measured clock hard bound",
        "slew_bound_source": "assumed not measured slew limit",
    }


def test_original_bytes_and_clock_uncertainty_math_not_physical_proof():
    req = fixture()
    original = deepcopy(req)
    out = audit_original_holdout_clock_budgets(**req)
    assert req == original
    assert out["status"] == "ORIGINAL_CLOCK_BUDGETS_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    assert len(out["runs"]) == 2
    assert all(run["worst_conservative_absolute_residual_upper"] == pytest.approx(.17)
               for run in out["runs"])
    assert not out["clock_calibration_authenticated"]
    assert not out["original_measurement_physical_origin_authenticated"]
    assert not out["independent_real_world_fidelity_established"]
    assert not out["flight_release_authorized"]


def test_large_declared_clock_uncertainty_can_reject_formerly_good_holdouts():
    req = fixture()
    for clock in req["clock_bound_runs"]:
        for row in clock["samples"]:
            row["clock_time_hard_bound_s"] = .2
    out = audit_original_holdout_clock_budgets(**req)
    assert out["status"] == "ORIGINAL_CLOCK_BUDGETS_REJECTED"
    assert not out["all_claimed_holdout_and_clock_gates_passed"]


def test_tampered_original_source_rejected():
    req = fixture()
    req["runs"][0]["observed_csv"] += " "
    with pytest.raises(ValueError, match="digest mismatch"):
        audit_original_holdout_clock_budgets(**req)


def test_clock_budget_cannot_skip_sample_or_change_time_grid():
    req = fixture()
    req["clock_bound_runs"][0]["samples"].pop()
    with pytest.raises(ValueError, match="one clock hard-bound entry"):
        audit_original_holdout_clock_budgets(**req)
    req = fixture()
    req["clock_bound_runs"][0]["samples"][0]["time_s"] = .03
    with pytest.raises(ValueError, match="clock budget mismatch"):
        audit_original_holdout_clock_budgets(**req)


def test_duplicate_run_budget_and_missing_run_rejected():
    req = fixture()
    req["clock_bound_runs"][1]["run_id"] = "run0"
    with pytest.raises(ValueError, match="duplicate"):
        audit_original_holdout_clock_budgets(**req)
    req = fixture()
    req["clock_bound_runs"][1]["run_id"] = "other"
    with pytest.raises(ValueError, match="must match"):
        audit_original_holdout_clock_budgets(**req)


def test_synthetic_label_and_calibration_group_leakage_block_claimed_gate():
    req = fixture()
    req["runs"][0]["dataset_kind"] = "synthetic_fixture"
    out = audit_original_holdout_clock_budgets(**req)
    assert not out["all_claimed_holdout_and_clock_gates_passed"]
    req = fixture()
    req["runs"][1]["group_id"] = "calibration_only"
    with pytest.raises(ValueError, match="leakage"):
        audit_original_holdout_clock_budgets(**req)


@pytest.mark.parametrize("bound", [-1, float("nan"), float("inf"), True])
def test_invalid_clock_hard_bounds_fail_closed(bound):
    req = fixture()
    req["clock_bound_runs"][0]["samples"][0]["clock_time_hard_bound_s"] = bound
    with pytest.raises(ValueError, match="finite"):
        audit_original_holdout_clock_budgets(**req)
