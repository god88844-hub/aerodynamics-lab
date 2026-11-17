"""M23 source-pinned controller-in-the-loop trace quality and tracking audit.

NO physical control-model validation. Commands and measured tracking are both
operator-reported; without an independently frozen *simulator prediction*
stream this is a descriptive controller-tracking calculation only.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from physics.validation.validation_protocol import ValidationProtocol, protocol_sha256

FIELDS = [
    "t_s", "command_roll_deg", "observed_roll_deg",
    "command_pitch_deg", "observed_pitch_deg", "saturation_flag",
]
MAX_SAMPLES = 50000


class HILRecording(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    dataset_kind: Literal["synthetic_fixture", "reported_physical_hil"]
    role: Literal["calibration", "holdout"]
    experiment_id: str = Field(min_length=1, max_length=120)
    recording_id: str = Field(min_length=1, max_length=120)
    vehicle_id: str = Field(min_length=1, max_length=120)
    battery_id: str = Field(min_length=1, max_length=120)
    controller_serial: str = Field(min_length=1, max_length=120)
    firmware_revision: str = Field(min_length=1, max_length=160)
    controller_configuration_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sensor_serial: str = Field(min_length=1, max_length=160)
    calibration_reference: str | None = Field(default=None, max_length=500)
    source_reference: str = Field(min_length=1, max_length=500)
    source_permission: str = Field(min_length=1, max_length=250)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_samples: int = Field(ge=6, le=MAX_SAMPLES)
    csv_text: str = Field(min_length=1, max_length=5_000_000)
    declared_max_sampling_gap_s: float = Field(gt=0, le=2)
    clock_alignment_error_bound_s: float | None = Field(default=None, ge=0, le=2)
    unused_for_calibration_self_reported: bool
    hardware_matches_frozen_controller_self_reported: bool

    @model_validator(mode="after")
    def check_names(self):
        for key in ("dataset_id", "experiment_id", "recording_id",
                    "vehicle_id", "battery_id", "controller_serial",
                    "firmware_revision", "sensor_serial", "source_reference",
                    "source_permission"):
            if not getattr(self, key).strip():
                raise ValueError(f"{key} cannot be blank")
        return self


class HILCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    frozen_protocol: ValidationProtocol
    expected_frozen_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    recordings: list[HILRecording] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def reject_duplicates(self):
        for key in ("dataset_id", "recording_id"):
            vals = [getattr(r, key) for r in self.recordings]
            if len(set(vals)) != len(vals):
                raise ValueError(f"duplicate {key} in controller test bundle")
        return self


def _read(record: HILRecording) -> tuple[list[dict], float]:
    raw = record.csv_text.encode("utf-8")
    if sha256(raw).hexdigest() != record.source_sha256:
        raise ValueError("original controller telemetry SHA-256 mismatch")
    try:
        rows = list(csv.reader(io.StringIO(record.csv_text, newline=""), strict=True))
    except csv.Error as exc:
        raise ValueError("malformed controller CSV quotation") from exc
    if not rows or rows[0] != FIELDS:
        raise ValueError("controller telemetry requires exact SI channel header")
    if len(rows) - 1 != record.expected_samples:
        raise ValueError("controller telemetry sample count differs from source manifest")
    values = []
    max_gap = 0.0
    previous = None
    for line, fields in enumerate(rows[1:], start=2):
        if len(fields) != len(FIELDS) or any(not value.strip() for value in fields):
            raise ValueError(f"row {line}: missing controller sensor value")
        try:
            nums = [float(v) for v in fields]
        except ValueError as exc:
            raise ValueError(f"row {line}: nonnumeric controller sample") from exc
        if not all(math.isfinite(v) for v in nums):
            raise ValueError(f"row {line}: nonfinite controller sample")
        t, rollcmd, rollobs, pitchcmd, pitchobs, saturation = nums
        if t < 0 or abs(rollcmd) > 180 or abs(rollobs) > 180 or abs(pitchcmd) > 180 or abs(pitchobs) > 180:
            raise ValueError(f"row {line}: physically unsupported time or attitude")
        if saturation not in (0, 1):
            raise ValueError(f"row {line}: saturation flag must be 0 or 1")
        if previous is None:
            if t != 0:
                raise ValueError("controller recording elapsed time must start at zero")
        else:
            gap = t - previous
            if gap <= 0:
                raise ValueError(f"row {line}: timestamps must strictly increase")
            max_gap = max(max_gap, gap)
        values.append(dict(zip(FIELDS, nums)))
        previous = t
    return values, max_gap


def audit_hil_campaign(body: HILCampaignRequest) -> dict:
    plan = body.frozen_protocol
    digest = protocol_sha256(plan)
    frozen = body.expected_frozen_sha256 is not None and body.expected_frozen_sha256 == digest
    blockers = []
    if not frozen:
        blockers.append("Frozen control test preregistration hash missing or modified")
    criteria = [m for m in plan.acceptance_metrics if m.channel == "attitude_error_deg"]
    if len(criteria) != 1:
        blockers.append("Exactly one frozen attitude tracking tolerance required")
    metric = criteria[0] if criteria else None
    if any(m.channel != "attitude_error_deg" for m in plan.acceptance_metrics):
        blockers.append("Other decision-critical outputs need separate physical prediction models")
    hard_terms = [u for u in plan.uncertainties if u.channel == "attitude_error_deg"]
    hard_bound = (sum(u.absolute_value for u in hard_terms)
                  if hard_terms and all(u.type == "hard_absolute_bound" and u.source_reference
                                        for u in hard_terms) else None)
    if hard_bound is None or not math.isfinite(hard_bound):
        blockers.append("Missing finite traceable hard attitude measurement uncertainty enclosure")
        hard_bound = None
    instrument = next((i for i in plan.instruments if i.channel == "attitude_error_deg"), None)
    if instrument is None or not all((
        instrument.serial, instrument.calibration_reference, instrument.calibration_date_utc,
        instrument.bandwidth_hz, instrument.clock_alignment_bound_s is not None,
    )):
        blockers.append("Missing authenticable attitude instrument serial, calibration or clock data")
    controllers = [h for h in plan.hardware if h.role == "controller"]
    if not controllers:
        blockers.append("No actual flight controller and firmware registered")
    registered = {e.recording_id: e for e in plan.experiments}
    calibration = [r for r in body.recordings if r.role == "calibration"]
    holdouts = [r for r in body.recordings if r.role == "holdout"]
    if not calibration or len(holdouts) < 2:
        blockers.append("Missing one calibration and two complete independent holdout recordings")
    collisions = []
    for a in calibration:
        for b in holdouts:
            shared = [name for name in (
                "experiment_id", "recording_id", "vehicle_id", "battery_id", "controller_serial",
                "sensor_serial", "source_sha256",
            ) if getattr(a, name) == getattr(b, name)]
            if shared:
                collisions.append({"calibration": a.dataset_id, "holdout": b.dataset_id,
                                   "shared_identifiers": shared})
    if collisions:
        blockers.append("Controller calibration and holdout hardware/source groups overlap")
    results = []
    all_declared_holdouts_compatible = bool(frozen and len(holdouts) >= 2 and not collisions and
                                            metric is not None and hard_bound is not None)
    for record in body.recordings:
        observed, max_gap = _read(record)
        reasons = []
        planned = registered.get(record.recording_id)
        if planned is None or (
            planned.experiment_id != record.experiment_id
            or planned.vehicle_id != record.vehicle_id
            or planned.battery_id != record.battery_id
            or planned.role != record.role
        ):
            reasons.append("Controller recording does not match frozen experiment registration")
        if not any(c.serial_or_lot == record.controller_serial
                   and c.geometry_or_firmware_revision == record.firmware_revision for c in controllers):
            reasons.append("Controller firmware and serial differ from frozen hardware")
        if record.controller_configuration_sha256 != plan.frozen_controller_configuration_sha256:
            reasons.append("Controller configuration digest differs from frozen protocol")
        if not record.hardware_matches_frozen_controller_self_reported:
            reasons.append("Controller hardware match not declared")
        if record.dataset_kind != "reported_physical_hil":
            reasons.append("Synthetic controller telemetry cannot physically validate control response")
        if record.role == "calibration":
            reasons.append("Calibration recording cannot serve as blind holdout")
        if record.role == "holdout" and not record.unused_for_calibration_self_reported:
            reasons.append("Holdout recording reportedly used for parameter fitting")
        if not record.calibration_reference or record.calibration_reference != (
            instrument.calibration_reference if instrument is not None else None
        ):
            reasons.append("Actual sensor calibration source not linked to frozen instrument")
        if record.clock_alignment_error_bound_s is None or record.clock_alignment_error_bound_s > 0:
            reasons.append("Clock alignment uncertainty prevents continuous-time tracking bound")
        if max_gap > record.declared_max_sampling_gap_s:
            reasons.append("Actual timestamp gaps exceed recorder-declared maximum")
        if metric is not None:
            if record.expected_samples < metric.minimum_holdout_samples:
                reasons.append("Insufficient samples for preregistered attitude criterion")
            if record.declared_max_sampling_gap_s > metric.maximum_sampling_gap_s:
                reasons.append("Recorder sampling bound looser than preregistered criterion")
            if max_gap > metric.maximum_sampling_gap_s:
                reasons.append("Actual sampling does not meet frozen interval limit")
        abs_errors = [max(abs(x["command_roll_deg"] - x["observed_roll_deg"]),
                          abs(x["command_pitch_deg"] - x["observed_pitch_deg"]))
                      for x in observed]
        max_error = max(abs_errors)
        rmse = math.sqrt(sum(e*e for e in abs_errors) / len(abs_errors))
        saturation_count = sum(x["saturation_flag"] == 1 for x in observed)
        uncertainty_upper = max_error + hard_bound if hard_bound is not None else None
        if uncertainty_upper is not None and not math.isfinite(uncertainty_upper):
            uncertainty_upper = None
            reasons.append("Nonfinite attitude error enclosure")
        compatible = bool(metric is not None and uncertainty_upper is not None
                          and uncertainty_upper <= metric.maximum_absolute_prediction_error)
        if not compatible:
            reasons.append("Observed attitude tracking exceeds or cannot establish frozen tolerance")
        if saturation_count:
            reasons.append("Actuator saturation event observed; control authority not independently validated")
        if record.role == "holdout" and reasons:
            all_declared_holdouts_compatible = False
        results.append({
            "dataset_id": record.dataset_id,
            "partition_role": record.role,
            "original_sha256_verified_against_user_manifest": record.source_sha256,
            "count": len(observed), "maximum_gap_s": max_gap,
            "max_roll_or_pitch_tracking_error_deg": max_error,
            "tracking_rmse_deg": rmse,
            "saturation_count": saturation_count,
            "samplewise_tracking_upper_bound_deg": uncertainty_upper,
            "samplewise_tracking_within_declared_limits": compatible,
            "blockers": reasons,
        })
    blockers.extend([
        "No independent simulator-predicted controller trajectory is compared to original measurements",
        "Command-vs-observation tracking does NOT measure AeroForge flight prediction error",
        "No independently authenticated hardware/firmware, instrumentation or physical safety approval",
        "Unmodeled sensor delay, disturbance rejection and actuator dynamics remain unvalidated",
    ])
    return {
        "status": "HIL_PHYSICAL_VALIDATION_NOT_ESTABLISHED",
        "protocol_sha256": digest,
        "matches_supplied_frozen_digest": frozen,
        "experiment_group_collisions": collisions,
        "run_count": len(results),
        "holdout_count": len(holdouts),
        "reported_samplewise_tracking_compatible_only": all_declared_holdouts_compatible,
        "runs": results, "blockers": list(dict.fromkeys(blockers)),
        "simulation_prediction_error_measured": False,
        "independent_controller_hardware_validation": False,
        "aircraft_flight_readiness": False,
        "components_or_flight_model_modified": False,
    }
