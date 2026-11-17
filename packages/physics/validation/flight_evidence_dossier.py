"""M26.13 reproducible *analytical* validation dossier from three raw-data gates.

Recomputes M26.10 metric decisions, M26.11 component operating-limit screens
and M26.12 uncertainty stress directly from original/prediction files.
No user-supplied 'passed' reports are accepted. FAIL dominates INCONCLUSIVE,
and even an all-green mathematical result does not authenticate physical data.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from physics.validation.flight_decision_reports import assess_original_flight_decisions
from physics.validation.flight_envelope_limits import screen_flight_hard_limits
from physics.validation.flight_uncertainty_stress import audit_frozen_uncertainty_sensitivity

_STRESS = {"observed_relative_path", "widened_error_scenarios"}


def build_flight_evidence_dossier(
    root, source_manifest: Mapping, *,
    holdout_case: Mapping,
    required_metrics: Sequence[Mapping],
    comparison_cases: Sequence[Mapping],
    required_limits: Sequence[Mapping],
    stress_cases: Sequence[Mapping],
) -> dict:
    """Generate deterministic evidence fingerprint and fail-closed verdict."""
    metrics = assess_original_flight_decisions(
        root, source_manifest, holdout_case=holdout_case,
        required_metrics=required_metrics, comparison_cases=comparison_cases,
    )
    originals = [c["observed_relative_path"] for c in comparison_cases]
    if not isinstance(required_limits, Sequence) or isinstance(required_limits, (str, bytes)):
        raise ValueError("all critical metrics require declared hard-limit envelopes")
    if ({(x["operating_regime_id"], x["channel"]) for x in required_limits}
            != {(x["operating_regime_id"], x["channel"]) for x in required_metrics}):
        raise ValueError("hard-limit regime/channel scope must exactly match required critical metrics")
    limits = screen_flight_hard_limits(
        root, source_manifest, holdout_case=holdout_case,
        required_limits=required_limits, observed_source_paths=originals,
    )
    if isinstance(stress_cases, (str, bytes)) or not isinstance(stress_cases, Sequence) or len(stress_cases) != len(originals):
        raise ValueError("every original comparison needs exactly one uncertainty stress case")
    by_stress = {}
    for row in stress_cases:
        if not isinstance(row, Mapping) or set(row) != _STRESS:
            raise ValueError("exact source and widened error scenarios required")
        path = row["observed_relative_path"]
        if not isinstance(path, str) or path in by_stress:
            raise ValueError("uncertainty stress source path must be unique")
        by_stress[path] = row["widened_error_scenarios"]
    if set(by_stress) != set(originals):
        raise ValueError("uncertainty stress sources must match all original comparison cases")
    by_file = {f["relative_path"]: f for f in source_manifest["files"]}
    partition_by_flight = {r["flight_id"]: r for r in holdout_case["partitions"]}
    metric_by_pair = {(r["operating_regime_id"], r["channel"]): r for r in required_metrics}
    stressed = []
    for case in sorted(comparison_cases, key=lambda x: x["observed_relative_path"]):
        original = by_file[case["observed_relative_path"]]
        part = partition_by_flight[original["flight_id"]]
        req = metric_by_pair[(part["operating_regime_id"], case["channel"])]
        baseline = {k: req[k] for k in (
            "measurement_hard_error", "numerical_hard_error",
            "additional_model_discrepancy_hard_error",
            "predeclared_max_conservative_error",
            "predeclared_min_robust_interval_coverage",
        )}
        report = audit_frozen_uncertainty_sensitivity(
            root, source_manifest, holdout_case=holdout_case,
            original_case=case, baseline_limits=baseline,
            widened_error_scenarios=by_stress[case["observed_relative_path"]],
        )
        stressed.append({
            "observed_relative_path": case["observed_relative_path"],
            "flight_id": original["flight_id"],
            "channel": case["channel"],
            "report": report,
        })
    failure = (metrics["status"] == "FAIL_DECLARED_CRITICAL_NUMERIC_LIMIT_VIOLATION"
               or limits["any_declared_hard_limit_exceeded"]
               or any(s["report"]["status"] == "FAIL_ORIGINAL_DECLARED_NUMERICAL_BASELINE" for s in stressed))
    insufficient = (
        metrics["status"] != "ANALYTICALLY_CONSISTENT_NOT_PHYSICALLY_AUTHENTICATED"
        or limits["status"] != "WITHIN_OPERATOR_DECLARED_LIMITS_UNAUTHENTICATED"
        or any(not s["report"]["all_declared_uncertainty_scenarios_passed"] for s in stressed)
        or source_manifest["source_permission"] is None
    )
    verdict = (
        "FAIL_CRITICAL_RECOMPUTED_LIMIT_OR_PREDICTION"
        if failure else
        "INCONCLUSIVE_SOURCE_ENVELOPE_COVERAGE_OR_ERROR_SENSITIVITY"
        if insufficient else
        "CONDITIONAL_ANALYTICAL_SCREEN_ONLY_EXTERNAL_PHYSICAL_REVIEW_REQUIRED"
    )
    stable = {
        "archive": source_manifest["archive_id"],
        "split": metrics["canonical_split_sha256"],
        "decisions": metrics["canonical_recomputed_decision_sha256"],
        "hard_limits": limits["canonical_hard_limit_report_sha256"],
        "stress": sorted([
            {"path": row["observed_relative_path"],
             "sha256": row["report"]["canonical_sensitivity_sha256"]}
            for row in stressed
        ], key=lambda row: row["path"]),
        "verdict": verdict,
    }
    return {
        "status": verdict,
        "reproducible_dossier_sha256": hashlib.sha256(json.dumps(
            stable, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest(),
        "canonical_input_and_report_fingerprints": stable,
        "critical_metric_recomputed_report": metrics,
        "operating_envelope_and_hard_limit_report": limits,
        "per_original_holdout_uncertainty_stress_reports": stressed,
        "all_declared_analytical_gates_passed": not failure and not insufficient,
        "independent_real_world_recording_origin_authenticated": False,
        "instrument_calibration_and_physical_limits_authenticated": False,
        "historical_model_freeze_and_blind_holdouts_authenticated": False,
        "decision_equivalent_physical_evidence_established": False,
        "manufacturing_or_flight_release_authorized": False,
        "unresolved_external_evidence_issue": 16,
    }
