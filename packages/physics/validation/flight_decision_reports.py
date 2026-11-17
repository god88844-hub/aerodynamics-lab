"""M26.10 frozen metric-by-regime decision screen using recomputed byte-linked inputs.

No accepted caller-provided result flags: re-evaluate every prediction CSV
against its original held-out measured CSV, with the SAME predeclared metric
thresholds per regime and separate experiment groups.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from physics.validation.flight_holdout_preflight import prepare_whole_flight_holdout_manifest
from physics.validation.flight_channel_csv import _CHANNEL_UNITS
from physics.validation.flight_clock_alignment import _finite
from physics.validation.frozen_flight_comparison import compare_frozen_flight_channel

_REQUIREMENT = {
    "operating_regime_id", "channel", "minimum_distinct_holdout_groups",
    "measurement_hard_error", "numerical_hard_error",
    "additional_model_discrepancy_hard_error",
    "predeclared_max_conservative_error",
    "predeclared_min_robust_interval_coverage",
}
_CASE = {
    "observed_relative_path", "channel", "frozen_prediction_csv_path",
    "frozen_prediction_sha256", "maximum_original_time_gap_s",
}


def assess_original_flight_decisions(
    root, source_manifest: Mapping, *,
    holdout_case: Mapping,
    required_metrics: Sequence[Mapping],
    comparison_cases: Sequence[Mapping],
) -> dict:
    """Classify a missing metric as INCONCLUSIVE; any real numeric failure as FAIL.

    All data source authenticity and objective preregistration remain
    unauthenticated regardless of the numerical classifications.
    """
    if (isinstance(required_metrics, (str, bytes)) or not isinstance(required_metrics, Sequence)
            or not 1 <= len(required_metrics) <= 100):
        raise ValueError("1..100 exact critical metric requirements are required")
    if (isinstance(comparison_cases, (str, bytes)) or not isinstance(comparison_cases, Sequence)
            or not 1 <= len(comparison_cases) <= 500):
        raise ValueError("1..500 actual source/prediction cases required")
    reqs = {}
    for item in required_metrics:
        if not isinstance(item, Mapping) or set(item) != _REQUIREMENT:
            raise ValueError("exact critical metric requirements required")
        regime, channel = item["operating_regime_id"], item["channel"]
        if not isinstance(regime, str) or not regime or len(regime) > 100:
            raise ValueError("invalid predeclared regime")
        if not isinstance(channel, str) or channel not in _CHANNEL_UNITS:
            raise ValueError("unsupported predeclared measured channel")
        key = (regime, channel)
        if key in reqs:
            raise ValueError("duplicate critical regime-channel requirement")
        minimum = item["minimum_distinct_holdout_groups"]
        if type(minimum) is not int or not 2 <= minimum <= 50:
            raise ValueError("minimum_distinct_holdout_groups must be 2..50")
        for name in _REQUIREMENT - {"operating_regime_id", "channel", "minimum_distinct_holdout_groups"}:
            value = _finite(item[name], name, nonnegative=True)
            if name == "predeclared_min_robust_interval_coverage" and value > 1:
                raise ValueError("coverage fraction must be <=1")
        reqs[key] = item

    split = prepare_whole_flight_holdout_manifest(root, source_manifest, **holdout_case)
    by_flight = {row["flight_id"]: row for row in split["partitions"]}
    by_original_path = {row["relative_path"]: row for row in source_manifest["files"]}
    measured_paths = set()
    reports = []
    for case in comparison_cases:
        if not isinstance(case, Mapping) or set(case) != _CASE:
            raise ValueError("each comparison requires exact measured and frozen source fields")
        path = case["observed_relative_path"]
        if not isinstance(path, str) or path in measured_paths or path not in by_original_path:
            raise ValueError("each original measurement path must be declared exactly once")
        measured_paths.add(path)
        measured = by_original_path[path]
        flight = by_flight[measured["flight_id"]]
        if flight["partition"] != "holdout":
            raise ValueError("calibration source cannot be used as independent heldout decision")
        key = (flight["operating_regime_id"], case["channel"])
        if key not in reqs:
            raise ValueError("comparison case for undeclared regime-channel decision")
        req = reqs[key]
        r = compare_frozen_flight_channel(
            root, source_manifest, holdout_case=holdout_case,
            observed_relative_path=path, channel=case["channel"],
            frozen_prediction_csv_path=case["frozen_prediction_csv_path"],
            frozen_prediction_sha256=case["frozen_prediction_sha256"],
            maximum_original_time_gap_s=case["maximum_original_time_gap_s"],
            measurement_hard_error=req["measurement_hard_error"],
            numerical_hard_error=req["numerical_hard_error"],
            additional_model_discrepancy_hard_error=req["additional_model_discrepancy_hard_error"],
            predeclared_max_conservative_error=req["predeclared_max_conservative_error"],
            predeclared_min_robust_interval_coverage=req["predeclared_min_robust_interval_coverage"],
        )
        reports.append(r)
    summarized = []
    any_fail = False
    any_missing = False
    for key, req in sorted(reqs.items()):
        selected = [r for r in reports if (r["operating_regime_id"], r["channel"]) == key]
        groups = {}
        for r in selected:
            group = r["experimental_group_id"]
            groups.setdefault(group, []).append(r)
        passing_groups = sorted(
            group for group, entries in groups.items()
            if all(entry["analytical_gates_passed"] for entry in entries)
        )
        failed_groups = sorted(
            group for group, entries in groups.items()
            if any(not entry["analytical_gates_passed"] for entry in entries)
        )
        if failed_groups:
            status = "DECLARED_CRITICAL_METRIC_FAILED"
            any_fail = True
        elif len(passing_groups) < req["minimum_distinct_holdout_groups"]:
            status = "INCONCLUSIVE_INSUFFICIENT_INDEPENDENT_HOLDOUT_GROUPS"
            any_missing = True
        else:
            status = "RECOMPUTED_DECLARED_NUMERIC_METRIC_PASSED_UNAUTHENTICATED"
        summarized.append({
            "operating_regime_id": key[0],
            "channel": key[1], "unit": _CHANNEL_UNITS[key[1]],
            "status": status,
            "reported_passing_groups": passing_groups,
            "reported_failing_groups": failed_groups,
            "minimum_predeclared_groups": req["minimum_distinct_holdout_groups"],
            "reported_group_count": len(groups),
            "true_holdout_group_independence_authenticated": False,
        })
    all_numeric = not any_fail and not any_missing
    verdict = (
        "FAIL_DECLARED_CRITICAL_NUMERIC_LIMIT_VIOLATION" if any_fail
        else "INCONCLUSIVE_ORIGINAL_HOLDOUT_COVERAGE_MISSING" if any_missing
        else "ANALYTICALLY_CONSISTENT_NOT_PHYSICALLY_AUTHENTICATED"
    )
    stable = {
        "split_sha256": split["canonical_split_sha256"],
        "requirements": [dict(reqs[k]) for k in sorted(reqs)],
        "results": sorted(
            [{k: r[k] for k in (
                "flight_id", "experimental_group_id", "operating_regime_id", "channel",
                "measured_original_sha256", "frozen_prediction_sha256",
                "maximum_conservative_absolute_residual",
                "robust_measurement_interval_coverage_fraction",
                "analytical_gates_passed",
            )} for r in reports],
            key=lambda r: (r["flight_id"], r["channel"]),
        ),
    }
    digest = hashlib.sha256(json.dumps(
        stable, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return {
        "status": verdict,
        "canonical_recomputed_decision_sha256": digest,
        "canonical_split_sha256": split["canonical_split_sha256"],
        "critical_metric_verdicts": summarized,
        "recomputed_flight_channel_comparisons": sorted(
            reports, key=lambda r: (r["flight_id"], r["channel"]),
        ),
        "all_operator_declared_analytical_gates_passed": all_numeric,
        "independent_original_measurement_origin_authenticated": False,
        "calibration_instruments_and_clocks_authenticated": False,
        "preregistration_and_holdout_blinding_authenticated": False,
        "physical_decision_equivalence_established": False,
        "manufacturing_or_flight_release_authorized": False,
    }
