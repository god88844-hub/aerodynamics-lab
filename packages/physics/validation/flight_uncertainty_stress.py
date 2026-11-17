"""M26.12: recompute sensitivity of heldout decisions to widened error budgets.

Never reuses caller-supplied green result flags. Each additional scenario
must not decrease measurement, numerical or model discrepancy uncertainty
below the preregistered baseline. All comparisons read original bytes anew.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json

from physics.validation.flight_clock_alignment import _finite
from physics.validation.frozen_flight_comparison import compare_frozen_flight_channel

_PARAMS = {
    "measurement_hard_error", "numerical_hard_error",
    "additional_model_discrepancy_hard_error",
    "predeclared_max_conservative_error",
    "predeclared_min_robust_interval_coverage",
}
_SCENARIO = {
    "scenario_id", "measurement_hard_error", "numerical_hard_error",
    "additional_model_discrepancy_hard_error",
}


def _checked_budget(values: Mapping, *, exact: set[str]) -> dict:
    if not isinstance(values, Mapping) or set(values) != exact:
        raise ValueError("exact uncertainty and fixed acceptance fields required")
    parsed = {k: _finite(v, k, nonnegative=True) for k, v in values.items() if k != "scenario_id"}
    if "predeclared_min_robust_interval_coverage" in parsed and parsed["predeclared_min_robust_interval_coverage"] > 1:
        raise ValueError("predeclared coverage must be <= 1")
    return parsed


def audit_frozen_uncertainty_sensitivity(
    root, source_manifest: Mapping, *,
    holdout_case: Mapping, original_case: Mapping,
    baseline_limits: Mapping, widened_error_scenarios: Sequence[Mapping],
) -> dict:
    """Recompute each source/prediction comparison with widened uncertainty."""
    if not isinstance(original_case, Mapping) or set(original_case) != {
        "observed_relative_path", "channel", "frozen_prediction_csv_path",
        "frozen_prediction_sha256", "maximum_original_time_gap_s",
    }:
        raise ValueError("exact original source and frozen prediction case required")
    base = _checked_budget(baseline_limits, exact=_PARAMS)
    if (isinstance(widened_error_scenarios, (str, bytes))
            or not isinstance(widened_error_scenarios, Sequence)
            or not 1 <= len(widened_error_scenarios) <= 12):
        raise ValueError("1..12 explicit widened hard-error scenarios required")
    ids = set()
    scenarios = []
    for case in widened_error_scenarios:
        checked = _checked_budget(case, exact=_SCENARIO)
        scenario_id = case["scenario_id"]
        if (not isinstance(scenario_id, str) or not scenario_id
                or len(scenario_id) > 100 or scenario_id in ids):
            raise ValueError("unique nonempty scenario_id required")
        ids.add(scenario_id)
        for name in _PARAMS & _SCENARIO:
            if checked[name] < base[name]:
                raise ValueError("uncertainty stress scenarios cannot reduce frozen baseline hard budgets")
        scenarios.append((scenario_id, checked))

    def calculate(budget):
        return compare_frozen_flight_channel(
            root, source_manifest, holdout_case=holdout_case, **original_case, **budget
        )

    baseline = calculate(base)
    evaluated = []
    for scenario_id, values in sorted(scenarios):
        stressed = dict(base)
        stressed.update(values)
        report = calculate(stressed)
        evaluated.append({
            "scenario_id": scenario_id,
            "widened_hard_error_assumptions": values,
            "analytical_gates_passed": report["analytical_gates_passed"],
            "maximum_conservative_absolute_residual": report["maximum_conservative_absolute_residual"],
            "robust_measurement_interval_coverage_fraction": report[
                "robust_measurement_interval_coverage_fraction"
            ],
            "error_margin_to_declared_maximum": (
                base["predeclared_max_conservative_error"] -
                report["maximum_conservative_absolute_residual"]
            ),
        })
    if not baseline["analytical_gates_passed"]:
        status = "FAIL_ORIGINAL_DECLARED_NUMERICAL_BASELINE"
    elif any(not entry["analytical_gates_passed"] for entry in evaluated):
        status = "INCONCLUSIVE_UNCERTAINTY_STRESS_LOSES_DECLARED_PASS"
    else:
        status = "ALL_SUBMITTED_UNCERTAINTY_STRESSES_CONDITIONALLY_PASS_UNAUTHENTICATED"
    stable = {
        "flight_id": baseline["flight_id"], "channel": baseline["channel"],
        "original_source_sha256": baseline["measured_original_sha256"],
        "prediction_sha256": baseline["frozen_prediction_sha256"],
        "split_sha256": baseline["canonical_split_sha256"],
        "baseline_parameters": base,
        "baseline_passed": baseline["analytical_gates_passed"],
        "scenarios": evaluated,
    }
    digest = hashlib.sha256(json.dumps(
        stable, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return {
        "status": status, "canonical_sensitivity_sha256": digest,
        "baseline_recomputed_report": baseline,
        "stress_scenario_reports": evaluated,
        "all_declared_uncertainty_scenarios_passed": (
            baseline["analytical_gates_passed"]
            and all(x["analytical_gates_passed"] for x in evaluated)
        ),
        "true_hard_uncertainty_bounds_independently_established": False,
        "physical_measured_source_and_holdout_blinding_authenticated": False,
        "physical_prediction_accuracy_established": False,
        "flight_release_authorized": False,
    }
