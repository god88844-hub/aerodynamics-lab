"""M13: compare immutable simulation-run telemetry with operator-supplied flight logs.

This is prediction error analysis, not calibration or certification. Sources,
independence, clock synchronization, and vehicle identity are self-declared.
No input logs are saved and no flight model is changed.
"""
from __future__ import annotations

from hashlib import sha256
import math
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CHANNELS: dict[str, tuple[str, str]] = {
    "altitude_m": ("z", "m"),
    "vertical_speed_m_s": ("vz", "m/s"),
    "bus_voltage_v": ("v_bus_v", "V"),
    "battery_current_a": ("motor_current_a", "A"),
}


class FlightObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    t_s: float = Field(ge=0)
    altitude_m: float | None = None
    vertical_speed_m_s: float | None = None
    bus_voltage_v: float | None = Field(default=None, gt=0)
    battery_current_a: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_measurement(self) -> "FlightObservation":
        if all(getattr(self, field) is None for field in CHANNELS):
            raise ValueError("every timestamp must have at least one measured channel")
        return self


class FlightEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    dataset_kind: Literal["physical_measurements", "synthetic_fixture"]
    vehicle_id: str = Field(min_length=1, max_length=120)
    flight_log_id: str = Field(min_length=1, max_length=120)
    log_source: str = Field(min_length=1, max_length=500)
    hardware_matches_simulated_design: bool
    unused_for_model_calibration: bool
    # Explicitly declared (not optimized by the service). The measurement
    # clock is assumed to start at simulated t=0 after applying the offset.
    measurement_to_sim_time_offset_s: float = Field(ge=-60, le=60)
    # Absolute maximum acceptable error for each measured channel, SI units.
    tolerances: dict[Literal[
        "altitude_m", "vertical_speed_m_s", "bus_voltage_v", "battery_current_a"
    ], float] = Field(min_length=1, max_length=4)
    observations: list[FlightObservation] = Field(min_length=5, max_length=1000)
    # Optional, operator-supplied HARD absolute error bounds (not 1-sigma
    # estimates). Their provenance is not authenticated by AeroForge.
    measurement_error_bounds: dict[Literal[
        "altitude_m", "vertical_speed_m_s", "bus_voltage_v", "battery_current_a"
    ], float] | None = None
    clock_error_bound_s: float = Field(default=0.0, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def validate_metadata_and_time(self) -> "FlightEvidenceRequest":
        if not all(v.strip() for v in (self.vehicle_id, self.flight_log_id, self.log_source)):
            raise ValueError("vehicle ID, flight log ID and data source must not be blank")
        timestamps = [p.t_s for p in self.observations]
        if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
            raise ValueError("flight log timestamps must be strictly increasing")
        present = {key for p in self.observations for key in CHANNELS if getattr(p, key) is not None}
        if set(self.tolerances) != present:
            raise ValueError("predeclared tolerances must exactly match measured channels")
        for key, value in self.tolerances.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key}: tolerance must be finite and positive")
        if any(sum(getattr(p, key) is not None for p in self.observations) < 5 for key in present):
            raise ValueError("each measured channel needs at least five observations")
        if self.measurement_error_bounds is None:
            if self.clock_error_bound_s != 0:
                raise ValueError("clock bound requires measurement error bounds")
        else:
            if set(self.measurement_error_bounds) != present:
                raise ValueError("absolute measurement error bounds must cover exactly the measured channels")
            for key, value in self.measurement_error_bounds.items():
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"{key}: measurement bound must be finite and nonnegative")
        return self


def _uncertainty_assessment(
    comparison: dict[str, dict],
    times: list[float],
    predictions: dict[str, list[float]],
    body: FlightEvidenceRequest,
) -> dict:
    """Conservative error enclosure without a Gaussian assumption.

    Bound on true prediction residual is [max(0, abs(pred-measured)-U),
    abs(pred-measured)+U]. Here U adds the declared sensor absolute error
    and a local Lipschitz slope bound for timestamp error. If the entire
    clock interval is not covered by stored predictions, no robust pass.
    """
    from bisect import bisect_left

    if body.measurement_error_bounds is None:
        return {"status": "NOT_REQUESTED", "channels": {},
                "independently_authenticated": False}
    channel_summaries = {}
    all_pass = True
    any_definite_fail = False
    for name, info in comparison.items():
        values = predictions[name]
        bound = body.measurement_error_bounds[name]
        tolerance = body.tolerances[name]
        row_results = []
        for row in info["rows"]:
            t = row["time_s"]
            delta = body.clock_error_bound_s
            # The whole declared time-error interval must be in the
            # prediction record; clipping makes a false positive possible.
            supported = (t - delta >= times[0] and t + delta <= times[-1])
            if supported:
                lo, hi = t - delta, t + delta
                left = max(0, bisect_left(times, lo) - 1)
                right = min(len(times) - 2, bisect_left(times, hi))
                max_slope = max(
                    abs((values[k + 1] - values[k]) / (times[k + 1] - times[k]))
                    for k in range(left, right + 1)
                )
                total_bound = bound + max_slope * delta
                lower = max(0.0, abs(row["residual"]) - total_bound)
                upper = abs(row["residual"]) + total_bound
                disposition = ("ROBUST_PASS" if upper <= tolerance
                               else "ROBUST_FAIL" if lower > tolerance
                               else "INDETERMINATE")
            else:
                total_bound = None
                lower = None
                upper = None
                disposition = "CLOCK_ENVELOPE_UNSUPPORTED"
            row_results.append({
                "time_s": t,
                "measured": row["measured"],
                "predicted": row["predicted"],
                "absolute_measured_residual": abs(row["residual"]),
                "conservative_error_bound": total_bound,
                "minimum_possible_absolute_error": lower,
                "maximum_possible_absolute_error": upper,
                "disposition": disposition,
            })
        dispositions = [row["disposition"] for row in row_results]
        channel_pass = all(d == "ROBUST_PASS" for d in dispositions)
        definite_fail = any(d == "ROBUST_FAIL" for d in dispositions)
        all_pass = all_pass and channel_pass
        any_definite_fail = any_definite_fail or definite_fail
        channel_summaries[name] = {
            "unit": info["unit"],
            "declared_absolute_measurement_bound": bound,
            "tolerance": tolerance,
            "all_samples_robust_pass": channel_pass,
            "any_robust_failure": definite_fail,
            "rows": row_results,
        }
    status = ("ROBUST_FAIL_UNDER_DECLARED_BOUNDS" if any_definite_fail
              else "ROBUST_PASS_UNDER_DECLARED_BOUNDS" if all_pass
              else "INDETERMINATE_UNDER_DECLARED_BOUNDS")
    return {
        "status": status,
        "channels": channel_summaries,
        "clock_error_bound_s": body.clock_error_bound_s,
        "independently_authenticated": False,
        "meaning": "bounded consistency of sampled predictions, not physical validation or certification",
    }


def _prediction_series(telemetry: dict, name: str, size: int) -> list[float]:
    """Produce model outputs in operator-facing NED-derived conventions.

    NED z points DOWN and NED vz is positive downward; measured altitude and
    vertical velocity are explicitly defined positive UP from the takeoff origin.
    """
    field, _unit = CHANNELS[name]
    values = telemetry.get(field)
    if not isinstance(values, list) or len(values) != size:
        raise ValueError(f"simulation lacks a consistent {name} prediction channel")
    if name == "battery_current_a":
        if not all(isinstance(v, list) and v and all(_finite(x) and x >= 0 for x in v)
                   for v in values):
            raise ValueError("simulated motor-current arrays are absent or malformed")
        return [float(sum(v)) for v in values]
    if not all(_finite(v) for v in values):
        raise ValueError(f"simulation {field} contains nonfinite or nonnumeric data")
    if name == "bus_voltage_v" and any(v <= 0 for v in values):
        raise ValueError("simulation bus-voltage series contains invalid values")
    factor = -1 if name in ("altitude_m", "vertical_speed_m_s") else 1
    return [float(factor * v) for v in values]


def _finite(value: object) -> bool:
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def _interpolated(times: list[float], values: list[float], t: float) -> tuple[float, float]:
    """Linear interpolation within two recorded solver samples; no extrapolation.

    Returns the interpolated value and its source sample spacing (seconds).
    """
    from bisect import bisect_left

    pos = bisect_left(times, t)
    if pos == len(times):
        if t == times[-1]:
            return values[-1], 0.0
        raise ValueError("flight log timestamp is after simulated mission")
    if times[pos] == t:
        return values[pos], 0.0
    if pos == 0:
        raise ValueError("flight log timestamp is before simulated mission")
    dt = times[pos] - times[pos - 1]
    if dt <= 0:
        raise ValueError("simulation time samples must increase")
    frac = (t - times[pos - 1]) / dt
    return values[pos - 1] + frac * (values[pos] - values[pos - 1]), dt


def _channel_metrics(rows: list[dict], tolerance: float) -> dict:
    residuals = [r["predicted"] - r["measured"] for r in rows]
    n = len(residuals)
    abs_err = sorted(abs(e) for e in residuals)
    return {
        "count": n,
        "mae": mean(abs_err),
        "rmse": math.sqrt(mean(e * e for e in residuals)),
        "bias": mean(residuals),
        "max_absolute_error": abs_err[-1],
        "predeclared_max_absolute_error": tolerance,
        "meets_predeclared_tolerance": abs_err[-1] <= tolerance,
    }


def evaluate_flight_evidence(
    simulation_report: dict, body: FlightEvidenceRequest, *,
    simulation_id: int, design_id: int, scenario: str, saved_result_json: str,
) -> dict:
    """Score a stored *pre-existing* flight run; report never alters it."""
    if simulation_report.get("status") != "completed" or not scenario.startswith("flight"):
        raise ValueError("flight evidence requires a successful stored flight simulation")
    mission = simulation_report.get("mission")
    success = simulation_report.get("success")
    if not isinstance(mission, dict) or not isinstance(success, dict) or not success:
        raise ValueError("stored flight report lacks mission outcome and success criteria")
    if not isinstance(mission.get("aborted"), bool) or any(
        not isinstance(outcome, bool) for outcome in success.values()
    ):
        raise ValueError("stored mission outcomes must be explicit booleans")
    mission_succeeded = not mission["aborted"] and all(success.values())
    tel = simulation_report.get("telemetry")
    if not isinstance(tel, dict):
        raise ValueError("stored flight simulation has no telemetry")
    times = tel.get("t")
    if not isinstance(times, list) or len(times) < 2 or not all(_finite(t) for t in times):
        raise ValueError("stored simulation has no finite telemetry clock")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("stored simulation time samples must strictly increase")
    total_duration = times[-1] - times[0]
    if total_duration <= 0:
        raise ValueError("stored simulated mission duration must be positive")
    shifted_times = [p.t_s + body.measurement_to_sim_time_offset_s for p in body.observations]
    if shifted_times[0] < times[0] - 1e-9 or shifted_times[-1] > times[-1] + 1e-9:
        raise ValueError("flight log times fall outside stored simulation (no extrapolation)")

    comparison: dict[str, dict] = {}
    predictions: dict[str, list[float]] = {}
    max_spacing = max(b - a for a, b in zip(times, times[1:]))
    for name, tolerance in body.tolerances.items():
        prediction = _prediction_series(tel, name, len(times))
        predictions[name] = prediction
        rows = []
        for sample, t in zip(body.observations, shifted_times):
            measurement = getattr(sample, name)
            if measurement is None:
                continue
            estimate, _gap = _interpolated(times, prediction, max(times[0], min(t, times[-1])))
            rows.append({
                "time_s": t,
                "measured": measurement,
                "predicted": estimate,
                "residual": estimate - measurement,
            })
        comparison[name] = {
            "unit": CHANNELS[name][1],
            "metrics": _channel_metrics(rows, tolerance),
            "rows": rows,
        }

    uncertainty_assessment = _uncertainty_assessment(comparison, times, predictions, body)
    coverage = (shifted_times[-1] - shifted_times[0]) / total_duration
    # Report cadence and coverage as explicit applicability checks. Sparse
    # points can look perfect while omitting takeoff or landing completely.
    min_coverage = 0.8
    # 1-second gaps in downsampled predictions would hide rapid transient
    # behavior; reject the claim rather than manufacturing a smooth line.
    max_allowed_prediction_spacing_s = 0.5
    adequate = coverage >= min_coverage
    interpolation_supported = max_spacing <= max_allowed_prediction_spacing_s
    threshold_met = all(s["metrics"]["meets_predeclared_tolerance"] for s in comparison.values())

    if body.dataset_kind == "synthetic_fixture":
        verdict = "SYNTHETIC_VERIFICATION_ONLY"
    elif not mission_succeeded:
        verdict = "SIMULATED_MISSION_FAILED_OR_ABORTED"
    elif not body.hardware_matches_simulated_design:
        verdict = "UNCONFIRMED_HARDWARE_CONFIGURATION"
    elif not body.unused_for_model_calibration:
        verdict = "CALIBRATION_DATA_NOT_INDEPENDENT_VALIDATION"
    elif not adequate:
        verdict = "INSUFFICIENT_FLIGHT_COVERAGE"
    elif not interpolation_supported:
        verdict = "UNSUPPORTED_PREDICTION_SAMPLING_GAP"
    elif not threshold_met:
        verdict = "REPORTED_FLIGHT_ERROR_TOLERANCE_NOT_MET"
    elif body.measurement_error_bounds is not None and uncertainty_assessment["status"] != "ROBUST_PASS_UNDER_DECLARED_BOUNDS":
        verdict = "UNCERTAINTY_AWARE_TOLERANCE_NOT_DEMONSTRATED"
    else:
        verdict = "REPORTED_FLIGHT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"

    return {
        "simulation_id": simulation_id,
        "design_id": design_id,
        "scenario": scenario,
        "stored_prediction_sha256": sha256(saved_result_json.encode("utf-8")).hexdigest(),
        "dataset_kind": body.dataset_kind,
        "provenance": {
            "vehicle_id": body.vehicle_id,
            "flight_log_id": body.flight_log_id,
            "log_source": body.log_source,
            "hardware_match_self_reported": body.hardware_matches_simulated_design,
            "unused_for_calibration_self_reported": body.unused_for_model_calibration,
            "measurement_to_sim_time_offset_s": body.measurement_to_sim_time_offset_s,
            "independence_and_instrumentation_not_authenticated": True,
        },
        "coverage": {
            "observations": len(body.observations),
            "mission_fraction": coverage,
            "minimum_required_fraction": min_coverage,
            "adequate": adequate,
            "max_interpolation_spacing_s": max_spacing,
            "maximum_supported_spacing_s": max_allowed_prediction_spacing_s,
            "interpolation_supported": interpolation_supported,
        },
        "channels": comparison,
        "uncertainty_assessment": uncertainty_assessment,
        "all_predeclared_tolerances_met": threshold_met,
        "simulated_mission_succeeded": mission_succeeded,
        "verdict": verdict,
        "simulation_modified": False,
        "limitations": [
            "Real flight logs and vehicle matches are operator-declared, not authenticated",
            "Any previously calibrated/used data are not independent validation",
            "Timestamp origin and synchronization are operator-declared; no automatic alignment or phase shift is fitted",
            "Altitude is relative to takeoff and positive up; no GPS datum or sensor bias is corrected",
            "Battery current sums modeled motor currents and may omit auxiliary loads or ESC losses",
            "Linear interpolation between recorded simulator samples is not a higher-fidelity solution",
            "Reported prediction match does not override failed or aborted simulated mission criteria",
            "Only reported sampled channels and conditions are scored, not full flight safety or unseen failures",
            "Uncertainty bounds (if provided) are operator-declared and not independently established or calibrated",
            "Uncertainty-aware envelopes bound sampled residuals only, assuming declared hard absolute sensor and timing error bounds",
            "No independent replicated test coverage or sensor calibration is established",
            "Comparison cannot certify an aircraft or quantify the probability of real-world mission success",
            "No model calibration or mutation of saved results is performed",
        ],
    }
