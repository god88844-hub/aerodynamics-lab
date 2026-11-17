"""M23 read-only controller/HIL trajectory comparison with immutable evidence.

Observations and predictions must be supplied as distinct SHA-256 pinned CSVs.
This module *never* authenticates sensors or firmware, commands hardware, fits
models, or claims independent aircraft/flight-controller physical validation.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import math
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from physics.validation.validation_protocol import (
    ValidationProtocol, protocol_sha256,
)

CHANNELS = ("altitude_m", "vertical_speed_m_s", "attitude_error_deg")
MAX_BYTES = 2_000_000
MAX_POINTS = 5000


class HILRecording(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    dataset_kind: Literal["synthetic_fixture", "reported_physical_measurements"]
    role: Literal["calibration", "holdout"]
    experiment_id: str = Field(min_length=1, max_length=120)
    recording_id: str = Field(min_length=1, max_length=120)
    vehicle_id: str = Field(min_length=1, max_length=120)
    battery_id: str = Field(min_length=1, max_length=120)
    controller_serial: str = Field(min_length=1, max_length=120)
    firmware_version: str = Field(min_length=1, max_length=120)
    controller_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_reference: str = Field(min_length=1, max_length=500)
    instrument_reference: str = Field(min_length=1, max_length=500)
    hardware_match_self_reported: bool
    unused_for_calibration_self_reported: bool
    observation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prediction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_csv: str = Field(min_length=1, max_length=MAX_BYTES)
    predicted_csv: str = Field(min_length=1, max_length=MAX_BYTES)

    @model_validator(mode="after")
    def check_identifiers(self):
        for name in ("experiment_id", "recording_id", "vehicle_id", "battery_id",
                     "controller_serial", "firmware_version", "source_reference",
                     "instrument_reference"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be blank")
        return self


class HILCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    frozen_protocol: ValidationProtocol
    expected_frozen_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    channels: list[Literal["altitude_m", "vertical_speed_m_s", "attitude_error_deg"]] = Field(
        min_length=1, max_length=len(CHANNELS),
    )
    runs: list[HILRecording] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def check_runs(self):
        if len(set(self.channels)) != len(self.channels):
            raise ValueError("duplicate comparison channel")
        for field in ("dataset_id", "recording_id"):
            keys = [getattr(r, field) for r in self.runs]
            if len(keys) != len(set(keys)):
                raise ValueError(f"duplicate {field}")
        return self


def _read_csv(data: str, digest: str, selected: list[str], *, name: str) -> list[dict]:
    raw = data.encode("utf-8")
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError(f"{name}: over byte limit")
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"{name}: original SHA-256 mismatch")
    try:
        reader = list(csv.reader(io.StringIO(data, newline=""), strict=True))
    except csv.Error as exc:
        raise ValueError(f"{name}: malformed quoted CSV") from exc
    if not reader or reader[0] != ["t_s", *selected]:
        raise ValueError(f"{name}: CSV header does not match declared channel order")
    if not 6 <= len(reader) - 1 <= MAX_POINTS:
        raise ValueError(f"{name}: expected 6–5000 rows")
    parsed = []
    last_t = None
    for row_number, row in enumerate(reader[1:], start=2):
        if len(row) != len(selected) + 1 or any(not value.strip() for value in row):
            raise ValueError(f"{name}: row {row_number} incomplete")
        try:
            nums = [float(value) for value in row]
        except ValueError as exc:
            raise ValueError(f"{name}: row {row_number} not numeric") from exc
        if not all(math.isfinite(v) for v in nums):
            raise ValueError(f"{name}: row {row_number} nonfinite")
        t = nums[0]
        if (last_t is None and t != 0) or (last_t is not None and t <= last_t):
            raise ValueError(f"{name}: timestamps must start at zero and strictly increase")
        if "attitude_error_deg" in selected:
            attitude = nums[1 + selected.index("attitude_error_deg")]
            if not 0 <= attitude <= 180:
                raise ValueError(f"{name}: attitude-error magnitude outside [0,180] degrees")
        last_t = t
        parsed.append(dict(zip(["t_s", *selected], nums)))
    return parsed


def audit_hil_campaign(body: HILCampaignRequest) -> dict:
    """Screen reported trajectory agreement, never grant airworthiness or hardware validation."""
    plan = body.frozen_protocol
    digest = protocol_sha256(plan)
    frozen = body.expected_frozen_sha256 is not None and digest == body.expected_frozen_sha256
    blockers = []
    if not frozen:
        blockers.append("Missing or altered separately archived preregistration digest")
    if not any(h.role == "controller" and h.serial_or_lot for h in plan.hardware):
        blockers.append("No serial-identified controller in frozen hardware plan")
    metrics = {m.channel: m for m in plan.acceptance_metrics}
    sources = {}
    for channel in body.channels:
        metric = metrics.get(channel)
        if metric is None:
            blockers.append(f"No preregistered acceptance metric for {channel}")
        instrument = next((i for i in plan.instruments if i.channel == channel), None)
        if instrument is None or not (instrument.serial and instrument.calibration_reference
                                       and instrument.calibration_date_utc and instrument.bandwidth_hz
                                       and instrument.clock_alignment_bound_s is not None):
            blockers.append(f"Missing traceable calibrated instrument for {channel}")
        terms = [u for u in plan.uncertainties if u.channel == channel]
        if not terms or any(u.type != "hard_absolute_bound" or not u.source_reference
                            for u in terms):
            sources[channel] = None
            blockers.append(f"Missing traceable hard measurement bounds for {channel}")
        else:
            bound = sum(u.absolute_value for u in terms)
            sources[channel] = bound if math.isfinite(bound) else None
            if sources[channel] is None:
                blockers.append(f"Nonfinite accumulated error bound for {channel}")
        if instrument and instrument.clock_alignment_bound_s:
            blockers.append(
                f"Unpropagated positive clock uncertainty for {channel}; samplewise only"
            )

    calibration = [run for run in body.runs if run.role == "calibration"]
    holdout = [run for run in body.runs if run.role == "holdout"]
    if not calibration or len(holdout) < 2:
        blockers.append("Require at least one calibration and two independent whole-run holdouts")
    collisions = []
    for a in calibration:
        for b in holdout:
            shared = [k for k in ("recording_id", "experiment_id", "vehicle_id", "battery_id",
                                  "controller_serial", "observation_sha256")
                      if getattr(a, k) == getattr(b, k)]
            if shared:
                collisions.append({
                    "calibration_dataset": a.dataset_id,
                    "holdout_dataset": b.dataset_id,
                    "shared_groups": shared,
                })
    if collisions:
        blockers.append("Calibrating and held-out recordings share source or hardware groups")
    registered = {e.recording_id: e for e in plan.experiments}
    controller_serials = {
        h.serial_or_lot for h in plan.hardware if h.role == "controller"
    }
    results = []
    all_compatible = len(holdout) >= 2 and bool(calibration) and not collisions
    for run in body.runs:
        observed = _read_csv(
            run.observed_csv, run.observation_sha256, body.channels, name="observations"
        )
        predicted = _read_csv(
            run.predicted_csv, run.prediction_sha256, body.channels, name="predictions"
        )
        reasons = []
        if len(observed) != len(predicted) or any(
            obs["t_s"] != pred["t_s"] for obs, pred in zip(observed, predicted)
        ):
            reasons.append("Prediction and observation clocks are not exactly aligned")
        if run.controller_config_sha256 != plan.frozen_controller_configuration_sha256:
            reasons.append("Controller config differs from frozen model")
        if run.controller_serial not in controller_serials:
            reasons.append("Controller serial is absent from preregistration")
        registration = registered.get(run.recording_id)
        if (registration is None or registration.experiment_id != run.experiment_id
            or registration.vehicle_id != run.vehicle_id
            or registration.battery_id != run.battery_id
            or registration.role != run.role):
            reasons.append("Recording metadata differs from preregistered experiment")
        if run.dataset_kind != "reported_physical_measurements":
            reasons.append("Synthetic source does not establish physical accuracy")
        if not run.hardware_match_self_reported:
            reasons.append("Hardware identity/match not declared")
        if run.role == "holdout" and not run.unused_for_calibration_self_reported:
            reasons.append("Holdout reportedly used for calibration")
        if run.role != "holdout":
            reasons.append("Calibration source is not a blind holdout")
        scores = {}
        if len(observed) == len(predicted) and all(
            obs["t_s"] == pred["t_s"] for obs, pred in zip(observed, predicted)
        ):
            gaps = [b["t_s"] - a["t_s"] for a, b in zip(observed, observed[1:])]
            for channel in body.channels:
                metric = metrics.get(channel)
                residuals = [p[channel] - o[channel] for p, o in zip(predicted, observed)]
                if not all(math.isfinite(r) and abs(r) <= 1e100 for r in residuals):
                    reasons.append(f"Nonfinite or unstable model residual for {channel}")
                    continue
                max_gap = max(gaps)
                mae = mean(abs(r) for r in residuals)
                rmse = math.sqrt(mean(r * r for r in residuals))
                max_abs = max(abs(r) for r in residuals)
                bound = sources[channel]
                upper = max_abs + bound if bound is not None else None
                if upper is not None and not math.isfinite(upper):
                    upper = None
                enough = metric is not None and len(observed) >= metric.minimum_holdout_samples
                dense = metric is not None and max_gap <= metric.maximum_sampling_gap_s
                compatible = bool(
                    metric is not None and bound is not None and upper is not None
                    and enough and dense and upper <= metric.maximum_absolute_prediction_error
                )
                if not compatible and run.role == "holdout":
                    reasons.append(f"Undemonstrated preregistered bounds or sampling for {channel}")
                scores[channel] = {
                    "unit": "m" if channel == "altitude_m" else (
                        "m/s" if channel == "vertical_speed_m_s" else "deg"
                    ),
                    "sample_count": len(observed), "maximum_sample_gap_s": max_gap,
                    "mae": mae, "rmse": rmse, "max_absolute_residual": max_abs,
                    "declared_samplewise_upper_bound": upper,
                    "within_declared_samplewise_tolerance": compatible,
                    "clock_and_model_form_error_enclosed": False,
                }
        if run.role == "holdout" and (reasons or len(scores) != len(body.channels)):
            all_compatible = False
        results.append({
            "dataset_id": run.dataset_id, "role": run.role,
            "original_observation_sha256_checked_against_operator_manifest": run.observation_sha256,
            "original_model_prediction_sha256_checked_against_operator_manifest": run.prediction_sha256,
            "rows": len(observed), "channel_errors": scores, "blockers": reasons,
        })
    if not all_compatible:
        blockers.append("Holdout samplewise comparison unsupported or mismatched")
    blockers += [
        "Actual sensor provenance, firmware and independent calibration are not authenticated",
        "External controller clock drift, actuator dynamics and model-form error remain unbounded",
        "Input CSVs are operator-declared and not independently attested",
    ]
    return {
        "status": "HIL_CONTROLLER_PHYSICAL_VALIDATION_NOT_ESTABLISHED",
        "frozen_protocol_sha256": digest,
        "matches_supplied_preregistration_digest": frozen,
        "calibration_holdout_collisions": collisions,
        "all_reported_holdouts_compatible_declared_samplewise_bounds": bool(
            all_compatible and frozen and all(
                run.dataset_kind == "reported_physical_measurements" for run in body.runs
            )
        ),
        "runs": results,
        "blockers": list(dict.fromkeys(blockers)),
        "simulation_only_test_mode": all(run.dataset_kind == "synthetic_fixture" for run in body.runs),
        "actual_hardware_in_loop_experiment_performed_by_software": False,
        "independent_physical_flight_validation_established": False,
        "flight_safety_certified": False,
        "model_parameters_changed": False,
        "commands_sent_to_hardware": False,
    }
