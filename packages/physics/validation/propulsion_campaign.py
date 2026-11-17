"""M22: read-only preregistered static propulsion source comparison.

The existing P80 manufacturer bench table is calibration, NOT an independent
holdout. This module reads operator-reported per-operating-point static
observations; it does not fit a model or authenticate test instruments,
serials, physical installation, safety, dynamics or rotor thermal limits.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from physics.propulsion.dataset import OutOfEnvelopeError, PowertrainDataset
from physics.validation.validation_protocol import ValidationProtocol, protocol_sha256

GF_TO_N = 0.00980665
HEADER = ["rpm", "voltage_v", "thrust_n", "current_a"]


class BenchRun(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    dataset_kind: Literal["synthetic_fixture", "reported_physical_measurements"]
    partition_role: Literal["calibration", "holdout"]
    recording_id: str = Field(min_length=1, max_length=120)
    experiment_id: str = Field(min_length=1, max_length=120)
    vehicle_id: str = Field(min_length=1, max_length=120)
    battery_id: str = Field(min_length=1, max_length=120)
    motor_serial: str = Field(min_length=1, max_length=120)
    propeller_serial: str = Field(min_length=1, max_length=120)
    esc_serial: str = Field(min_length=1, max_length=120)
    fixture_id: str = Field(min_length=1, max_length=120)
    source_reference: str = Field(min_length=1, max_length=500)
    source_permission: str = Field(min_length=1, max_length=200)
    fixture_description: str = Field(min_length=1, max_length=500)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    csv_text: str = Field(min_length=1, max_length=500000)
    hardware_match_self_reported: bool
    unused_for_model_calibration_self_reported: bool
    ambient_air_density_kg_m3: float | None = Field(default=None, gt=0)
    ambient_temperature_c: float | None = None

    @model_validator(mode="after")
    def check_whitespace(self):
        for key in ("recording_id", "experiment_id", "vehicle_id", "battery_id",
                    "motor_serial", "propeller_serial", "esc_serial", "fixture_id",
                    "source_reference", "source_permission", "fixture_description"):
            if not getattr(self, key).strip():
                raise ValueError(f"{key} cannot be blank")
        return self


class PropulsionCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    motor_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    propeller_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    frozen_protocol: ValidationProtocol
    expected_frozen_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    runs: list[BenchRun] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def unique_records(self):
        for key in ("dataset_id", "recording_id"):
            values = [getattr(r, key) for r in self.runs]
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate static bench {key}")
        return self


def read_static_bench(run: BenchRun) -> list[dict]:
    raw = run.csv_text.encode("utf-8")
    if sha256(raw).hexdigest() != run.source_sha256:
        raise ValueError(f"{run.dataset_id}: original steady bench CSV SHA-256 mismatch")
    try:
        entries = list(csv.reader(io.StringIO(run.csv_text, newline=""), strict=True))
    except csv.Error as exc:
        raise ValueError("malformed steady bench CSV quotation") from exc
    if not entries or entries[0] != HEADER:
        raise ValueError("steady bench CSV must have exactly rpm,voltage_v,thrust_n,current_a")
    values = entries[1:]
    if not 5 <= len(values) <= 500:
        raise ValueError("steady bench must have 5–500 operating points")
    parsed = []
    seen_rpms = set()
    for i, row in enumerate(values, start=2):
        if len(row) != 4 or any(not v.strip() for v in row):
            raise ValueError(f"row {i}: incomplete static bench observation")
        try:
            nums = [float(v) for v in row]
        except ValueError as exc:
            raise ValueError(f"row {i}: nonnumeric bench sample") from exc
        if not all(math.isfinite(v) and v > 0 for v in nums):
            raise ValueError(f"row {i}: nonfinite or nonpositive bench sample")
        if nums[0] in seen_rpms:
            raise ValueError(f"row {i}: duplicated RPM operating point")
        seen_rpms.add(nums[0])
        parsed.append(dict(zip(HEADER, nums)))
    return parsed


def _hard_bound(protocol: ValidationProtocol, channel: str) -> float | None:
    terms = [u for u in protocol.uncertainties if u.channel == channel]
    if not terms or any(t.type != "hard_absolute_bound" or not t.source_reference
                        for t in terms):
        return None
    bound = sum(t.absolute_value for t in terms)
    return bound if math.isfinite(bound) else None


def audit_propulsion_campaign(
    dataset: PowertrainDataset, body: PropulsionCampaignRequest,
) -> dict:
    if dataset.motor.id != body.motor_id:
        raise ValueError("motor model does not match frozen reference")
    digest = protocol_sha256(body.frozen_protocol)
    frozen = body.expected_frozen_sha256 is not None and digest == body.expected_frozen_sha256
    blockers: list[str] = []
    if not frozen:
        blockers.append("Missing or changed externally preregistered protocol digest")
    plan = body.frozen_protocol
    metrics = {x.channel: x for x in plan.acceptance_metrics}
    for ch in ("thrust_n", "current_a"):
        if ch not in metrics:
            blockers.append(f"Missing frozen absolute-error acceptance metric for {ch}")
        if _hard_bound(plan, ch) is None:
            blockers.append(f"No traceable hard absolute measurement-error bound for {ch}")
        instrument = next((i for i in plan.instruments if i.channel == ch), None)
        if instrument is None or not (
            instrument.serial and instrument.calibration_reference
            and instrument.calibration_date_utc and instrument.bandwidth_hz
        ):
            blockers.append(f"Missing complete instrument calibration for {ch}")
    for metric in plan.acceptance_metrics:
        if metric.channel not in ("thrust_n", "current_a"):
            blockers.append(f"Static RPM-conditioned model does not predict {metric.channel}")

    registrations = plan.hardware
    registered_motors = [
        h for h in registrations if h.role == "motor" and h.model == body.motor_id
    ]
    registered_props = [
        h for h in registrations if h.role == "propeller" and h.model == body.propeller_id
    ]
    if not registered_motors or not registered_props:
        blockers.append("Exact motor and propeller models are not registered in frozen hardware plan")
    planned = {e.recording_id: e for e in plan.experiments}
    calibration = [r for r in body.runs if r.partition_role == "calibration"]
    holdout = [r for r in body.runs if r.partition_role == "holdout"]
    if not calibration or len(holdout) < 2:
        blockers.append("At least one calibration and two full held-out bench recordings required")
    collisions = []
    for a in calibration:
        for b in holdout:
            equal = [
                key for key in ("experiment_id", "recording_id", "vehicle_id", "battery_id",
                                "motor_serial", "propeller_serial", "esc_serial", "fixture_id",
                                "source_sha256")
                if getattr(a, key) == getattr(b, key)
            ]
            if equal:
                collisions.append({
                    "calibration": a.dataset_id, "holdout": b.dataset_id,
                    "shared_groups": equal,
                })
    if collisions:
        blockers.append("Calibration/holdout bench hardware or source recording overlaps")

    runs = []
    all_samplewise = True
    for run in body.runs:
        observations = read_static_bench(run)
        reasons = []
        registered = planned.get(run.recording_id)
        if registered is None or (
            registered.experiment_id != run.experiment_id
            or registered.vehicle_id != run.vehicle_id
            or registered.battery_id != run.battery_id
            or registered.role != run.partition_role
        ):
            reasons.append("Bench experiment differs from preregistered plan")
        if not any(h.serial_or_lot == run.motor_serial for h in registered_motors):
            reasons.append("Motor serial missing from frozen hardware list")
        if not any(h.serial_or_lot == run.propeller_serial for h in registered_props):
            reasons.append("Propeller serial missing from frozen hardware list")
        if run.dataset_kind != "reported_physical_measurements":
            reasons.append("Numerical fixture is not physical evidence")
        if run.partition_role != "holdout":
            reasons.append("Calibration data cannot count as blind holdout")
        if run.partition_role == "holdout" and not run.unused_for_model_calibration_self_reported:
            reasons.append("Holdout reportedly used for model calibration")
        if not run.hardware_match_self_reported:
            reasons.append("Hardware installation match not established")
        if run.ambient_air_density_kg_m3 is None or run.ambient_temperature_c is None:
            reasons.append("Static experimental density/temperature unavailable")
        row_scores = []
        unsupported = []
        all_match = True
        reference_overlap = 0
        for idx, obs in enumerate(observations):
            if any(
                p.prop == dataset.prop_key and abs(p.rpm - obs["rpm"]) < 1e-6
                and abs(p.voltage_v - obs["voltage_v"]) < .1
                for p in dataset.motor.test_data
            ):
                reference_overlap += 1
            try:
                thrust = dataset.thrust_gf(obs["rpm"])
                current = dataset.current_a(obs["rpm"], obs["voltage_v"])
            except (OutOfEnvelopeError, ValueError) as exc:
                unsupported.append({"index": idx, "reason": str(exc)})
                all_match = False
                continue
            if (current.voltage_extrapolated or
                    not math.isfinite(thrust.value) or not math.isfinite(current.value)
                    or thrust.value <= 0 or current.value <= 0):
                unsupported.append({
                    "index": idx, "reason": "unsupported voltage or nonphysical prediction",
                })
                all_match = False
                continue
            pred_t = thrust.value * GF_TO_N
            pred_i = current.value
            abs_t = abs(pred_t - obs["thrust_n"])
            abs_i = abs(pred_i - obs["current_a"])
            if not all(math.isfinite(x) for x in (abs_t, abs_i)):
                unsupported.append({"index": idx, "reason": "numeric residual overflow"})
                all_match = False
                continue
            upper_t = abs_t + (_hard_bound(plan, "thrust_n") or 0)
            upper_i = abs_i + (_hard_bound(plan, "current_a") or 0)
            if not all(math.isfinite(x) for x in (upper_t, upper_i)):
                unsupported.append({"index": idx, "reason": "numeric bound overflow"})
                all_match = False
                continue
            row_scores.append({
                "rpm": obs["rpm"], "voltage_v": obs["voltage_v"],
                "measured_thrust_n": obs["thrust_n"], "reference_thrust_n": pred_t,
                "measured_current_a": obs["current_a"], "reference_current_a": pred_i,
                "abs_thrust_residual_n": abs_t, "abs_current_residual_a": abs_i,
                "samplewise_thrust_upper_n": upper_t if _hard_bound(plan, "thrust_n") is not None else None,
                "samplewise_current_upper_a": upper_i if _hard_bound(plan, "current_a") is not None else None,
            })
            if (metrics.get("thrust_n") is None or metrics.get("current_a") is None
                    or _hard_bound(plan, "thrust_n") is None
                    or _hard_bound(plan, "current_a") is None
                    or upper_t > metrics["thrust_n"].maximum_absolute_prediction_error
                    or upper_i > metrics["current_a"].maximum_absolute_prediction_error):
                all_match = False
        if unsupported:
            reasons.append("Unsupported points cannot be cherry-picked from bench envelope")
        if not all_match:
            reasons.append("Reported thrust/current discrepancy exceeds or cannot demonstrate bounds")
        if run.partition_role == "holdout" and (reasons or not all_match):
            all_samplewise = False
        runs.append({
            "dataset_id": run.dataset_id,
            "role": run.partition_role,
            "source_sha256_verified_against_operator_declaration": run.source_sha256,
            "original_point_count": len(observations),
            "scored_count": len(row_scores),
            "unsupported": unsupported,
            "overlaps_reference_manufacturer_operating_points": reference_overlap,
            "rows": row_scores,
            "samplewise_compatible": all_match and not unsupported,
            "blockers": reasons,
        })
    if not all_samplewise:
        blockers.append("Not every holdout supports a complete, bounded static comparison")
    if any(r.dataset_kind != "reported_physical_measurements" for r in body.runs):
        blockers.append("Synthetic recordings are not independent physical tests")
    blockers.extend([
        "Benches/fixtures, instrument calibration and true blind independence are operator declared, not authenticated",
        "Unmeasured installation/air-density/temperature effects not corrected or validated",
        "Static plateau comparisons cannot validate motor/ESC thermal, transient or full aircraft behavior",
    ])
    return {
        "motor_id": body.motor_id, "propeller_id": body.propeller_id,
        "status": "PHYSICAL_PROPULSION_VALIDATION_NOT_ESTABLISHED",
        "protocol_sha256": digest,
        "matches_supplied_frozen_protocol_digest": frozen,
        "calibration_holdout_collisions": collisions,
        "run_count": len(runs),
        "holdout_count": len(holdout),
        "all_holdout_samples_compatible_declared_bounds_only": all_samplewise,
        "runs": runs, "blockers": list(dict.fromkeys(blockers)),
        "manufacturer_reference_is_calibration_not_validation": True,
        "independent_static_propulsion_validation_established": False,
        "dynamic_propulsion_validation_established": False,
        "flight_readiness_established": False,
        "model_or_components_modified": False,
    }
