"""M29.6 cross-check source-to-obstacle-to-solver report consistency.

A consistency screen is not a physical acceptance, product certification,
authentic source review or remotely verified CI result. The submitted report
objects and any green flags can be fabricated by the operator.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def assess_frozen_scenario_coverage(
    *,
    frozen_model_git_sha: str,
    design_name: str,
    selected_channel: str,
    intended_envelope_id: str,
    original_clock_report: Mapping,
    obstacle_inventory_report: Mapping,
    solver_convergence_report: Mapping,
    decision_coverage_report: Mapping,
) -> dict:
    """Verify self-reported analyses refer to one frozen scenario and channel.

    A decision coverage record claiming a smaller worst-case error than the
    directly linked clock/instrument bounded original-source holdouts is
    inconsistent. Numerical discretization is separately screened; this
    does not mathematically prove the model-form error is bounded.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be lowercase 40-hex")
    for label, value in (("design_name", design_name), ("selected_channel", selected_channel),
                         ("intended_envelope_id", intended_envelope_id)):
        if not isinstance(value, str) or not _NAME.fullmatch(value):
            raise ValueError(f"{label}: declared identifier required")
    reports = (original_clock_report, obstacle_inventory_report,
               solver_convergence_report, decision_coverage_report)
    if any(not isinstance(r, Mapping) for r in reports):
        raise ValueError("all four source/geometry/numerical/decision reports required")
    if original_clock_report.get("frozen_model_git_sha") != frozen_model_git_sha:
        raise ValueError("original source clock report model mismatch")
    if solver_convergence_report.get("model_git_sha") != frozen_model_git_sha:
        raise ValueError("numerical solver convergence report model mismatch")
    if original_clock_report.get("channel") != selected_channel or solver_convergence_report.get("channel") != selected_channel:
        raise ValueError("original-source and solver channels do not match")
    obstacle = obstacle_inventory_report.get("geometry_report")
    if not isinstance(obstacle, Mapping) or obstacle.get("design_name") != design_name:
        raise ValueError("obstacle inventory geometry design identity differs")
    records = decision_coverage_report.get("metric_reports")
    if not isinstance(records, list):
        raise ValueError("complete decision metric coverage report required")
    matching = [entry for entry in records if isinstance(entry, Mapping) and entry.get("channel") == selected_channel]
    if len(matching) != 1:
        raise ValueError("exact selected decision-critical channel report required")
    record = matching[0]
    observed = record.get("reported_worst_hard_error")
    if isinstance(observed, bool) or not isinstance(observed, (int, float)):
        raise ValueError("metric report worst bound must be finite")
    try:
        reported_max = float(observed)
    except (OverflowError, ValueError) as exc:
        raise ValueError("metric report worst bound must be finite") from exc
    if not math.isfinite(reported_max) or reported_max < 0:
        raise ValueError("metric report worst bound must be finite nonnegative")
    source_runs = original_clock_report.get("runs")
    if not isinstance(source_runs, list) or len(source_runs) < 2:
        raise ValueError("two or more whole-run clock-bounded reports required")
    seen_groups = set()
    raw_worst = 0.
    raw_all_pass = True
    for run in source_runs:
        if not isinstance(run, Mapping):
            raise ValueError("invalid original-source run")
        group = run.get("group_id")
        if not isinstance(group, str) or not _NAME.fullmatch(group) or group in seen_groups:
            raise ValueError("duplicated or invalid source experimental group")
        seen_groups.add(group)
        raw = run.get("worst_conservative_absolute_residual_upper")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError("raw worst bound must be finite")
        try:
            val = float(raw)
        except (ValueError, OverflowError) as exc:
            raise ValueError("raw worst bound must be finite") from exc
        if not math.isfinite(val) or val < 0:
            raise ValueError("raw worst bound must be finite nonnegative")
        raw_worst = max(raw_worst, val)
        raw_all_pass &= run.get("analytical_clock_residual_gate_passed") is True
    if reported_max + 1e-12 < raw_worst:
        raise ValueError("decision metric hard error understates clock-bounded original source residual")
    clock_ok = (
        original_clock_report.get("status") == "ORIGINAL_CLOCK_BUDGETS_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
        and original_clock_report.get("all_claimed_holdout_and_clock_gates_passed") is True
        and raw_all_pass
    )
    obstacle_ok = (
        obstacle_inventory_report.get("status") == "DECLARED_OBSTACLE_INVENTORY_SCREENED_ANALYTICALLY_ONLY"
        and obstacle_inventory_report.get("declared_inventory_exactly_covered") is True
        and obstacle_inventory_report.get("analytical_screen_passed") is True
        and obstacle.get("analytical_screen_passed") is True
    )
    numerical_ok = (
        solver_convergence_report.get("status") == "REPORTED_THREE_GRID_CONVERGENCE_CONSISTENT_UNVERIFIED"
        and solver_convergence_report.get("analytical_convergence_gate_passed") is True
    )
    decision_ok = (
        decision_coverage_report.get("status") == "OPERATOR_DECISION_COVERAGE_CONSISTENT_UNVERIFIED"
        and decision_coverage_report.get("reported_software_coverage_consistent") is True
        and record.get("declared_numeric_gate_passed") is True
        and record.get("inside_declared_operating_envelope") is True
        and record.get("holdout_group_count") == len(seen_groups)
    )
    blockers = []
    if not clock_ok:
        blockers.append("Original-source clock and sensor bounds fail the reported holdout gate")
    if not obstacle_ok:
        blockers.append("Operator-declared airframe obstacle clearance inventory is incomplete or not screened")
    if not numerical_ok:
        blockers.append("Conditional three-grid numerical convergence was not demonstrated")
    if not decision_ok:
        blockers.append("Critical decision metric coverage/operating-envelope claim is inconsistent")
    blockers.extend([
        "Operator-supplied reports and per-domain provenance cannot authenticate physical experiments",
        "Source identity, instrument calibration, actual as-built obstacle inventory and qualified flight approvals absent",
    ])
    software_ok = clock_ok and obstacle_ok and numerical_ok and decision_ok
    snapshot = {
        "model_git_sha": frozen_model_git_sha,
        "design_name": design_name, "selected_channel": selected_channel,
        "intended_envelope_id": intended_envelope_id,
        "declared_obstacle_inventory_sha256": obstacle_inventory_report.get("declared_inventory_digest_sha256"),
        "source_whole_holdout_group_count": len(seen_groups),
        "clock_bounded_worst_absolute_residual": raw_worst,
        "reported_max_absolute_residual": reported_max,
        "clock_screen_operator_reported": clock_ok,
        "obstacle_screen_operator_reported": obstacle_ok,
        "numerical_screen_operator_reported": numerical_ok,
        "decision_screen_operator_reported": decision_ok,
    }
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {
        "status": ("OPERATOR_FROZEN_SCENARIO_AUDIT_CONSISTENT_UNVERIFIED"
                   if software_ok else "OPERATOR_FROZEN_SCENARIO_AUDIT_BLOCKED"),
        "snapshot_sha256": digest,
        "snapshot": snapshot,
        "reported_software_consistency_passed": software_ok,
        "blockers": blockers,
        "physical_source_attestation_verified": False,
        "real_assembled_aircraft_geometry_authenticated": False,
        "real_world_predictive_accuracy_validated": False,
        "engineering_airworthiness_established": False,
        "production_or_flight_release_authorized": False,
    }
