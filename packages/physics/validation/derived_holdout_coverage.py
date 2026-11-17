"""M26.23: no cherry-picked single-flight pass for derived channels.

Recomputes every provided file's holdout comparison and counts independent
DECLARED experiment groups, without claiming their real-world independence.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence

from physics.validation.derived_holdout_comparison import compare_derived_holdout
from physics.validation.flight_holdout_preflight import prepare_whole_flight_holdout_manifest

_CASE = {
    "derived_csv_path", "provenance_json_path", "channel",
    "maximum_declared_sample_gap_s", "frozen_prediction_csv_path",
    "frozen_prediction_sha256", "measurement_hard_error",
    "numerical_hard_error", "model_discrepancy_hard_error",
    "predeclared_max_conservative_error", "predeclared_min_robust_coverage",
}


def audit_derived_holdout_group_coverage(root, manifest, *, holdout_case: Mapping,
                                         comparison_cases: Sequence[Mapping],
                                         required_regime: str, required_channel: str,
                                         minimum_distinct_holdout_groups: int = 2) -> dict:
    if not isinstance(required_regime, str) or not required_regime:
        raise ValueError("exact operating regime required")
    if not isinstance(required_channel, str) or not required_channel:
        raise ValueError("exact measured channel required")
    if type(minimum_distinct_holdout_groups) is not int or not 2 <= minimum_distinct_holdout_groups <= 50:
        raise ValueError("required group count must be 2..50")
    if (isinstance(comparison_cases, (str, bytes)) or not isinstance(comparison_cases, Sequence)
            or not 1 <= len(comparison_cases) <= 500):
        raise ValueError("at least one holdout comparison source required")
    split = prepare_whole_flight_holdout_manifest(root, manifest, **holdout_case)
    reports = []
    source_seen, prediction_seen = set(), set()
    fixed_acceptance = None
    for item in comparison_cases:
        if not isinstance(item, Mapping) or set(item) != _CASE:
            raise ValueError("comparison cases require exact original-derived/prediction fields")
        if item["channel"] != required_channel:
            raise ValueError("wrong channel cannot satisfy declared coverage")
        # One frozen numeric criterion and uncertainty budget for every
        # independent claimed holdout in the same channel and regime.
        criterion = tuple(item[k] for k in (
            "measurement_hard_error", "numerical_hard_error",
            "model_discrepancy_hard_error", "predeclared_max_conservative_error",
            "predeclared_min_robust_coverage",
        ))
        if fixed_acceptance is None:
            fixed_acceptance = criterion
        elif criterion != fixed_acceptance:
            raise ValueError("holdout cases cannot cherry-pick different critical acceptance thresholds or uncertainty budgets")
        path = str(item["derived_csv_path"])
        prediction = str(item["frozen_prediction_csv_path"])
        if path in source_seen or prediction in prediction_seen:
            raise ValueError("duplicate derived source or prediction cannot count multiple times")
        source_seen.add(path)
        prediction_seen.add(prediction)
        report = compare_derived_holdout(root, manifest, holdout_case=holdout_case, **item)
        if report["operating_regime_id"] != required_regime:
            raise ValueError("wrong operating regime cannot count toward coverage")
        reports.append(report)
    groups = {}
    for row in reports:
        groups.setdefault(row["experimental_group_id"], []).append(row)
    passed = sorted(g for g, rs in groups.items() if all(r["operator_declared_numerical_gate_passed"] for r in rs))
    failed = sorted(g for g, rs in groups.items() if any(not r["operator_declared_numerical_gate_passed"] for r in rs))
    if failed:
        verdict = "FAIL_DECLARED_DERIVED_HOLDOUT_CRITICAL_METRIC"
    elif len(passed) < minimum_distinct_holdout_groups:
        verdict = "INCONCLUSIVE_INSUFFICIENT_WHOLE_FLIGHT_DERIVED_HOLDOUTS"
    else:
        verdict = "CONDITIONAL_DERIVED_HOLDOUT_GROUP_COVERAGE_UNAUTHENTICATED"
    return {
        "status": verdict,
        "canonical_split_sha256": split["canonical_split_sha256"],
        "operating_regime_id": required_regime, "channel": required_channel,
        "required_distinct_holdout_groups": minimum_distinct_holdout_groups,
        "declared_passing_groups": passed, "declared_failing_groups": failed,
        "comparison_reports": sorted(reports, key=lambda r: (r["flight_id"], r["derived_csv_sha256"])),
        "all_numeric_checks_passed": bool(not failed and len(passed) >= minimum_distinct_holdout_groups),
        "independent_flight_custody_authenticated": False,
        "calibration_and_units_authenticated": False,
        "physical_prediction_validation_completed": False,
    }
