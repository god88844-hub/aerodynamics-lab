"""M20 frozen preregistration audit. No physical validation or flight authorization."""
from __future__ import annotations

from datetime import date
from hashlib import sha256
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from physics.validation.telemetry_ingestion import TelemetryManifest


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


PhysicalChannel = Literal[
    "terminal_voltage_v", "current_a", "temperature_c", "altitude_m",
    "vertical_speed_m_s", "wind_speed_m_s", "thrust_n", "rpm",
    "mass_kg", "attitude_error_deg", "energy_wh", "endurance_s",
    "structural_deflection_mm", "shaft_torque_nm",
]

UNITS = {
    "terminal_voltage_v": "V", "current_a": "A", "temperature_c": "degC",
    "altitude_m": "m", "vertical_speed_m_s": "m/s", "wind_speed_m_s": "m/s",
    "thrust_n": "N", "rpm": "rpm", "mass_kg": "kg", "attitude_error_deg": "deg",
    "energy_wh": "Wh", "endurance_s": "s", "structural_deflection_mm": "mm",
    "shaft_torque_nm": "N*m",
}


class RegisteredHardware(StrictModel):
    role: Literal["airframe", "motor", "propeller", "esc", "battery", "controller", "sensor", "payload"]
    model: str = Field(min_length=1, max_length=160)
    serial_or_lot: str | None = Field(default=None, max_length=160)
    geometry_or_firmware_revision: str | None = Field(default=None, max_length=160)
    quantity: int = Field(ge=1, le=100)


class RegisteredInstrument(StrictModel):
    channel: PhysicalChannel
    manufacturer_model: str = Field(min_length=1, max_length=160)
    serial: str | None = Field(default=None, max_length=160)
    calibration_reference: str | None = Field(default=None, max_length=500)
    calibration_date_utc: date | None = None
    bandwidth_hz: float | None = Field(default=None, gt=0)
    clock_alignment_bound_s: float | None = Field(default=None, ge=0, le=2)


class UncertaintyTerm(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    channel: PhysicalChannel
    absolute_value: float = Field(ge=0)
    type: Literal["hard_absolute_bound", "standard_uncertainty"]
    source_reference: str | None = Field(default=None, max_length=500)
    independent_standard_terms_assumed: bool = False

    @model_validator(mode="after")
    def check_assumption(self):
        if self.type == "hard_absolute_bound" and self.independent_standard_terms_assumed:
            raise ValueError("independence assumption applies only to standard uncertainties")
        return self


class AcceptanceMetric(StrictModel):
    channel: PhysicalChannel
    maximum_absolute_prediction_error: float = Field(gt=0)
    minimum_holdout_samples: int = Field(ge=5, le=100000)
    maximum_sampling_gap_s: float = Field(gt=0, le=300)
    decision_critical: bool = True


class ExperimentPlan(StrictModel):
    experiment_id: str = Field(min_length=1, max_length=120)
    recording_id: str = Field(min_length=1, max_length=120)
    vehicle_id: str = Field(min_length=1, max_length=120)
    battery_id: str = Field(min_length=1, max_length=120)
    role: Literal["calibration", "holdout"]
    scenario: str = Field(min_length=1, max_length=160)
    original_data_source: str | None = Field(default=None, max_length=500)


class OperatingEnvelope(StrictModel):
    ambient_temperature_c: tuple[float, float]
    air_density_kg_m3: tuple[float, float]
    wind_speed_m_s: tuple[float, float]
    payload_kg: tuple[float, float]
    altitude_m: tuple[float, float]

    @model_validator(mode="after")
    def validate_envelope(self):
        for key in type(self).model_fields:
            lo, hi = getattr(self, key)
            if lo >= hi:
                raise ValueError(f"{key} operating interval must increase strictly")
        if (self.air_density_kg_m3[0] <= 0 or self.wind_speed_m_s[0] < 0
                or self.payload_kg[0] < 0):
            raise ValueError("nonphysical air density, wind, or payload envelope")
        return self


class ValidationProtocol(StrictModel):
    schema_version: Literal["1.0"]
    protocol_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    intended_engineering_decision: str = Field(min_length=8, max_length=1000)
    frozen_model_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    frozen_design_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_controller_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    preregistration_record_reference: str | None = Field(default=None, max_length=500)
    numerical_convergence_report_reference: str | None = Field(default=None, max_length=500)
    independent_reviewer_reference: str | None = Field(default=None, max_length=500)
    approved_test_safety_plan_reference: str | None = Field(default=None, max_length=500)
    envelope: OperatingEnvelope
    hardware: list[RegisteredHardware] = Field(min_length=1, max_length=200)
    instruments: list[RegisteredInstrument] = Field(min_length=1, max_length=100)
    uncertainties: list[UncertaintyTerm] = Field(min_length=1, max_length=200)
    acceptance_metrics: list[AcceptanceMetric] = Field(min_length=1, max_length=30)
    experiments: list[ExperimentPlan] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def reject_ambiguity(self):
        refs = ("preregistration_record_reference", "numerical_convergence_report_reference",
                "independent_reviewer_reference", "approved_test_safety_plan_reference")
        if any(getattr(self, k) is not None and not getattr(self, k).strip() for k in refs):
            raise ValueError("blank document reference")
        if len({m.channel for m in self.acceptance_metrics}) != len(self.acceptance_metrics):
            raise ValueError("duplicate acceptance metric channel")
        if len({m.channel for m in self.instruments}) != len(self.instruments):
            raise ValueError("duplicate instrument channel")
        if len({(m.channel, m.name) for m in self.uncertainties}) != len(self.uncertainties):
            raise ValueError("duplicate uncertainty source on one channel")
        if len({(h.role, h.model, h.serial_or_lot) for h in self.hardware}) != len(self.hardware):
            raise ValueError("duplicate registered hardware identity")
        if len({e.recording_id for e in self.experiments}) != len(self.experiments):
            raise ValueError("duplicate experiment recording ID")
        if len({e.experiment_id for e in self.experiments}) != len(self.experiments):
            raise ValueError("duplicate whole-experiment ID")
        return self


class ProtocolAuditRequest(StrictModel):
    protocol: ValidationProtocol
    expected_frozen_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    imported_manifests: list[TelemetryManifest] = Field(default_factory=list, max_length=60)


def protocol_sha256(protocol: ValidationProtocol) -> str:
    """Normalized JSON hash checks changes, NOT independent timestamp/approval."""
    canonical = json.dumps(
        protocol.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _present(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def audit_protocol(body: ProtocolAuditRequest) -> dict:
    plan = body.protocol
    digest = protocol_sha256(plan)
    frozen = body.expected_frozen_sha256 is not None
    digest_ok = frozen and digest == body.expected_frozen_sha256
    blockers: list[str] = []
    if not frozen:
        blockers.append("No independently archived pre-commit protocol hash supplied")
    elif not digest_ok:
        blockers.append("Frozen preregistration digest mismatch: protocol was altered")
    for field, name in (
        (plan.preregistration_record_reference, "externally timestamped preregistration record"),
        (plan.numerical_convergence_report_reference, "solver convergence study"),
        (plan.independent_reviewer_reference, "independent reviewer record"),
        (plan.approved_test_safety_plan_reference, "qualified and approved physical-test safety plan"),
    ):
        if not _present(field):
            blockers.append(f"Missing {name}")
    roles = {h.role for h in plan.hardware}
    for role in ("airframe", "motor", "propeller", "esc", "battery", "controller"):
        if role not in roles:
            blockers.append(f"Missing actual hardware registration: {role}")
    for h in plan.hardware:
        if not _present(h.serial_or_lot) or not _present(h.geometry_or_firmware_revision):
            blockers.append(f"Missing hardware serial/revision: {h.role} {h.model}")

    instruments = {i.channel: i for i in plan.instruments}
    by_channel: dict[str, list[UncertaintyTerm]] = {}
    for term in plan.uncertainties:
        by_channel.setdefault(term.channel, []).append(term)
    uncertainty_report = {}
    for metric in plan.acceptance_metrics:
        ch = metric.channel
        instrument = instruments.get(ch)
        if instrument is None:
            blockers.append(f"Missing independent instrument for {ch}")
        else:
            if (not _present(instrument.serial)
                    or not _present(instrument.calibration_reference)
                    or instrument.calibration_date_utc is None
                    or instrument.bandwidth_hz is None
                    or instrument.clock_alignment_bound_s is None):
                blockers.append(f"Incomplete calibration, bandwidth or clock data for {ch}")
            elif instrument.bandwidth_hz < .5 / metric.maximum_sampling_gap_s:
                blockers.append(f"Instrument bandwidth insufficient for sampling interval on {ch}")

        terms = by_channel.get(ch, [])
        if not terms:
            blockers.append(f"Missing measurement uncertainty budget for {ch}")
        elif any(not _present(t.source_reference) for t in terms):
            blockers.append(f"Untraceable measurement uncertainty term for {ch}")
        hard_terms = [t.absolute_value for t in terms if t.type == "hard_absolute_bound"]
        standard_terms = [t for t in terms if t.type == "standard_uncertainty"]
        hard_bound = sum(hard_terms) if terms and not standard_terms else None
        if hard_bound is not None and not math.isfinite(hard_bound):
            blockers.append(f"Nonfinite accumulated measurement bound for {ch}")
            hard_bound = None
        if hard_bound is not None and hard_bound >= metric.maximum_absolute_prediction_error:
            blockers.append(f"Measurement bound alone exhausts prediction tolerance for {ch}")
        if standard_terms:
            blockers.append(f"No defensible deterministic hard error enclosure for {ch}: standard uncertainties require independent coverage model")
        uncertainty_report[ch] = {
            "unit": UNITS[ch],
            "predeclared_max_absolute_prediction_error": metric.maximum_absolute_prediction_error,
            "worst_case_hard_absolute_measurement_bound": hard_bound,
            "standard_term_count": len(standard_terms),
            "independent_measurement_error_budget_established": False,
            "note": "Operator-declared values are not calibrated or authenticated by AeroForge",
        }

    planned = {x.recording_id: x for x in plan.experiments}
    calibrations = [x for x in plan.experiments if x.role == "calibration"]
    holdouts = [x for x in plan.experiments if x.role == "holdout"]
    if not calibrations:
        blockers.append("No calibration experiment preregistered")
    if len(holdouts) < 2:
        blockers.append("At least two entire blind holdout experiments required")
    collisions = []
    for cal in calibrations:
        for hold in holdouts:
            same = [k for k in ("recording_id", "experiment_id", "battery_id", "vehicle_id")
                    if getattr(cal, k) == getattr(hold, k)]
            if same:
                collisions.append({"calibration_recording": cal.recording_id,
                                   "holdout_recording": hold.recording_id, "overlap": same})
    if collisions:
        blockers.append("Calibration/holdout physical groups overlap")

    imported_status = []
    seen = set()
    for manifest in body.imported_manifests:
        if manifest.dataset_id in seen:
            blockers.append(f"Duplicated imported dataset id {manifest.dataset_id}")
        seen.add(manifest.dataset_id)
        exp = planned.get(manifest.recording_id)
        reasons = []
        if exp is None:
            reasons.append("Recording was not preregistered")
        elif (exp.experiment_id != manifest.experiment_id
              or exp.vehicle_id != manifest.vehicle_id
              or exp.battery_id != manifest.battery_id
              or exp.role != manifest.partition_role):
            reasons.append("Imported experiment/vehicle/pack/partition differs from preregistration")
        if manifest.dataset_kind != "reported_physical_measurements":
            reasons.append("Source is not reported physical measurements")
        for metric in plan.acceptance_metrics:
            if metric.channel in ("terminal_voltage_v", "current_a", "temperature_c",
                                  "altitude_m", "vertical_speed_m_s", "wind_speed_m_s"):
                if metric.channel not in manifest.columns:
                    reasons.append(f"Missing predeclared channel {metric.channel}")
                if manifest.predeclared_max_sample_gap_s > metric.maximum_sampling_gap_s:
                    reasons.append(f"Looser sampling requirement on {metric.channel}")
                if manifest.expected_samples < metric.minimum_holdout_samples:
                    reasons.append(f"Insufficient samples for {metric.channel}")
        if reasons:
            blockers.append(f"Imported {manifest.dataset_id}: " + "; ".join(reasons))
        imported_status.append({
            "dataset_id": manifest.dataset_id,
            "matches_declared_protocol_metadata": not reasons,
            "gaps": reasons,
        })
    if not body.imported_manifests:
        blockers.append("No imported physical telemetry from registered tests")
    for hold in holdouts:
        if not any(m.recording_id == hold.recording_id for m in body.imported_manifests):
            blockers.append(f"No evidence for preregistered holdout {hold.recording_id}")

    status = ("FROZEN_PROTOCOL_TAMPERED" if frozen and not digest_ok
              else "PREREGISTRATION_GAPS" if blockers
              else "OPERATOR_DECLARED_PROTOCOL_COMPLETE_EXTERNAL_REVIEW_REQUIRED")
    return {
        "schema_version": "1.0", "protocol_id": plan.protocol_id,
        "canonical_protocol_sha256": digest,
        "matches_supplied_frozen_sha256": bool(digest_ok),
        "frozen_sha256_externally_authenticated": False,
        "readiness_status": status, "blockers": blockers,
        "uncertainty_budget": uncertainty_report,
        "holdout_group_collisions": collisions,
        "imported_recording_checks": imported_status,
        "independently_approved": False,
        "independent_physical_accuracy_demonstrated": False,
        "validated_operating_envelope": None,
        "decision_equivalent_to_physical_testing": False,
        "limitations": [
            "A hash proves content identity relative to supplied hash, not preregistration timing or author identity",
            "Operator input cannot authenticate instruments, permits, hardware or peer review",
            "A planned experiment is not independent measured prediction error",
            "Standard uncertainties require an appropriate propagation, correlation and coverage model",
            "No software audit can authorize physical testing or replace qualified safety review",
        ],
    }
