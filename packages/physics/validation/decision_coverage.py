"""M29.4 audited-by-operator decision-metric coverage matrix for release preflight.

Combines M27.5 timing, M28.6 geometry and M29.3 preflight consistency.
Even wholly green operator-reported metrics NEVER authorize physical flight.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_SHA1 = re.compile(r"^[a-f0-9]{40}$")


def _positive_finite(value: object, name: str, *, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: finite numeric input required")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name}: finite numeric input required") from exc
    if not math.isfinite(number) or number < 0 or (not allow_zero and number == 0):
        raise ValueError(f"{name}: positive finite numeric input required")
    return number


def assess_decision_metric_coverage(
    *,
    frozen_model_git_sha: str,
    timeline_report: Mapping,
    rotor_sphere_report: Mapping,
    prior_release_preflight: Mapping,
    critical_decisions: Sequence[str],
    declared_metric_reports: Sequence[Mapping],
) -> dict:
    """Check complete operator-reported numeric gates; never certify hardware.

    Each metric is a whole-run conservative maximum hard-error report, not a
    statistical probability or an authenticated instrument result. Its
    claimed predeclared tolerance is not checked against an external archive.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be lowercase 40-hex")
    if any(not isinstance(x, Mapping) for x in (timeline_report, rotor_sphere_report, prior_release_preflight)):
        raise ValueError("all three prior verification reports are required")
    if timeline_report.get("frozen_model_git_sha") != frozen_model_git_sha:
        raise ValueError("timeline model and release model identity differ")
    snapshot = prior_release_preflight.get("snapshot")
    if not isinstance(snapshot, Mapping) or snapshot.get("frozen_model_git_sha") != frozen_model_git_sha:
        raise ValueError("original release snapshot model identity differs")
    if rotor_sphere_report.get("design_name") != snapshot.get("geometry_design_name"):
        raise ValueError("geometry model design identity differs from release snapshot")
    if isinstance(critical_decisions, (str, bytes)) or not isinstance(critical_decisions, Sequence):
        raise ValueError("critical decisions must be an explicit sequence")
    decisions = list(critical_decisions)
    if not 1 <= len(decisions) <= 64 or any(not isinstance(d, str) or not _ID.fullmatch(d) for d in decisions):
        raise ValueError("invalid or absent critical decision metrics")
    if len(set(decisions)) != len(decisions):
        raise ValueError("duplicate critical decision")
    if isinstance(declared_metric_reports, (str, bytes)) or not isinstance(declared_metric_reports, Sequence):
        raise ValueError("exact per-critical-decision metric reports required")
    reports = {}
    keys = {"channel", "predeclared_max_hard_error", "reported_worst_hard_error",
            "holdout_group_count", "inside_declared_operating_envelope", "measurement_source"}
    for item in declared_metric_reports:
        if not isinstance(item, Mapping) or set(item) != keys:
            raise ValueError("metric report requires exact declared fields")
        channel = item["channel"]
        if not isinstance(channel, str) or not _ID.fullmatch(channel) or channel in reports:
            raise ValueError("invalid or duplicate metric channel")
        if not isinstance(item["measurement_source"], str) or not 1 <= len(item["measurement_source"].strip()) <= 500:
            raise ValueError("measurement source must be identified")
        if type(item["holdout_group_count"]) is not int or item["holdout_group_count"] < 0 or item["holdout_group_count"] > 10000:
            raise ValueError("invalid whole-holdout-group count")
        if type(item["inside_declared_operating_envelope"]) is not bool:
            raise ValueError("inside_declared_operating_envelope must be boolean")
        tolerance = _positive_finite(item["predeclared_max_hard_error"], "frozen tolerance")
        observed = _positive_finite(item["reported_worst_hard_error"], "conservative worst error", allow_zero=True)
        reports[channel] = {
            "channel": channel,
            "predeclared_max_hard_error": tolerance,
            "reported_worst_hard_error": observed,
            "holdout_group_count": item["holdout_group_count"],
            "inside_declared_operating_envelope": item["inside_declared_operating_envelope"],
            "measurement_source_operator_declared": item["measurement_source"].strip(),
            "declared_numeric_gate_passed": (
                observed <= tolerance and
                item["holdout_group_count"] >= 2 and
                item["inside_declared_operating_envelope"]
            ),
        }
    if set(reports) != set(decisions):
        raise ValueError("exactly one metric report per declared critical decision required")
    metrics = [reports[d] for d in sorted(decisions)]
    numeric_ok = all(m["declared_numeric_gate_passed"] for m in metrics)
    timeline_ok = (
        timeline_report.get("status") == "DECLARED_SEQUENCE_CONSISTENT_UNAUTHENTICATED"
        and timeline_report.get("reported_temporal_order_consistent") is True
    )
    geometry_ok = (
        rotor_sphere_report.get("status") == "ANALYTICAL_ORIENTATION_INDEPENDENT_SPHERE_SEPARATION_ONLY"
        and rotor_sphere_report.get("analytical_screen_passed") is True
    )
    preflight_ok = (
        prior_release_preflight.get("status") == "REPORTED_SOFTWARE_GATES_CONSISTENT_EXTERNAL_VERIFICATION_REQUIRED"
        and prior_release_preflight.get("software_preflight_consistency_operator_reported") is True
    )
    blockers = []
    if not timeline_ok:
        blockers.append("Declared frozen-model/test chronology does not pass internal checks")
    if not geometry_ok:
        blockers.append("Rotor outer-envelope separation is not demonstrated under declared assumptions")
    if not preflight_ok:
        blockers.append("Cross-domain release preflight has missing or failed reported checks")
    for metric in metrics:
        if not metric["declared_numeric_gate_passed"]:
            blockers.append(f"{metric['channel']}: reported hard-error, holdout count or envelope gate failed")
    blockers.extend([
        "Metric tolerances and reported errors are operator-supplied and not externally preregistered",
        "Instrument provenance, true raw measurements, exact hardware and model prediction error unauthenticated",
        "Independent physical decision equivalence, manufacturing approval and flightworthiness not established",
    ])
    internally_consistent = timeline_ok and geometry_ok and preflight_ok and numeric_ok
    canonical = {
        "frozen_model_git_sha": frozen_model_git_sha,
        "decisions": sorted(decisions),
        "metric_reports": metrics,
        "timeline_consistent_operator_reported": timeline_ok,
        "rotor_sphere_consistent_operator_reported": geometry_ok,
        "prior_preflight_consistent_operator_reported": preflight_ok,
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "status": (
            "OPERATOR_DECISION_COVERAGE_CONSISTENT_UNVERIFIED"
            if internally_consistent else "OPERATOR_DECISION_COVERAGE_BLOCKED"
        ),
        "canonical_report_sha256": digest,
        "declared_critical_decision_count": len(decisions),
        "metric_reports": metrics,
        "reported_software_coverage_consistent": internally_consistent,
        "blockers": blockers,
        "independent_physical_metric_coverage_authenticated": False,
        "real_world_equivalence_demonstrated": False,
        "design_airworthiness_established": False,
        "production_or_flight_release_authorized": False,
    }
