"""M27.8: exact original-source holdout regime-specific acceptance checks.

An attractive pooled average can hide a failed regime. Every declared
operating regime must be represented in at least two distinct whole
experimental groups, with every sample assigned exactly once; every
(group, regime) cell must pass hard-bound residual and full measurement
interval inclusion gates. Regime labels and physical sources are not
authenticated and are not proof of independent physical validity.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import re

from physics.validation.source_pinned_holdouts import (
    _OBS_HEADER, _PRED_HEADER, _read_original_csv, audit_source_pinned_holdouts,
)

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


def audit_per_regime_holdouts(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    channel: str,
    maximum_absolute_error: float,
    minimum_robust_coverage_fraction: float,
    calibration_group_ids: Sequence[str],
    runs: Sequence[Mapping],
    regime_ids: Sequence[str],
    regime_labels: Sequence[Mapping],
) -> dict:
    """Run original-source verification, then disjoint regime/campaign gates.

    regime_labels contains one entry per run:
      {"run_id": id, "sample_regimes": [
          {"sample_id": id, "regime_id": id}, ...]}
    For every run and regime with samples, require >=5 samples so singleton
    favorable observations cannot pass. Require >=2 whole-run groups/regime.
    """
    base = audit_source_pinned_holdouts(
        frozen_model_git_sha=frozen_model_git_sha,
        frozen_protocol_sha256=frozen_protocol_sha256,
        channel=channel,
        maximum_absolute_error=maximum_absolute_error,
        minimum_robust_coverage_fraction=minimum_robust_coverage_fraction,
        calibration_group_ids=calibration_group_ids,
        runs=runs,
    )
    if isinstance(regime_ids, (str, bytes)) or not isinstance(regime_ids, Sequence):
        raise ValueError("explicit predeclared regime IDs required")
    regimes = list(regime_ids)
    if not 1 <= len(regimes) <= 32 or any(not isinstance(r, str) or not _ID.fullmatch(r) for r in regimes):
        raise ValueError("1–32 unique valid regime identifiers required")
    if len(set(regimes)) != len(regimes):
        raise ValueError("duplicate predeclared regime identifier")
    if isinstance(regime_labels, (str, bytes)) or not isinstance(regime_labels, Sequence):
        raise ValueError("exact run-specific original sample regime labels required")
    if len(regime_labels) != len(runs):
        raise ValueError("one original sample regime mapping per run required")
    mapping = {}
    for item in regime_labels:
        if not isinstance(item, Mapping) or set(item) != {"run_id", "sample_regimes"}:
            raise ValueError("each regime map requires exact run ID and sample labels")
        run_id = item["run_id"]
        if not isinstance(run_id, str) or run_id in mapping:
            raise ValueError("invalid or duplicate regime run ID")
        samples = item["sample_regimes"]
        if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence):
            raise ValueError("regime labels must be an explicit sample sequence")
        labels = {}
        for label in samples:
            if not isinstance(label, Mapping) or set(label) != {"sample_id", "regime_id"}:
                raise ValueError("every sample regime label requires exact fields")
            sid, rid = label["sample_id"], label["regime_id"]
            if not isinstance(sid, str) or not _ID.fullmatch(sid) or sid in labels:
                raise ValueError("invalid or duplicate labeled sample ID")
            if rid not in regimes:
                raise ValueError("unregistered operating regime")
            labels[sid] = rid
        mapping[run_id] = labels
    if set(mapping) != {run["run_id"] for run in runs}:
        raise ValueError("labeled runs differ from original source runs")

    tolerance = float(maximum_absolute_error)
    min_coverage = float(minimum_robust_coverage_fraction)
    grouped: dict[str, list[dict]] = {regime: [] for regime in regimes}
    for run in runs:
        run_id = run["run_id"]
        observed = _read_original_csv(run["observed_csv"], run["observed_sha256"],
                                      _OBS_HEADER, f"{run_id}/observations")
        predicted = _read_original_csv(run["prediction_csv"], run["prediction_sha256"],
                                       _PRED_HEADER, f"{run_id}/predictions")
        labels = mapping[run_id]
        if set(labels) != {sample["sample_id"] for sample in observed}:
            raise ValueError(f"{run_id}: every original sample must be labeled exactly once")
        cells = {regime: [] for regime in regimes}
        for o, p in zip(observed, predicted):
            if o["sample_id"] != p["sample_id"] or o["t_s"] != p["t_s"]:
                raise ValueError("original sample grids are not identically aligned")
            sid = o["sample_id"]
            u, y, yhat = o["measurement_hard_bound"], o["observed"], p["prediction"]
            lo, hi = p["lower"], p["upper"]
            residual_bound = abs(yhat - y) + u
            if not all(math.isfinite(v) for v in (y-u, y+u, residual_bound)):
                raise ValueError("regime residual hard-bound overflow")
            cells[labels[sid]].append({
                "hard_residual": residual_bound,
                "robustly_enclosed": lo <= y-u and y+u <= hi,
                "error_met": residual_bound <= tolerance,
            })
        for regime in regimes:
            values = cells[regime]
            if not values:
                continue
            count = len(values)
            if count < 5:
                raise ValueError(f"{run_id}/{regime}: at least five samples per nonempty regime required")
            robust_count = sum(int(v["robustly_enclosed"]) for v in values)
            error_met = all(v["error_met"] for v in values)
            coverage = robust_count/count
            grouped[regime].append({
                "run_id": run_id,
                "group_id": run["group_id"],
                "sample_count": count,
                "robust_coverage_fraction": coverage,
                "max_conservative_abs_residual": max(v["hard_residual"] for v in values),
                "robust_interval_gate_passed": coverage >= min_coverage,
                "absolute_error_gate_passed": error_met,
                "cell_gate_passed": error_met and coverage >= min_coverage,
            })
    results = []
    accepted = base["status"] == "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    blockers = []
    for regime in regimes:
        rows = grouped[regime]
        unique_groups = {r["group_id"] for r in rows}
        independent_coverage_met = len(unique_groups) >= 2
        cells_met = bool(rows) and all(r["cell_gate_passed"] for r in rows)
        regime_passed = independent_coverage_met and cells_met
        accepted = accepted and regime_passed
        if not independent_coverage_met:
            blockers.append(f"{regime}: fewer than two declared whole-run holdout groups")
        if not cells_met:
            blockers.append(f"{regime}: at least one experiment/regime error or coverage gate failed")
        results.append({
            "regime_id": regime,
            "holdout_group_count": len(unique_groups),
            "declared_whole_run_coverage_met": independent_coverage_met,
            "each_experiment_regime_cell_passed": cells_met,
            "regime_analytical_gate_passed": regime_passed,
            "run_cells": rows,
        })
    if base["status"] == "REPORTED_HOLDOUT_REJECTED":
        blockers.append("Original source held-out campaign rejected or declared physical provenance unsupported")
    return {
        "status": ("ORIGINAL_REGIME_AUDIT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
                   if accepted else "ORIGINAL_REGIME_AUDIT_BLOCKED"),
        "frozen_model_git_sha": frozen_model_git_sha,
        "channel": channel,
        "base_holdout_status": base["status"],
        "original_byte_digests_checked": True,
        "regimes": results,
        "every_regime_and_run_cell_passed": accepted,
        "blockers": blockers,
        "regime_partition_authentically_predeclared": False,
        "real_physical_origin_independently_verified": False,
        "future_prediction_success_probability_established": False,
        "flight_release_authorized": False,
        "limitations": [
            "Regime IDs and membership are operator-declared and can be selected after observing outcomes",
            "Whole-run independence and actual physical provenance are not externally authenticated",
            "Per-regime mathematical gates cannot certify a future operating envelope or flightworthiness",
        ],
    }
