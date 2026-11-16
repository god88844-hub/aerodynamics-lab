"""M12: independent-run battery discharge evidence ingestion and evaluation.

The fitted single-resistance OCV model is an *estimate* from user-provided
observations, not an automatic change to the aircraft's simulation battery.
A "held_out" tag and distinct source/run IDs cannot authenticate physical
measurement independence; provenance is reported as user-declared.
"""
from __future__ import annotations

from collections import Counter
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import BatteryPack


class BatteryObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    split: Literal["calibration", "held_out"]
    soc_pct: float = Field(ge=0, le=100)
    current_a: float = Field(gt=0)
    terminal_voltage_v: float = Field(gt=0)
    temperature_c: float | None = None


class BatteryEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    battery_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    dataset_kind: Literal["physical_measurements", "synthetic_fixture"]
    calibration_run_id: str = Field(min_length=1, max_length=120)
    heldout_run_id: str = Field(min_length=1, max_length=120)
    calibration_source: str = Field(min_length=1, max_length=500)
    heldout_source: str = Field(min_length=1, max_length=500)
    predeclared_max_abs_percentage_error_pct: float = Field(gt=0, le=100)
    samples: list[BatteryObservation] = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def validate_evidence_split(self) -> "BatteryEvidenceRequest":
        for value in (self.calibration_run_id, self.heldout_run_id,
                      self.calibration_source, self.heldout_source):
            if not value.strip():
                raise ValueError("run IDs and evidence sources may not be blank")
        if self.calibration_run_id.strip() == self.heldout_run_id.strip():
            raise ValueError("calibration and held-out run IDs must be different")
        ids = [s.id for s in self.samples]
        if len(ids) != len(set(ids)):
            raise ValueError("observation IDs must be unique across both runs")
        counts = Counter(s.split for s in self.samples)
        if counts["calibration"] < 3 or counts["held_out"] < 2:
            raise ValueError("at least 3 calibration and 2 held-out measurements are required")
        currents = {s.current_a for s in self.samples if s.split == "calibration"}
        if len(currents) < 2:
            raise ValueError("calibration requires two or more distinct load currents")
        return self


def _metrics(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("cannot score an empty observation set")
    residuals = [row["predicted_voltage_v"] - row["measured_voltage_v"] for row in rows]
    abs_pcts = [
        100.0 * abs(err) / row["measured_voltage_v"]
        for err, row in zip(residuals, rows)
    ]
    return {
        "count": len(rows),
        "mae_v": sum(abs(e) for e in residuals) / len(rows),
        "rmse_v": math.sqrt(sum(e * e for e in residuals) / len(rows)),
        "bias_v": sum(residuals) / len(rows),
        "mape_pct": sum(abs_pcts) / len(rows),
        "max_abs_percentage_error_pct": max(abs_pcts),
    }


def _score_row(
    pack: BatteryPack,
    observation: BatteryObservation,
    resistance_ohm: float,
) -> dict:
    ocv = pack.ocv_pack(observation.soc_pct)
    sag = observation.current_a * resistance_ohm
    # Match the existing flight battery model's fail-closed high-sag guard.
    if sag > .9 * ocv:
        raise ValueError(
            f"model predicts excessive voltage sag for sample {observation.id}; "
            "the first-order model is not applicable at that load"
        )
    prediction = ocv - sag
    return {
        "id": observation.id,
        "split": observation.split,
        "soc_pct": observation.soc_pct,
        "current_a": observation.current_a,
        "c_rate": observation.current_a / pack.spec.capacity_ah,
        "temperature_c": observation.temperature_c,
        "ocv_pack_v": ocv,
        "measured_voltage_v": observation.terminal_voltage_v,
        "predicted_voltage_v": prediction,
        "residual_v": prediction - observation.terminal_voltage_v,
        "absolute_percentage_error_pct": 100.0 * abs(
            prediction - observation.terminal_voltage_v
        ) / observation.terminal_voltage_v,
    }


def evaluate_battery_evidence(
    spec: BatterySpec, body: BatteryEvidenceRequest
) -> dict:
    """Calibrate on one *declared* run, score on a separate declared run.

    No external dataset is fabricated or loaded here. The predeclared
    tolerance tests only the supplied held-out observations. The existing
    BatterySpec is not mutated, so flight/endurance predictions are unchanged.
    """
    if spec.id != body.battery_id:
        raise ValueError("battery evidence ID does not match the selected pack spec")
    pack = BatteryPack(spec)
    calib = [s for s in body.samples if s.split == "calibration"]
    held = [s for s in body.samples if s.split == "held_out"]
    curve_min = min(p.soc_pct for p in spec.ocv_curve)
    curve_max = max(p.soc_pct for p in spec.ocv_curve)
    if any(not curve_min <= s.soc_pct <= curve_max for s in body.samples):
        raise ValueError("observation SOC lies outside the declared OCV curve support")

    # Ordinary least squares on measured pack-terminal voltages.
    # For fixed OCV(SOC), V_ocv - V_measured = I * R, with no fitted intercept.
    numerator = sum(
        s.current_a * (pack.ocv_pack(s.soc_pct) - s.terminal_voltage_v)
        for s in calib
    )
    denominator = sum(s.current_a ** 2 for s in calib)
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator <= 0:
        raise ValueError("calibration observations do not support a finite fit")
    fit_r = numerator / denominator
    if not math.isfinite(fit_r) or fit_r <= 0:
        raise ValueError("calibrated pack resistance is nonphysical; check SOC, OCV and voltage data")

    calibration_rows = [_score_row(pack, s, fit_r) for s in calib]
    holdout_rows = [_score_row(pack, s, fit_r) for s in held]
    holdout_metrics = _metrics(holdout_rows)

    current_min = min(s.current_a for s in calib)
    current_max = max(s.current_a for s in calib)
    soc_min = min(s.soc_pct for s in calib)
    soc_max = max(s.soc_pct for s in calib)
    within_envelope = all(
        current_min <= s.current_a <= current_max and
        soc_min <= s.soc_pct <= soc_max for s in held
    )
    over_limit = (
        spec.max_discharge_c is not None and any(
            row["c_rate"] > spec.max_discharge_c for row in holdout_rows
        )
    )
    threshold_met = (
        holdout_metrics["max_abs_percentage_error_pct"]
        <= body.predeclared_max_abs_percentage_error_pct
    )

    nominal_metrics = None
    nominal_status = "UNKNOWN_RESISTANCE"
    if spec.internal_resistance_ohm is not None:
        try:
            nominal_metrics = _metrics([
                _score_row(pack, s, spec.internal_resistance_ohm) for s in held
            ])
            nominal_status = "SCORED_ON_HELD_OUT"
        except ValueError:
            nominal_status = "OUTSIDE_FIRST_ORDER_VOLTAGE_SAG_ENVELOPE"

    if body.dataset_kind == "synthetic_fixture":
        verdict = "SYNTHETIC_VERIFICATION_ONLY"
    elif not within_envelope:
        verdict = "OUTSIDE_CALIBRATION_ENVELOPE"
    elif not threshold_met:
        verdict = "REPORTED_HOLDOUT_TOLERANCE_NOT_MET"
    elif over_limit:
        verdict = "EXCEEDS_DECLARED_C_RATE"
    else:
        verdict = "REPORTED_HOLDOUT_TOLERANCE_MET_NOT_PHYSICALLY_VERIFIED"

    temps = [s.temperature_c for s in body.samples if s.temperature_c is not None]
    return {
        "battery_id": spec.id,
        "dataset_kind": body.dataset_kind,
        "sources": {
            "calibration_run_id": body.calibration_run_id,
            "heldout_run_id": body.heldout_run_id,
            "calibration_source": body.calibration_source,
            "heldout_source": body.heldout_source,
            "self_reported_not_authenticated": True,
            "original_battery_model_source": spec.source.source,
            "original_battery_model_notes": spec.source.notes,
        },
        "fit": {
            "method": "OLS_fixed_OCV_single_pack_R",
            "fitted_pack_resistance_ohm": fit_r,
            "declared_pack_resistance_ohm": spec.internal_resistance_ohm,
            "calibration_metrics": _metrics(calibration_rows),
            "calibration_current_range_a": [current_min, current_max],
            "calibration_soc_range_pct": [soc_min, soc_max],
        },
        "heldout": {
            "metrics": holdout_metrics,
            "rows": holdout_rows,
            "nominal_model_metrics": nominal_metrics,
            "nominal_model_status": nominal_status,
            "within_calibration_envelope": within_envelope,
            "predeclared_max_abs_percentage_error_pct":
                body.predeclared_max_abs_percentage_error_pct,
            "meets_predeclared_error_tolerance": threshold_met,
            "max_observed_c_rate": max(row["c_rate"] for row in holdout_rows),
            "above_declared_c_rate_limit": bool(over_limit),
        },
        "temperature": {
            "recorded_count": len(temps),
            "missing_count": len(body.samples) - len(temps),
            "measured_range_c": [min(temps), max(temps)] if temps else None,
            "modeled": False,
        },
        "verdict": verdict,
        "simulation_battery_modified": False,
        "limitations": [
            "Evidence, run independence, measurement calibration and provenance are user-declared, not externally verified",
            "Physical validation of a particular battery requires traceable hardware, measurements and test conditions",
            "Generic OCV(SOC) curve is not a pack-specific independently validated OCV reference",
            "Only a constant pack DC resistance is fitted; no rate-capacity derating, thermal behavior, hysteresis, aging or cell imbalance",
            "Held-out tolerance is a prediction-error check on supplied data, not a probability of successful real-world flight",
            "Predeclared tolerance and calibration envelope are not interchangeable with airworthiness or physical validation",
            "No design component entry, original simulation result or endurance estimate is altered",
        ],
    }
