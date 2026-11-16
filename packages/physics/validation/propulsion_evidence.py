"""M14 independent static motor+prop test evidence against frozen model of record.

Only predicts within the stated model envelope. Ineligible observations and
user-declared provenance cannot be converted to certified real-world validity.
No calibration, persistence or powertrain mutation occurs.
"""
from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from physics.propulsion.dataset import OutOfEnvelopeError, PowertrainDataset


class PropulsionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,80}$")
    rpm: float = Field(gt=0)
    voltage_v: float = Field(gt=0)
    thrust_gf: float = Field(gt=0)
    current_a: float = Field(gt=0)


class PropulsionEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    motor_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    propeller_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    dataset_kind: Literal["physical_measurements", "synthetic_fixture"]
    independent_run_id: str = Field(min_length=1, max_length=120)
    evidence_source: str = Field(min_length=1, max_length=500)
    hardware_matches_selected_components: bool
    unused_for_model_calibration: bool
    predeclared_max_thrust_error_pct: float = Field(gt=0, le=100)
    predeclared_max_current_error_pct: float = Field(gt=0, le=100)
    ambient_air_density_kg_m3: float | None = Field(default=None, gt=0)
    ambient_temperature_c: float | None = None
    test_fixture_description: str | None = Field(default=None, max_length=500)
    observations: list[PropulsionObservation] = Field(min_length=5, max_length=500)

    @model_validator(mode="after")
    def inspect(self) -> "PropulsionEvidenceRequest":
        if not self.independent_run_id.strip() or not self.evidence_source.strip():
            raise ValueError("declare a nonblank independent run ID and source")
        ids = [row.id for row in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("observation IDs must be unique")
        if len({row.rpm for row in self.observations}) < 5:
            raise ValueError("at least five distinct measured RPMs are needed")
        return self


def _metrics(rows: list[dict], name: str, limit_pct: float) -> dict:
    errs = [row[f"{name}_prediction_error_pct"] for row in rows]
    return {
        "n": len(errs),
        "mape_pct": sum(abs(e) for e in errs) / len(errs),
        "rmse_pct": math.sqrt(sum(e * e for e in errs) / len(errs)),
        "bias_pct": sum(errs) / len(errs),
        "max_abs_error_pct": max(abs(e) for e in errs),
        "predeclared_max_abs_error_pct": limit_pct,
        "threshold_met": max(abs(e) for e in errs) <= limit_pct,
    }


def evaluate_propulsion_evidence(
    dataset: PowertrainDataset, body: PropulsionEvidenceRequest
) -> dict:
    """Predict held-out static thrust/current from a pre-existing bench model."""
    if dataset.motor.id != body.motor_id:
        raise ValueError("motor ID does not match loaded bench model")
    if body.dataset_kind == "physical_measurements" and not (body.test_fixture_description or "").strip():
        raise ValueError("physical evidence requires fixture and instrumentation description")
    matched: list[dict] = []
    unsupported: list[dict] = []
    calibration_knots = dataset.motor.test_data
    matching_knots = 0
    any_voltage_extrapolated = False
    any_voltage_corrected = False

    for row in body.observations:
        # An identical operating point can be measured on a genuinely
        # independent run; count overlaps for audit, never infer independence.
        if any(
            point.prop == dataset.prop_key and abs(point.rpm - row.rpm) < 1e-6
            and abs(point.voltage_v - row.voltage_v) < .1
            for point in calibration_knots
        ):
            matching_knots += 1
        try:
            thrust = dataset.thrust_gf(row.rpm)
            current = dataset.current_a(row.rpm, row.voltage_v)
        except (OutOfEnvelopeError, ValueError) as exc:
            unsupported.append({"id": row.id, "reason": str(exc),
                                "rpm": row.rpm, "voltage_v": row.voltage_v})
            continue
        if not all(math.isfinite(x) and x > 0 for x in (thrust.value, current.value)):
            unsupported.append({"id": row.id, "reason": "nonphysical model prediction",
                                "rpm": row.rpm, "voltage_v": row.voltage_v})
            continue
        any_voltage_extrapolated |= current.voltage_extrapolated
        any_voltage_corrected |= current.voltage_corrected
        matched.append({
            "id": row.id,
            "rpm": row.rpm,
            "voltage_v": row.voltage_v,
            "thrust_measured_gf": row.thrust_gf,
            "thrust_predicted_gf": thrust.value,
            "current_measured_a": row.current_a,
            "current_predicted_a": current.value,
            "thrust_prediction_error_pct": 100.0 * (thrust.value-row.thrust_gf)/row.thrust_gf,
            "current_prediction_error_pct": 100.0 * (current.value-row.current_a)/row.current_a,
            "voltage_extrapolated": current.voltage_extrapolated,
            "voltage_corrected": current.voltage_corrected,
        })

    # No cherry-picking: one unsupported sample invalidates an overall pass,
    # even if the remaining points happen to fit tightly.
    complete = len(matched) == len(body.observations)
    thrust_metrics = _metrics(matched, "thrust", body.predeclared_max_thrust_error_pct) if matched else None
    current_metrics = _metrics(matched, "current", body.predeclared_max_current_error_pct) if matched else None
    thresholds_met = bool(
        complete and thrust_metrics and current_metrics
        and thrust_metrics["threshold_met"] and current_metrics["threshold_met"]
    )

    if body.dataset_kind == "synthetic_fixture":
        verdict = "SYNTHETIC_VERIFICATION_ONLY"
    elif not body.hardware_matches_selected_components:
        verdict = "HARDWARE_MATCH_UNCONFIRMED"
    elif not body.unused_for_model_calibration:
        verdict = "CALIBRATION_DATA_NOT_INDEPENDENT_VALIDATION"
    elif not complete:
        verdict = "OUTSIDE_SUPPORTED_MODEL_ENVELOPE"
    elif any_voltage_extrapolated:
        verdict = "VOLTAGE_EXTRAPOLATED_UNVALIDATED"
    elif not thresholds_met:
        verdict = "REPORTED_HOLDOUT_TOLERANCES_NOT_MET"
    else:
        verdict = "REPORTED_HOLDOUT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"

    return {
        "motor_id": body.motor_id,
        "propeller_id": body.propeller_id,
        "model_of_record": {
            "prop_key": dataset.prop_key,
            "manufacturer_data_source": dataset.motor.source.source,
            "reference_dataset_is_calibration_not_validation": True,
            "envelope": dataset.envelope(),
        },
        "provenance": {
            "dataset_kind": body.dataset_kind,
            "independent_run_id": body.independent_run_id,
            "evidence_source": body.evidence_source,
            "hardware_match_self_reported": body.hardware_matches_selected_components,
            "unused_for_calibration_self_reported": body.unused_for_model_calibration,
            "ambient_air_density_kg_m3": body.ambient_air_density_kg_m3,
            "ambient_temperature_c": body.ambient_temperature_c,
            "test_fixture_description": body.test_fixture_description,
            "instrumentation_and_run_independence_not_authenticated": True,
        },
        "evidence": {
            "observation_count": len(body.observations),
            "scored_count": len(matched),
            "unsupported_count": len(unsupported),
            "unsupported_samples": unsupported,
            "rows": matched,
            "calibration_knot_operating_point_overlap_count": matching_knots,
            "current_voltage_corrected": any_voltage_corrected,
            "current_voltage_extrapolated": any_voltage_extrapolated,
            "thrust_metrics": thrust_metrics,
            "current_metrics": current_metrics,
            "all_samples_scored_and_tolerances_met": thresholds_met,
            "measured_rpm_range": [min(r.rpm for r in body.observations),
                                   max(r.rpm for r in body.observations)],
            "measured_voltage_range_v": [min(r.voltage_v for r in body.observations),
                                         max(r.voltage_v for r in body.observations)],
        },
        "verdict": verdict,
        "simulation_modified": False,
        "limitations": [
            "Run identity, separation from manufacturer calibration data and component hardware match are not independently authenticated",
            "Manufacturer dataset is the fitted interpolation model of record; checking it against itself is not validation",
            "Measurements must be acquired at comparable static conditions and equivalent installed hardware",
            "Air density, temperature, rotor-rotor interference, dynamic inflow and advance ratio are not corrected",
            "Percent errors are relative to reported measurements and do not establish measurement traceability",
            "A held-out tolerance pass does not certify aircraft, guarantee flight or quantify mission success probability",
            "No fitted model, component database, design or prior simulation is changed",
        ],
    }
