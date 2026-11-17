"""M27.7 join exact-byte paired holdout recordings to declared hard clock budgets.

This module refuses a clock budget that does not cover exactly every raw
observation. It does not independently verify timestamp sources, sensor
calibration, physical test origin or the actual signal slew hard bounds.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from physics.validation.source_pinned_holdouts import (
    _OBS_HEADER, _PRED_HEADER, _read_original_csv, audit_source_pinned_holdouts,
)
from physics.validation.clock_residual_bounds import audit_clock_bounded_residuals


def audit_original_holdout_clock_budgets(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    channel: str,
    maximum_absolute_error: float,
    minimum_robust_coverage_fraction: float,
    calibration_group_ids: Sequence[str],
    runs: Sequence[Mapping],
    clock_bound_runs: Sequence[Mapping],
    clock_bound_source: str,
    slew_bound_source: str,
) -> dict:
    """Require original files and per-sample time/slew error budgets agree.

    Clock budgets may only add uncertainty; they cannot replace or narrow the
    original instrument measurement hard bounds from the original CSVs.
    """
    original = audit_source_pinned_holdouts(
        frozen_model_git_sha=frozen_model_git_sha,
        frozen_protocol_sha256=frozen_protocol_sha256,
        channel=channel,
        maximum_absolute_error=maximum_absolute_error,
        minimum_robust_coverage_fraction=minimum_robust_coverage_fraction,
        calibration_group_ids=calibration_group_ids,
        runs=runs,
    )
    if isinstance(clock_bound_runs, (str, bytes)) or not isinstance(clock_bound_runs, Sequence):
        raise ValueError("exact run-specific clock hard-bound records required")
    if len(clock_bound_runs) != len(runs):
        raise ValueError("exactly one clock hard-bound record for each original holdout run required")
    by_run = {}
    for item in clock_bound_runs:
        if not isinstance(item, Mapping) or set(item) != {"run_id", "samples"}:
            raise ValueError("clock budget requires exact run_id and samples")
        run_id = item.get("run_id")
        if not isinstance(run_id, str) or run_id in by_run:
            raise ValueError("duplicate or invalid clock budget run_id")
        by_run[run_id] = item["samples"]
    run_ids = {run["run_id"] for run in runs}
    if set(by_run) != run_ids:
        raise ValueError("clock budget group IDs must match original holdout run IDs")

    summaries = []
    all_pass = original["status"] == "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    for run in runs:
        run_id = run["run_id"]
        observed = _read_original_csv(run["observed_csv"], run["observed_sha256"],
                                      _OBS_HEADER, f"{run_id}/observations")
        predictions = _read_original_csv(run["prediction_csv"], run["prediction_sha256"],
                                         _PRED_HEADER, f"{run_id}/predictions")
        budget = by_run[run_id]
        if isinstance(budget, (str, bytes)) or not isinstance(budget, Sequence) or len(budget) != len(observed):
            raise ValueError(f"{run_id}: one clock hard-bound entry per raw sample required")
        combined = []
        for o, p, bound in zip(observed, predictions, budget):
            if not isinstance(bound, Mapping) or set(bound) != {
                "sample_id", "time_s", "clock_time_hard_bound_s",
                "signal_slew_hard_bound_per_s",
            }:
                raise ValueError(f"{run_id}: exact clock budget sample fields required")
            if (bound["sample_id"] != o["sample_id"] or bound["time_s"] != o["t_s"]
                    or p["sample_id"] != o["sample_id"] or p["t_s"] != o["t_s"]):
                raise ValueError(f"{run_id}: original sample/time grid and clock budget mismatch")
            combined.append({
                "sample_id": o["sample_id"], "time_s": o["t_s"],
                "prediction": p["prediction"], "observed": o["observed"],
                "measurement_hard_bound": o["measurement_hard_bound"],
                "clock_time_hard_bound_s": bound["clock_time_hard_bound_s"],
                "signal_slew_hard_bound_per_s": bound["signal_slew_hard_bound_per_s"],
            })
        report = audit_clock_bounded_residuals(
            model_git_sha=frozen_model_git_sha,
            protocol_sha256=frozen_protocol_sha256,
            channel=channel, absolute_error_tolerance=maximum_absolute_error,
            minimum_coverage_fraction=minimum_robust_coverage_fraction,
            samples=combined,
            measurement_source=f"original SHA-256 {run['observed_sha256']}",
            clock_bound_source=clock_bound_source,
            slew_bound_source=slew_bound_source,
        )
        all_pass = all_pass and report["metric_analytical_gate_passed"]
        summaries.append({
            "run_id": run_id,
            "group_id": run["group_id"],
            "original_observation_sha256": run["observed_sha256"],
            "original_prediction_sha256": run["prediction_sha256"],
            "sample_count": report["sample_count"],
            "worst_conservative_absolute_residual_upper": report["worst_conservative_absolute_residual_upper"],
            "clock_and_instrument_coverage_fraction": report["conservative_coverage_fraction"],
            "analytical_clock_residual_gate_passed": report["metric_analytical_gate_passed"],
        })
    return {
        "status": ("ORIGINAL_CLOCK_BUDGETS_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
                   if all_pass else "ORIGINAL_CLOCK_BUDGETS_REJECTED"),
        "frozen_model_git_sha": frozen_model_git_sha,
        "frozen_protocol_sha256": frozen_protocol_sha256,
        "channel": channel,
        "original_byte_digest_checks_passed": True,
        "all_claimed_holdout_and_clock_gates_passed": all_pass,
        "runs": summaries,
        "clock_calibration_authenticated": False,
        "signal_slew_hard_bounds_authenticated": False,
        "original_measurement_physical_origin_authenticated": False,
        "independent_real_world_fidelity_established": False,
        "flight_release_authorized": False,
        "limitations": [
            "Declared clock/slew hard bounds are not independently calibrated or authenticated",
            "Matching CSVs with supplied digests cannot establish physical acquisition",
            "All holdouts are operator-reported; independent physical evidence remains required",
        ],
    }
