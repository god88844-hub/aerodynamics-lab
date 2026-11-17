"""M29.7 deterministic decision margin under operator-declared hard error budget.

A conservative sign test can be useful when full hard enclosures on model
discrepancy, solver discretization, input, geometry and measurement actually
exist. This code does not validate those hard bounds, nor establish physical
decision equivalence or release authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_BOUND_NAMES = (
    "model_form_hard_bound",
    "numerical_hard_bound",
    "input_parameter_hard_bound",
    "geometry_hard_bound",
    "measurement_hard_bound",
)
_REQUIRED = {
    "decision_id", "channel", "metric_unit", "failure_direction",
    "predicted_value", "failure_limit", "threshold_source", "prediction_source",
    *_BOUND_NAMES,
}


def _number(value: object, label: str, *, nonnegative: bool) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{label}: finite real number required")
    try:
        x = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{label}: finite real number required") from exc
    if not math.isfinite(x) or (nonnegative and x < 0):
        raise ValueError(f"{label}: finite " + ("nonnegative" if nonnegative else "real") + " number required")
    return x


def _id(value: object, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{label}: 1–100 valid ASCII identifier required")
    return value


def _source(value: object, label: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
        raise ValueError(f"{label}: nonempty operator source reference required")
    return value.strip()


def audit_hard_bound_decision_margins(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    design_name: str,
    frozen_scenario_report: Mapping,
    hard_bound_source: str,
    critical_decisions: Sequence[Mapping],
) -> dict:
    """Check whether declared worst-case error intervals stay on the safe side.

    For fail-when-above limit: margin=limit-predicted.
    For fail-when-below limit: margin=predicted-limit.
    Bound=U_model+U_solver+U_input+U_geometry+U_measurement.
    Strict positive residual margin is required; equality is inconclusive.
    This is a sufficient sign test *only if* every supplied error term is a
    valid deterministic hard enclosure over the entire operating envelope.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be lowercase 40 hex")
    if not isinstance(frozen_protocol_sha256, str) or not _SHA256.fullmatch(frozen_protocol_sha256):
        raise ValueError("frozen_protocol_sha256 must be lowercase SHA-256")
    design_name = _id(design_name, "design_name")
    hard_bound_source = _source(hard_bound_source, "hard_bound_source")
    if not isinstance(frozen_scenario_report, Mapping) or not isinstance(frozen_scenario_report.get("snapshot"), Mapping):
        raise ValueError("complete frozen scenario audit snapshot required")
    snapshot = frozen_scenario_report["snapshot"]
    if snapshot.get("model_git_sha") != frozen_model_git_sha or snapshot.get("design_name") != design_name:
        raise ValueError("scenario/model/design frozen identity mismatch")
    selected_channel = _id(snapshot.get("selected_channel"), "selected_channel")
    scenario_ok = (
        frozen_scenario_report.get("status") == "OPERATOR_FROZEN_SCENARIO_AUDIT_CONSISTENT_UNVERIFIED"
        and frozen_scenario_report.get("reported_software_consistency_passed") is True
    )
    if isinstance(critical_decisions, (str, bytes)) or not isinstance(critical_decisions, Sequence) or not 1 <= len(critical_decisions) <= 64:
        raise ValueError("1–64 declared decision rows required")
    seen = set()
    rows = []
    blockers = []
    all_margins = True
    for item in critical_decisions:
        if not isinstance(item, Mapping) or set(item) != _REQUIRED:
            raise ValueError("each decision requires exact threshold/prediction/hard-error fields")
        did = _id(item["decision_id"], "decision_id")
        channel = _id(item["channel"], "channel")
        unit = _id(item["metric_unit"], "metric_unit")
        if did in seen:
            raise ValueError("duplicate decision identifier")
        seen.add(did)
        if channel != selected_channel:
            raise ValueError("decision channel must match frozen scenario critical channel")
        direction = item["failure_direction"]
        if direction not in ("exceed_max", "fall_below_min"):
            raise ValueError("failure_direction must be exceed_max or fall_below_min")
        predicted = _number(item["predicted_value"], "predicted_value", nonnegative=False)
        limit = _number(item["failure_limit"], "failure_limit", nonnegative=False)
        threshold_source = _source(item["threshold_source"], "threshold_source")
        prediction_source = _source(item["prediction_source"], "prediction_source")
        bounds = {key: _number(item[key], key, nonnegative=True) for key in _BOUND_NAMES}
        combined = sum(bounds.values())
        raw_margin = limit-predicted if direction == "exceed_max" else predicted-limit
        robust_margin = raw_margin-combined
        if not all(math.isfinite(v) for v in (combined, raw_margin, robust_margin)):
            raise ValueError("combined decision hard-error budget overflow")
        passed = robust_margin > 0
        all_margins = all_margins and passed
        if not passed:
            blockers.append(f"{did}: combined hard error touches/exceeds declared failure threshold")
        rows.append({
            "decision_id": did, "channel": channel, "metric_unit": unit,
            "failure_direction": direction,
            "predicted_value": predicted, "failure_limit": limit,
            "nominal_margin_to_failure": raw_margin,
            "combined_worst_case_hard_bound": combined,
            "remaining_conservative_hard_margin": robust_margin,
            "declared_assumption_margin_gate_passed": passed,
            "declared_hard_error_terms": bounds,
            "threshold_source_operator_declared": threshold_source,
            "prediction_source_operator_declared": prediction_source,
        })
    rows.sort(key=lambda x: x["decision_id"])
    if not scenario_ok:
        blockers.append("Frozen scenario source, geometry, numerical or decision audit is not internally consistent")
    blockers.extend([
        "Declared error bounds are not independently verified as physical hard enclosures",
        "Model-form discrepancy and all operating modes may have unbounded missing failure mechanisms",
        "A successful deterministic margin screen is not an empirical probability or flight approval",
    ])
    internally_ok = all_margins and scenario_ok
    canonical = {
        "model_git_sha": frozen_model_git_sha,
        "protocol_sha256": frozen_protocol_sha256,
        "design_name": design_name,
        "frozen_scenario_snapshot_sha256_operator_declared": frozen_scenario_report.get("snapshot_sha256"),
        "hard_bound_source_operator_declared": hard_bound_source,
        "decisions": rows,
        "frozen_scenario_consistent_operator_declared": scenario_ok,
    }
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return {
        "status": ("OPERATOR_HARD_MARGIN_CONSISTENT_BOUNDS_UNVERIFIED"
                   if internally_ok else "OPERATOR_HARD_MARGIN_GATE_BLOCKED"),
        "canonical_hard_margin_report_sha256": digest,
        "declared_decision_count": len(rows),
        "decisions": rows,
        "all_declared_hard_margin_gates_passed": internally_ok,
        "blockers": blockers,
        "model_form_hard_error_independently_validated": False,
        "complete_physical_failure_modes_covered": False,
        "future_failure_probability_established": False,
        "simulation_decision_equivalent_to_physical_validation": False,
        "manufacturing_or_flight_release_authorized": False,
    }
