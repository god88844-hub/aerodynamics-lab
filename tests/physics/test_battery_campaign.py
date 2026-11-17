"""M21 all numerical telemetry below is SYNTHETIC, including spoofed physical labels.

This tests software fail-closed decisions, not any real battery experiment.
"""
from __future__ import annotations

from hashlib import sha256
import copy

import pytest
from pydantic import ValidationError
from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import BatteryPack
from physics.validation.battery_campaign import (
    BatteryCampaignRequest, audit_battery_campaign,
)
from physics.validation.validation_protocol import (
    ValidationProtocol, protocol_sha256,
)


def battery():
    return BatterySpec.model_validate({
        "id": "verification_pack_2s", "name": "Synthetic analytical LiPo reference",
        "chemistry": "LiPo", "cells_series": 2, "capacity_ah": 1.0,
        "internal_resistance_ohm": .05, "max_discharge_c": 10,
        "ocv_curve": [
            {"soc_pct": 0, "cell_voltage_v": 3.3},
            {"soc_pct": 100, "cell_voltage_v": 4.2},
        ],
        "warning_cell_voltage_v": 3.5,
        "source": {"source": "Synthetic mathematical fixture, not an actual pack",
                   "estimated": False},
    })


def proto():
    return {
        "schema_version": "1.0", "protocol_id": "synthetic_high_c_fixture",
        "intended_engineering_decision": "Audit synthetic battery voltage replay, never actual aircraft flight",
        "frozen_model_git_sha": "a" * 40,
        "frozen_design_sha256": "b" * 64,
        "frozen_controller_configuration_sha256": "c" * 64,
        "preregistration_record_reference": "synthetic://precommit",
        "numerical_convergence_report_reference": "synthetic://convergence",
        "independent_reviewer_reference": "synthetic://review",
        "approved_test_safety_plan_reference": "synthetic://review-no-physical-authorization",
        "envelope": {
            "ambient_temperature_c": [0, 40], "air_density_kg_m3": [1.0, 1.4],
            "wind_speed_m_s": [0, 4], "payload_kg": [0, 2], "altitude_m": [0, 60],
        },
        "hardware": [
            *[{"role": role, "model": f"fixture_{role}", "serial_or_lot": "fixture_unique",
               "quantity": 1, "geometry_or_firmware_revision": "v1"}
              for role in ("airframe", "motor", "propeller", "esc", "controller")],
            *[{"role": "battery", "model": "verification_pack_2s",
               "serial_or_lot": f"pack_{k}", "quantity": 1,
               "geometry_or_firmware_revision": "v1"} for k in range(3)],
        ],
        "instruments": [
            {"channel": "terminal_voltage_v", "manufacturer_model": "synthetic meter",
             "serial": "synthetic meter 1", "calibration_reference": "synthetic://calibrated",
             "calibration_date_utc": "2026-11-17",
             "bandwidth_hz": 20, "clock_alignment_bound_s": 0},
        ],
        "uncertainties": [
            {"name": "math fixture error", "channel": "terminal_voltage_v",
             "absolute_value": .02, "type": "hard_absolute_bound",
             "source_reference": "synthetic://bound"},
        ],
        "acceptance_metrics": [
            {"channel": "terminal_voltage_v",
             "maximum_absolute_prediction_error": .2,
             "minimum_holdout_samples": 6, "maximum_sampling_gap_s": 65},
        ],
        "experiments": [
            {"experiment_id": f"exp_{k}", "recording_id": f"rec_{k}",
             "vehicle_id": f"vehicle_{k}", "battery_id": f"pack_{k}",
             "role": "calibration" if k == 0 else "holdout",
             "scenario": "synthetic discharge only"} for k in range(3)
        ],
    }


def run_fixture(k, *, physical=False, perturb=0.0):
    p = BatteryPack(battery())
    rows = ["t_s,terminal_voltage_v,current_a,temperature_c"]
    for sample in range(11):
        t = sample * 60
        soc = 100 - 100 * (5 * t / 3600)
        predicted = p.voltage_under_load(soc, 5)
        voltage = predicted + perturb + .001 * k
        rows.append(f"{t},{voltage:.9f},5,25")
    csv = "\n".join(rows) + "\n"
    return {
        "evidence": {
            "manifest": {
                "schema_version": "1.0",
                "dataset_id": f"fixture_{k}",
                "dataset_kind": (
                    "reported_physical_measurements" if physical else "synthetic_fixture"
                ),
                "partition_role": "calibration" if k == 0 else "holdout",
                "experiment_id": f"exp_{k}", "recording_id": f"rec_{k}",
                "vehicle_id": f"vehicle_{k}", "battery_id": f"pack_{k}",
                "source_reference": "synthetic numerical test, not an instrument",
                "license_or_permission": "test fixture",
                "filename": "trace.csv",
                "raw_sha256": sha256(csv.encode()).hexdigest(),
                "expected_samples": 11,
                "predeclared_max_sample_gap_s": 65,
                "columns": [
                    "t_s", "terminal_voltage_v", "current_a", "temperature_c",
                ],
            },
            "csv_text": csv,
        },
        "initial_soc_pct": 100,
        "hardware_match_self_reported": True,
        "unused_for_calibration_self_reported": k != 0,
        "illustrative_endpoint_error_limit_pct": 5,
    }


def request(*, physical=False, payload=None):
    p = payload or proto()
    protocol = ValidationProtocol.model_validate(p)
    return {
        "battery_model_id": "verification_pack_2s",
        "frozen_protocol": p,
        "expected_frozen_sha256": protocol_sha256(protocol),
        "runs": [run_fixture(k, physical=physical) for k in range(3)],
    }


def score(data=None, *, spec=None):
    return audit_battery_campaign(
        spec or battery(), BatteryCampaignRequest.model_validate(data or request())
    )


def test_full_synthetic_cohort_checks_math_without_physical_validation():
    result = score()
    assert result["source_count"] == 3
    assert result["holdout_count"] == 2
    assert result["partition_status"] == "SYNTHETIC_OR_MIXED_DATASET_NO_PHYSICAL_VALIDATION"
    assert result["campaign_status"] == "PHYSICAL_BATTERY_VALIDATION_NOT_ESTABLISHED"
    assert result["independently_validated_aircraft_endurance"] is False
    assert result["decision_equivalent_to_physical_testing"] is False
    assert result["claimed_voltage_compatibility_only_samplewise"] is False
    for entry in result["runs"]:
        assert entry["conditional_voltage_replay"] is not None
        assert entry["conditional_voltage_replay"]["voltage_max_abs_error_v"] < .01
        assert entry["conditional_voltage_replay"]["model_conditioned_on_measured_current"]
        assert entry["conditional_voltage_replay"]["measured_delivered_energy_wh"] > 0


def test_spoofed_physical_labels_cannot_authenticate_independent_measurements():
    report = score(request(physical=True))
    assert report["partition_status"] == "DECLARED_DISJOINT_SPLIT_NOT_INDEPENDENTLY_AUTHENTICATED"
    assert report["claimed_voltage_compatibility_only_samplewise"] is True
    assert report["independently_authenticated_physical_pack_test"] is False
    assert report["independently_validated_battery_temperature"] is False
    assert report["decision_equivalent_to_physical_testing"] is False
    assert report["blockers"]


def test_raw_file_tampering_detected_before_voltage_comparison():
    data = request(physical=True)
    data["runs"][1]["evidence"]["csv_text"] = (
        data["runs"][1]["evidence"]["csv_text"].replace("5,25", "6,25", 1)
    )
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        score(data)


def test_large_voltage_disagreement_fails_reported_bounds():
    data = request(physical=True)
    data["runs"][1] = run_fixture(1, physical=True, perturb=.45)
    result = score(data)
    r = result["runs"][1]["conditional_voltage_replay"]
    assert r["status"] == "TOLERANCE_EXCEEDED_UNDER_DECLARED_HARD_BOUNDS"
    assert result["claimed_voltage_compatibility_only_samplewise"] is False
    assert result["decision_equivalent_to_physical_testing"] is False


def test_generic_pack_is_unvalidated_even_for_perfect_synthetic_match():
    spec = battery()
    spec.name = "Generic synthetic LiPo"
    result = score(request(physical=True), spec=spec)
    assert result["generic_or_estimated_pack_reference"]
    assert not result["claimed_voltage_compatibility_only_samplewise"]
    assert any("Generic/estimated" in b for b in result["blockers"])


def test_positive_clock_error_invalidates_continuous_time_claim():
    data = request(physical=True)
    data["frozen_protocol"]["instruments"][0]["clock_alignment_bound_s"] = .05
    plan = ValidationProtocol.model_validate(data["frozen_protocol"])
    data["expected_frozen_sha256"] = protocol_sha256(plan)
    result = score(data)
    assert any("clock uncertainty" in b for b in result["blockers"])
    assert not result["decision_equivalent_to_physical_testing"]


def test_temperature_model_never_claimed_validated_even_when_measured():
    r = score(request(physical=True))
    assert all(
        x["conditional_voltage_replay"]["battery_temperature_model_validated"] is False
        for x in r["runs"]
    )


def test_declared_group_overlap_cannot_claim_holdout_independence():
    data = request(physical=True)
    data["runs"][1]["evidence"]["manifest"]["vehicle_id"] = "vehicle_0"
    report = score(data)
    assert report["partition_status"] == "CROSS_PARTITION_LEAKAGE_DECLARED"
    assert not report["decision_equivalent_to_physical_testing"]
    assert any("partition not fully" in b or "partition not" in b
               for b in report["blockers"])


def test_frozen_protocol_tamper_is_blocking():
    data = request(physical=True)
    data["frozen_protocol"]["acceptance_metrics"][0]["maximum_absolute_prediction_error"] = 10
    report = score(data)
    assert report["protocol"]["readiness_status"] == "FROZEN_PROTOCOL_TAMPERED"
    assert not report["claimed_voltage_compatibility_only_samplewise"]
    assert not report["decision_equivalent_to_physical_testing"]


def test_pack_discharge_rating_mismatch_blocks_positive_claim():
    spec = battery()
    spec.max_discharge_c = 4
    result = score(request(physical=True), spec=spec)
    assert any("C-rate limit" in reason for x in result["runs"] for reason in x["blockers"])
    assert result["decision_equivalent_to_physical_testing"] is False


@pytest.mark.parametrize("mutate", [
    lambda d: d["runs"][1]["evidence"]["manifest"].update({"recording_id": "rec_0"}),
    lambda d: d["runs"][0].update({"initial_soc_pct": 150}),
    lambda d: d["runs"][0].update({"illustrative_endpoint_error_limit_pct": 0}),
    lambda d: d.update({"battery_model_id": "../outside"}),
    lambda d: d["runs"].pop(),
    lambda d: d["runs"][0].update({"unknown_field": 1}),
])
def test_schema_fails_closed_or_never_claims_independent_validation(mutate):
    d = request()
    mutate(d)
    try:
        report = score(d)
    except (ValueError, ValidationError):
        return
    assert report["decision_equivalent_to_physical_testing"] is False


def test_evidence_and_spec_are_read_only():
    d = request(physical=True)
    spec = battery()
    original = copy.deepcopy((d, spec.model_dump()))
    score(d, spec=spec)
    assert (d, spec.model_dump()) == original



def test_unphysically_large_but_finite_voltage_blocks_squared_residual_overflow():
    data = request(physical=True)
    evidence = data["runs"][1]["evidence"]
    lines = evidence["csv_text"].splitlines()
    fields = lines[1].split(",")
    fields[1] = "1e200"
    lines[1] = ",".join(fields)
    evidence["csv_text"] = "\n".join(lines) + "\n"
    evidence["manifest"]["raw_sha256"] = sha256(evidence["csv_text"].encode()).hexdigest()
    result = score(data)
    assert result["runs"][1]["conditional_voltage_replay"] is None
    assert any("Observed voltage exceeds reference OCV support" in v
               for v in result["runs"][1]["blockers"])
    assert result["decision_equivalent_to_physical_testing"] is False


def test_sparse_real_time_samples_cannot_report_measured_energy_or_charge():
    data = request(physical=True)
    evidence = data["runs"][1]["evidence"]
    lines = evidence["csv_text"].splitlines()
    fields = lines[2].split(",")
    fields[0] = "100"
    lines[2] = ",".join(fields)
    evidence["csv_text"] = "\n".join(lines) + "\n"
    evidence["manifest"]["raw_sha256"] = sha256(evidence["csv_text"].encode()).hexdigest()
    report = score(data)
    prediction = report["runs"][1]["conditional_voltage_replay"]
    assert prediction is not None
    assert prediction["measured_charge_ah"] is None
    assert prediction["measured_delivered_energy_wh"] is None
    assert not report["claimed_voltage_compatibility_only_samplewise"]
    assert report["decision_equivalent_to_physical_testing"] is False
