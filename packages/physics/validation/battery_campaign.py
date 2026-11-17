"""M21 read-only campaign audit against unchanged battery OCV+R model.

This is conditional prediction of terminal voltage given MEASURED current.
It does not independently predict aircraft loads, endurance or pack temperature.
Original telemetry bytes are SHA-256 checked by M19. M20 checks operator-declared
experiment preregistration, but cannot authenticate approvals or calibration.
"""
from __future__ import annotations

import csv
import io
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import PowertrainError
from physics.validation.discharge_replay import DischargeReplayRequest, replay_discharge
from physics.validation.telemetry_ingestion import InlineTelemetryDataset, audit_telemetry_bundle
from physics.validation.validation_protocol import (
    ProtocolAuditRequest, ValidationProtocol, audit_protocol,
)

class CampaignRun(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    evidence: InlineTelemetryDataset
    initial_soc_pct: float = Field(gt=0, le=100)
    hardware_match_self_reported: bool
    unused_for_calibration_self_reported: bool
    # Report-only: NOT a frozen endurance criterion in the M20 model.
    illustrative_endpoint_error_limit_pct: float = Field(gt=0, le=100)

class BatteryCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    battery_model_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    frozen_protocol: ValidationProtocol
    expected_frozen_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    runs: list[CampaignRun] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_identifiers(self):
        ids = [r.evidence.manifest.dataset_id for r in self.runs]
        if len(ids) != len(set(ids)):
            raise ValueError("campaign dataset identifiers must be unique")
        rec = [r.evidence.manifest.recording_id for r in self.runs]
        if len(rec) != len(set(rec)):
            raise ValueError("campaign recording identifiers must be unique")
        return self


def _trace_to_samples(evidence: InlineTelemetryDataset) -> list[dict]:
    # Called ONLY after the original byte hash, CSV schema and timestamp audit.
    # The data cannot be replaced by a separately hand-entered replay.
    raw = evidence.csv_text
    reader = csv.DictReader(io.StringIO(raw, newline=""))
    points: list[dict] = []
    for row in reader:
        points.append({
            "t_s": float(row["t_s"]),
            "current_a": float(row["current_a"]),
            "terminal_voltage_v": float(row["terminal_voltage_v"]),
            "temperature_c": (
                float(row["temperature_c"]) if "temperature_c" in row else None
            ),
        })
    return points


def audit_battery_campaign(spec: BatterySpec, body: BatteryCampaignRequest) -> dict:
    if body.battery_model_id != spec.id:
        raise ValueError("battery model identifier differs from reference spec")
    bundles = [
        (r.evidence.manifest, r.evidence.csv_text.encode("utf-8"))
        for r in body.runs
    ]
    source_audit = audit_telemetry_bundle(bundles)
    protocol_audit = audit_protocol(ProtocolAuditRequest(
        protocol=body.frozen_protocol,
        expected_frozen_sha256=body.expected_frozen_sha256,
        imported_manifests=[r.evidence.manifest for r in body.runs],
    ))
    blockers = list(protocol_audit["blockers"])
    partition = source_audit["partition"]
    if partition["status"] != "DECLARED_DISJOINT_SPLIT_NOT_INDEPENDENTLY_AUTHENTICATED":
        blockers.append("Experiment-level calibration/holdout partition not fully declared disjoint")
    estimated_reference = bool(spec.source.estimated) or "generic" in spec.name.lower()
    if estimated_reference:
        blockers.append("Generic/estimated battery cannot qualify as matched physical pack validation")
    if spec.internal_resistance_ohm is None:
        blockers.append("Battery pack internal resistance not independently characterized")
    if spec.max_discharge_c is None:
        blockers.append("Battery maximum continuous C-rate unknown")
    voltage_metrics = [
        m for m in body.frozen_protocol.acceptance_metrics
        if m.channel == "terminal_voltage_v"
    ]
    if len(voltage_metrics) != 1:
        blockers.append("Exactly one preregistered terminal voltage acceptance metric required")
    for metric in body.frozen_protocol.acceptance_metrics:
        if metric.channel not in ("terminal_voltage_v", "current_a"):
            blockers.append(
                f"OCV+R replay cannot independently predict critical {metric.channel}; separate validated model required"
            )
        elif metric.channel == "current_a":
            blockers.append("Measured current is an input, not a prediction of flight power demand")
    voltage_metric = voltage_metrics[0] if voltage_metrics else None
    terms = [
        u for u in body.frozen_protocol.uncertainties
        if u.channel == "terminal_voltage_v"
    ]
    bound = (
        sum(t.absolute_value for t in terms)
        if terms and all(t.type == "hard_absolute_bound" for t in terms)
        else None
    )
    if bound is not None and not math.isfinite(bound):
        bound = None
    if bound is None:
        blockers.append("No finite traceable hard voltage measurement-error bound")
    instr = next(
        (i for i in body.frozen_protocol.instruments if i.channel == "terminal_voltage_v"),
        None,
    )
    clock_bound = instr.clock_alignment_bound_s if instr else None
    if clock_bound is None or clock_bound > 0:
        blockers.append(
            "Positive or unknown clock uncertainty has no continuous-time voltage enclosure; samplewise compatibility only"
        )

    run_results = []
    observed_holdout_count = 0
    all_samplewise_compatible = True
    all_reported_holdouts = True
    for run, (_, audit) in zip(body.runs, bundles):
        manifest = run.evidence.manifest
        source = next(x for x in source_audit["datasets"] if x["dataset_id"] == manifest.dataset_id)
        holdout = manifest.partition_role == "holdout"
        if holdout:
            observed_holdout_count += 1
        reasons = []
        if not source["quality"]["sampling_interval_within_predeclared_bound"]:
            reasons.append("Sparse timestamps invalidate time-integrated charge/energy")
        if voltage_metric is not None:
            if manifest.expected_samples < voltage_metric.minimum_holdout_samples:
                reasons.append("Insufficient voltage holdout samples")
            if manifest.predeclared_max_sample_gap_s > voltage_metric.maximum_sampling_gap_s:
                reasons.append("Manifest allows larger sample gaps than frozen voltage criterion")
        if manifest.dataset_kind != "reported_physical_measurements":
            reasons.append("Synthetic source is verification only, never physical evidence")
        if not holdout:
            reasons.append("Calibration/unassigned run cannot count as independent holdout")
        if not run.unused_for_calibration_self_reported and holdout:
            reasons.append("Held-out recording self-declared as used in calibration")
        if not run.hardware_match_self_reported:
            reasons.append("Physical pack hardware match was not declared")
        hardware = [
            h for h in body.frozen_protocol.hardware
            if h.role == "battery"
            and h.model == spec.id
            and h.serial_or_lot == manifest.battery_id
        ]
        if not hardware:
            reasons.append("Actual pack serial and model missing from frozen hardware registration")
        # This model has no temperature predictor, even when a thermocouple
        # channel exists; absence is a further evidence-quality deficit.
        if "temperature_c" not in manifest.columns:
            reasons.append("No pack temperature channel measured")
        if manifest.expected_samples > 10000:
            reasons.append("More than the supported 10,000 replay observations")
        replay = None
        if manifest.expected_samples <= 10000 and voltage_metric is not None:
            try:
                request = DischargeReplayRequest.model_validate({
                    "battery_id": spec.id,
                    "dataset_kind": (
                        "synthetic_fixture" if manifest.dataset_kind == "synthetic_fixture"
                        else "physical_measurements"
                    ),
                    "battery_serial_or_id": manifest.battery_id,
                    "run_id": manifest.recording_id,
                    "data_source": manifest.source_reference,
                    "model_unused_for_calibration": run.unused_for_calibration_self_reported,
                    "hardware_matches_reference_spec": run.hardware_match_self_reported,
                    "initial_soc_pct": run.initial_soc_pct,
                    "predeclared_max_abs_voltage_error_v":
                        voltage_metric.maximum_absolute_prediction_error,
                    "predeclared_max_endpoint_time_error_pct":
                        run.illustrative_endpoint_error_limit_pct,
                    "predeclared_max_sample_gap_s":
                        voltage_metric.maximum_sampling_gap_s,
                    "samples": _trace_to_samples(run.evidence),
                })
                replay = replay_discharge(spec, request)
            except (ValueError, PowertrainError) as exc:
                reasons.append(f"Unscorable battery replay: {exc}")
        else:
            reasons.append("Missing voltage acceptance metric or unsupported replay length")
        run_metrics = None
        if replay is not None and voltage_metric is not None:
            prediction = replay["prediction"]
            max_discrepancy = prediction["voltage_max_abs_error_v"]
            if bound is None:
                compatible = False
                sample_status = "INDETERMINATE_MISSING_MEASUREMENT_BOUND"
                upper = None
                lower = None
            else:
                upper = max_discrepancy + bound
                lower = max(0.0, max_discrepancy - bound)
                if not math.isfinite(upper):
                    compatible = False
                    sample_status = "INDETERMINATE_NUMERIC_OVERFLOW"
                    upper = None
                elif lower > voltage_metric.maximum_absolute_prediction_error:
                    compatible = False
                    sample_status = "TOLERANCE_EXCEEDED_UNDER_DECLARED_HARD_BOUNDS"
                elif upper <= voltage_metric.maximum_absolute_prediction_error:
                    compatible = True
                    sample_status = "SAMPLEWISE_COMPATIBLE_DECLARED_BOUNDS_ONLY"
                else:
                    compatible = False
                    sample_status = "INDETERMINATE_UNDER_DECLARED_HARD_BOUNDS"
            if not compatible:
                all_samplewise_compatible = False
            if holdout and not compatible:
                reasons.append(f"Holdout voltage comparison: {sample_status}")
            if replay["accounting"]["within_declared_discharge_rating"] is not True:
                reasons.append("Measured current exceeds or lacks known pack C-rate limit")
            if not replay["accounting"]["within_predeclared_sampling_gap"]:
                reasons.append("Observed time gaps exceed frozen protocol limit")
            if replay["prediction"]["measured_warning_crossing_s"] is None:
                reasons.append("Measured warning-voltage endpoint never observed")
            if replay["prediction"]["predicted_warning_crossing_s"] is None:
                reasons.append("Predicted warning-voltage endpoint never observed")
            run_metrics = {
                "status": sample_status,
                "voltage_mae_v": prediction["voltage_mae_v"],
                "voltage_rmse_v": prediction["voltage_rmse_v"],
                "voltage_max_abs_error_v": max_discrepancy,
                "samplewise_abs_residual_lower_bound_v": lower,
                "samplewise_abs_residual_upper_bound_v": upper,
                "model_conditioned_on_measured_current": True,
                "measured_charge_ah": replay["accounting"]["charge_consumed_ah"],
                "measured_delivered_energy_wh":
                    replay["accounting"]["measured_energy_delivered_wh"],
                "highest_c_rate": replay["accounting"]["maximum_c_rate"],
                "measured_warning_crossing_s":
                    prediction["measured_warning_crossing_s"],
                "predicted_warning_crossing_s":
                    prediction["predicted_warning_crossing_s"],
                "endpoint_error_pct_descriptive_only":
                    prediction["endpoint_time_error_pct"],
                "battery_temperature_model_validated": False,
                "flight_endurance_independently_predicted": False,
            }
        else:
            all_samplewise_compatible = False
        if holdout and reasons:
            all_reported_holdouts = False
        run_results.append({
            "dataset_id": manifest.dataset_id,
            "recording_id": manifest.recording_id,
            "partition_role": manifest.partition_role,
            "original_telemetry_sha256_verified_against_operator_manifest":
                source["raw_sha256_verified_against_manifest"],
            "conditional_voltage_replay": run_metrics,
            "blockers": reasons,
        })
    if observed_holdout_count < 2:
        blockers.append("Fewer than two reported holdout recordings")
    if not all_samplewise_compatible or not all_reported_holdouts:
        blockers.append("Not all holdouts support samplewise voltage compatibility")
    # Having no model discrepancy, thermal or high-C model-form uncertainties
    # cannot justify validating battery/mission readiness even with exact data.
    blockers.append("Battery thermal, aging, rate-capacity and model-form discrepancy unvalidated")
    blockers.append("No authenticated sensor/pack identity or independent laboratory evidence")
    return {
        "battery_model_id": spec.id,
        "campaign_status": "PHYSICAL_BATTERY_VALIDATION_NOT_ESTABLISHED",
        "protocol": {
            "readiness_status": protocol_audit["readiness_status"],
            "canonical_sha256": protocol_audit["canonical_protocol_sha256"],
            "externally_authenticated": False,
        },
        "partition_status": partition["status"],
        "source_count": len(run_results),
        "holdout_count": observed_holdout_count,
        "measured_current_is_external_input": True,
        "pack_model_form": "fixed_ocv_soc_plus_single_internal_resistance",
        "generic_or_estimated_pack_reference": estimated_reference,
        "claimed_voltage_compatibility_only_samplewise": bool(
            all_samplewise_compatible and all_reported_holdouts and not estimated_reference
        ),
        "runs": run_results,
        "blockers": list(dict.fromkeys(blockers)),
        "independently_authenticated_physical_pack_test": False,
        "independently_validated_battery_temperature": False,
        "independently_validated_aircraft_endurance": False,
        "decision_equivalent_to_physical_testing": False,
        "existing_battery_model_modified": False,
    }
