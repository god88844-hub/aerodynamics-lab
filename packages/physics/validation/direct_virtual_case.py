"""M29.8 direct cross-domain recomputation for an operator-supplied virtual case.

Unlike previous metadata preflight gates, this calls M27.9 and M28.10
analytical engines from supplied primary numeric input and does not trust
separately submitted 'passed' flags. Neither inputs, operating envelope
nor physical provenance are externally authenticated: no flight release.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.continuous_rotor_pair_clearance import screen_continuous_rotor_pair_clearance
from physics.validation.affine_adc_holdout import audit_affine_sensor_holdouts

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DECISION_FIELDS = {
    "decision_id", "channel", "metric_unit", "failure_direction", "predicted_value", "failure_limit",
    "additional_model_form_hard_bound", "numerical_hard_bound",
    "input_hard_bound", "geometry_hard_bound", "threshold_source",
}
_ROTOR_CASE_KEYS = {
    "installed_rotor_diameters_m", "maximum_swept_heights_m",
    "diameter_hard_bounds_m", "center_position_hard_bounds_m",
    "center_speed_hard_bounds_m_per_s", "time_samples",
    "minimum_declared_pair_gap_m", "trajectory_source",
    "geometry_hard_bound_source", "rotor_center_speed_source",
}
_SENSOR_CASE_KEYS = {
    "frozen_model_git_sha", "frozen_protocol_sha256", "channel",
    "calibration", "calibration_source",
    "maximum_conservative_absolute_residual",
    "minimum_interval_coverage_fraction", "holdout_runs",
}


def _finite(value: object, name: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: finite numeric value required")
    try:
        x = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name}: finite numeric value required") from exc
    if not math.isfinite(x) or (nonnegative and x < 0):
        raise ValueError(f"{name}: finite nonnegative/real numeric value required")
    return x


def _source(value: object, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
        raise ValueError(f"{name}: provenance reference required")
    return value.strip()


def audit_direct_virtual_case(
    design: DroneDesign,
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    operating_envelope_id: str,
    operating_envelope_source: str,
    sensor_case: Mapping,
    rotor_pair_motion_case: Mapping,
    decision_thresholds: Sequence[Mapping],
) -> dict:
    """Call source-value screens directly; derive gates from their real outputs.

    The maximum sensor/holdout residual includes any declared sensor hard
    errors. Its addition to other absolute error allowances is a conservative
    operator-supplied bound, not proof of model-form behavior outside the
    exact exercised scenario. In particular, it does NOT establish an actual
    physical upper envelope on future prediction errors.
    """
    if not isinstance(frozen_model_git_sha,str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha requires lowercase 40-hex")
    if not isinstance(frozen_protocol_sha256,str) or not _SHA256.fullmatch(frozen_protocol_sha256):
        raise ValueError("frozen_protocol_sha256 requires lowercase SHA-256")
    if not isinstance(operating_envelope_id,str) or not _ID.fullmatch(operating_envelope_id):
        raise ValueError("operating_envelope_id requires source-declared identifier")
    envelope_source = _source(operating_envelope_source,"operating_envelope_source")
    if not isinstance(sensor_case,Mapping) or set(sensor_case)!=_SENSOR_CASE_KEYS:
        raise ValueError("sensor_case exact original numerical input fields required")
    if sensor_case["frozen_model_git_sha"] != frozen_model_git_sha or sensor_case["frozen_protocol_sha256"] != frozen_protocol_sha256:
        raise ValueError("sensor case and frozen model/protocol identity mismatch")
    if not isinstance(rotor_pair_motion_case,Mapping) or set(rotor_pair_motion_case)!=_ROTOR_CASE_KEYS:
        raise ValueError("rotor_pair_motion_case exact numerical input fields required")
    sensor = audit_affine_sensor_holdouts(**sensor_case)
    geometry = screen_continuous_rotor_pair_clearance(design,**rotor_pair_motion_case)
    if isinstance(decision_thresholds,(str,bytes)) or not isinstance(decision_thresholds,Sequence) or not 1<=len(decision_thresholds)<=64:
        raise ValueError("1–64 decision thresholds required")
    worst_sensor = max(run["maximum_conservative_abs_residual"] for run in sensor["runs"])
    seen = set()
    decisions = []
    for entry in decision_thresholds:
        if not isinstance(entry,Mapping) or set(entry)!=_DECISION_FIELDS:
            raise ValueError("each decision requires exact failure threshold and hard-bound source fields")
        did = entry["decision_id"]
        if not isinstance(did,str) or not _ID.fullmatch(did) or did in seen:
            raise ValueError("invalid or duplicated decision ID")
        seen.add(did)
        if entry["channel"] != sensor["channel"] or entry["metric_unit"] != sensor["calibration_output_unit_operator_declared"]:
            raise ValueError("decision channel/unit differs from calibrated observation channel and unit")
        direction=entry["failure_direction"]
        if direction not in ("exceed_max","fall_below_min"):
            raise ValueError("failure_direction must be exceed_max or fall_below_min")
        predicted=_finite(entry["predicted_value"],"predicted_value")
        limit=_finite(entry["failure_limit"],"failure_limit")
        _source(entry["threshold_source"],"threshold_source")
        fields=(
            "additional_model_form_hard_bound", "numerical_hard_bound",
            "input_hard_bound", "geometry_hard_bound",
        )
        additional={key:_finite(entry[key],key,nonnegative=True) for key in fields}
        total=worst_sensor+sum(additional.values())
        nominal=(limit-predicted if direction=="exceed_max" else predicted-limit)
        remaining=nominal-total
        if not all(math.isfinite(x) for x in (total,nominal,remaining)):
            raise ValueError("decision residual margin arithmetic overflow")
        passed=remaining>0
        decisions.append({
            "decision_id":did, "channel":sensor["channel"],
            "metric_unit":sensor["calibration_output_unit_operator_declared"],
            "failure_direction":direction,
            "predicted_value":predicted, "failure_limit":limit,
            "maximum_declared_calibration_inclusive_holdout_residual":worst_sensor,
            "additional_hard_bounds":additional,
            "total_assumed_hard_residual_budget":total,
            "conditional_margin_to_failure":remaining,
            "declared_analytical_decision_margin_passed":passed,
        })
    decisions.sort(key=lambda x:x["decision_id"])
    sensor_ok=sensor["all_declared_holdout_analytical_gates_passed"] is True
    geometry_ok=geometry["analytical_screen_passed"] is True
    margins_ok=all(row["declared_analytical_decision_margin_passed"] for row in decisions)
    passed=sensor_ok and geometry_ok and margins_ok
    blockers=[]
    if not sensor_ok:
        blockers.append("Calibration-inclusive whole-run sensor holdout comparison failed")
    if not geometry_ok:
        blockers.append("Continuously moving rotor-pair assumed envelope clearance not established")
    if not margins_ok:
        blockers.append("One or more critical decision hard-error margins were insufficient")
    blockers.extend([
        "No sensor calibration authority or original hardware/ADC acquisition authenticity verified",
        "Reported holdout errors cannot be promoted to genuine upper bounds on unseen operating conditions",
        "Rotor geometry/velocity limits and model-form hard errors are operator-declared, not physically bounded",
        "No verified independent real-aircraft reliability or manufacturing/flight authorization",
    ])
    canonical={
        "model_git_sha":frozen_model_git_sha,
        "protocol_sha256":frozen_protocol_sha256,
        "design_name":design.name,
        "operating_envelope_id":operating_envelope_id,
        "operator_envelope_source":envelope_source,
        "sensor_report_digest":sensor["operator_report_digest_sha256"],
        "geometry_minimum_assumed_gap":geometry["minimum_analytical_full_interval_gap_m"],
        "decisions":decisions,
        "reported_analytic_gate_passed":passed,
    }
    digest=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {
        "status":("DIRECTLY_RECOMPUTED_VIRTUAL_CASE_CONSISTENT_UNVERIFIED"
                  if passed else "DIRECTLY_RECOMPUTED_VIRTUAL_CASE_BLOCKED"),
        "canonical_operator_case_digest_sha256":digest,
        "operating_envelope_id_operator_declared":operating_envelope_id,
        "calibration_inclusive_holdout_report":sensor,
        "continuous_rotor_pair_geometry_report":geometry,
        "decision_margins":decisions,
        "all_recomputed_operator_analytical_gates_passed":passed,
        "blockers":blockers,
        "physical_sensor_and_calibration_sources_authenticated":False,
        "real_as_built_dynamic_geometry_validated":False,
        "unseen_scenarios_decision_equivalence_established":False,
        "flight_or_manufacturing_release_authorized":False,
    }
