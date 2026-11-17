"""M15: read-only discharge trace replay with measured charge and energy accounting.

Uses measured current as an externally supplied load, not a flight prediction.
Real-world predictive validation remains impossible without independently
authenticated, pack-specific traces and instrument uncertainties.
"""
from __future__ import annotations

import math
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import BatteryPack


class DischargePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    t_s: float = Field(ge=0)
    current_a: float = Field(ge=0)
    terminal_voltage_v: float = Field(gt=0)
    temperature_c: float | None = None


class DischargeReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    battery_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    dataset_kind: Literal["physical_measurements", "synthetic_fixture"]
    battery_serial_or_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)
    data_source: str = Field(min_length=1, max_length=500)
    model_unused_for_calibration: bool
    hardware_matches_reference_spec: bool
    initial_soc_pct: float = Field(gt=0, le=100)
    predeclared_max_abs_voltage_error_v: float = Field(gt=0, le=100)
    predeclared_max_endpoint_time_error_pct: float = Field(gt=0, le=100)
    predeclared_max_sample_gap_s: float = Field(gt=0, le=300)
    samples: list[DischargePoint] = Field(min_length=6, max_length=10000)

    @model_validator(mode="after")
    def validate_record(self) -> "DischargeReplayRequest":
        if not all(x.strip() for x in (self.battery_serial_or_id, self.run_id, self.data_source)):
            raise ValueError("battery ID, run ID and source cannot be blank")
        if self.samples[0].t_s != 0:
            raise ValueError("discharge trace must start at elapsed time 0")
        if any(next_.t_s <= prev.t_s for prev, next_ in zip(self.samples, self.samples[1:])):
            raise ValueError("timestamps must increase strictly")
        if not any(s.current_a > 0 for s in self.samples):
            raise ValueError("discharge must include positive measured current")
        return self


def _first_threshold_crossing(rows: list[tuple[float, float]], threshold: float) -> float | None:
    """First falling crossing using only sampled voltages and linear interpolation."""
    if rows[0][1] <= threshold:
        return rows[0][0]
    for (t0, v0), (t1, v1) in zip(rows, rows[1:]):
        if v0 > threshold >= v1:
            return t0 + (t1 - t0) * (v0 - threshold) / (v0 - v1)
    return None


def replay_discharge(spec: BatterySpec, request: DischargeReplayRequest) -> dict:
    if request.battery_id != spec.id:
        raise ValueError("battery ID does not match component specification")
    if spec.internal_resistance_ohm is None:
        raise ValueError("pack resistance is unknown; cannot compare loaded-voltage trajectory")
    pack = BatteryPack(spec)
    ocv_min = min(p.soc_pct for p in spec.ocv_curve)
    ocv_max = max(p.soc_pct for p in spec.ocv_curve)
    if not ocv_min <= request.initial_soc_pct <= ocv_max:
        raise ValueError("initial SOC lies outside the reference OCV support")

    cumulative_ah = 0.0
    cumulative_wh = 0.0
    rows: list[dict] = []
    max_gap = 0.0
    for i, point in enumerate(request.samples):
        if i:
            previous = request.samples[i - 1]
            elapsed = point.t_s - previous.t_s
            max_gap = max(max_gap, elapsed)
            cumulative_ah += (point.current_a + previous.current_a) * elapsed / 7200.0
            cumulative_wh += (
                point.current_a * point.terminal_voltage_v
                + previous.current_a * previous.terminal_voltage_v
            ) * elapsed / 7200.0
        soc = request.initial_soc_pct - 100.0 * cumulative_ah / spec.capacity_ah
        if not ocv_min <= soc <= ocv_max:
            raise ValueError("replay exceeds declared SOC/capacity or OCV model envelope")
        prediction = pack.voltage_under_load(soc, point.current_a)
        error = prediction - point.terminal_voltage_v
        rows.append({
            "t_s": point.t_s,
            "measured_current_a": point.current_a,
            "measured_voltage_v": point.terminal_voltage_v,
            "predicted_voltage_v": prediction,
            "residual_v": error,
            "predicted_soc_pct": soc,
            "cumulative_charge_ah": cumulative_ah,
            "cumulative_energy_wh": cumulative_wh,
            "c_rate": point.current_a / spec.capacity_ah,
            "temperature_c": point.temperature_c,
        })

    errors = [r["residual_v"] for r in rows]
    max_error = max(abs(e) for e in errors)
    limit = spec.warning_cell_voltage_v * spec.cells_series
    measured_crossing = _first_threshold_crossing(
        [(r["t_s"], r["measured_voltage_v"]) for r in rows], limit
    )
    predicted_crossing = _first_threshold_crossing(
        [(r["t_s"], r["predicted_voltage_v"]) for r in rows], limit
    )
    endpoint_error_pct = (
        100.0 * abs(predicted_crossing - measured_crossing) / measured_crossing
        if measured_crossing is not None and predicted_crossing is not None
        and measured_crossing > 0 else None
    )
    maximum_c_rate = max(r["c_rate"] for r in rows)
    within_discharge_rating = (
        None if spec.max_discharge_c is None
        else maximum_c_rate <= spec.max_discharge_c
    )
    gap_supported = max_gap <= request.predeclared_max_sample_gap_s
    voltage_pass = max_error <= request.predeclared_max_abs_voltage_error_v
    endpoint_pass = (
        endpoint_error_pct is not None
        and endpoint_error_pct <= request.predeclared_max_endpoint_time_error_pct
    )
    # A comparison to generic / estimated reference pack data is a useful
    # model-discrepancy measurement, not pack-specific physical validation.
    reference_estimated = bool(spec.source.estimated) or "generic" in spec.name.lower()
    if request.dataset_kind == "synthetic_fixture":
        verdict = "SYNTHETIC_VERIFICATION_ONLY"
    elif not request.hardware_matches_reference_spec:
        verdict = "REFERENCE_PACK_MISMATCH"
    elif not request.model_unused_for_calibration:
        verdict = "CALIBRATION_DATA_NOT_INDEPENDENT_VALIDATION"
    elif not gap_supported:
        verdict = "DISCHARGE_SAMPLING_TOO_SPARSE"
    elif within_discharge_rating is False:
        verdict = "EXCEEDS_DECLARED_DISCHARGE_C_RATE"
    elif within_discharge_rating is None:
        verdict = "UNKNOWN_DISCHARGE_C_RATE_LIMIT"
    elif measured_crossing is None or predicted_crossing is None or measured_crossing == 0:
        verdict = "RUNTIME_ENDPOINT_NOT_OBSERVED_IN_BOTH_TRACES"
    elif not voltage_pass or not endpoint_pass:
        verdict = "REPORTED_DISCHARGE_TOLERANCES_NOT_MET"
    elif reference_estimated:
        verdict = "GENERIC_OR_ESTIMATED_PACK_REFERENCE_NOT_VALIDATED"
    else:
        verdict = "REPORTED_DISCHARGE_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"

    temps = [p.temperature_c for p in request.samples if p.temperature_c is not None]
    return {
        "battery_id": spec.id,
        "dataset_kind": request.dataset_kind,
        "provenance": {
            "battery_serial_or_id": request.battery_serial_or_id,
            "run_id": request.run_id,
            "data_source": request.data_source,
            "independence_self_reported": request.model_unused_for_calibration,
            "hardware_match_self_reported": request.hardware_matches_reference_spec,
            "identity_instrumentation_and_provenance_not_authenticated": True,
            "reference_source": spec.source.source,
            "reference_notes": spec.source.notes,
            "reference_is_generic_or_estimated": reference_estimated,
        },
        "accounting": {
            "duration_s": rows[-1]["t_s"],
            "charge_consumed_ah": cumulative_ah,
            "measured_energy_delivered_wh": cumulative_wh,
            "modeled_final_soc_pct": rows[-1]["predicted_soc_pct"],
            "maximum_c_rate": maximum_c_rate,
            "within_declared_discharge_rating": within_discharge_rating,
            "maximum_sampling_gap_s": max_gap,
            "within_predeclared_sampling_gap": gap_supported,
        },
        "prediction": {
            "method": "fixed_OCV_and_pack_R_coulomb_counting_conditioned_on_measured_current",
            "voltage_mae_v": mean(abs(e) for e in errors),
            "voltage_rmse_v": math.sqrt(mean(e * e for e in errors)),
            "voltage_bias_v": mean(errors),
            "voltage_max_abs_error_v": max_error,
            "voltage_predeclared_tolerance_v": request.predeclared_max_abs_voltage_error_v,
            "voltage_tolerance_met": voltage_pass,
            "warning_threshold_pack_voltage_v": limit,
            "measured_warning_crossing_s": measured_crossing,
            "predicted_warning_crossing_s": predicted_crossing,
            "endpoint_time_error_pct": endpoint_error_pct,
            "endpoint_predeclared_tolerance_pct": request.predeclared_max_endpoint_time_error_pct,
            "endpoint_tolerance_met": endpoint_pass,
            "rows": rows,
        },
        "temperature": {
            "recorded_count": len(temps),
            "missing_count": len(request.samples) - len(temps),
            "recorded_range_c": [min(temps), max(temps)] if temps else None,
            "modeled": False,
        },
        "verdict": verdict,
        "existing_component_modified": False,
        "existing_flight_predictions_modified": False,
        "limitations": [
            "This replays the measured load-current trace: it does not predict aircraft current or future mission endurance",
            "Initial SOC, hardware identity, instrument calibration, independence and provenance are operator-declared",
            "OCV shape, capacity and pack R must be independently characterized for the actual battery",
            "Trapezoidal charge and energy estimates rely on complete time samples and neglect current/voltage bandwidth limits",
            "Threshold-crossing time is linearly interpolated between reported points and is not an independent endurance test",
            "Temperature dependence, rate-capacity derating, aging, cell imbalance and hysteresis are not modeled",
            "No model update, physical certification, or probability of real-world flight success is implied",
        ],
    }
