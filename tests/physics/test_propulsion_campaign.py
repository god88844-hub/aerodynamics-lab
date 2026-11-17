"""All M22 observations are SYNTHETIC. 'physical' flags test spoof resistance."""
from __future__ import annotations

from hashlib import sha256
import copy
import math

import pytest
from pydantic import ValidationError
from aeroforge_schemas.component import MotorSpec
from physics.propulsion.dataset import PowertrainDataset
from physics.validation.propulsion_campaign import (
    PropulsionCampaignRequest, audit_propulsion_campaign, read_static_bench,
)
from physics.validation.validation_protocol import ValidationProtocol, protocol_sha256


def dataset():
    rows = []
    for v, rpms in ((10.0, [1000, 1200, 1400, 1600, 1800]),
                    (12.0, [1100, 1300, 1500, 1700, 1900])):
        for idx, rpm in enumerate(rpms):
            current = rpm / 1000 + v / 20
            rows.append({
                "throttle_pct": 50 + 12.5 * idx,
                "voltage_v": v, "current_a": current,
                "power_w": current * v, "thrust_gf": rpm / 2,
                "rpm": rpm, "prop": "SYNTHETIC_PROP",
                "source": {"source": "Synthetic numerical motor fixture", "estimated": True},
            })
    motor = MotorSpec.model_validate({
        "id": "fixture_motor", "name": "Synthetic motor",
        "source": {"source": "Synthetic test-only motor", "estimated": True},
        "test_data": rows,
    })
    return PowertrainDataset(motor, "SYNTHETIC_PROP")


def proto():
    return {
        "schema_version": "1.0", "protocol_id": "synthetic_motor_campaign",
        "intended_engineering_decision": "Compare synthetic RPM-conditioned static motor thrust and current",
        "frozen_model_git_sha": "a" * 40,
        "frozen_design_sha256": "b" * 64,
        "frozen_controller_configuration_sha256": "c" * 64,
        "preregistration_record_reference": "synthetic://precommit",
        "numerical_convergence_report_reference": "synthetic://solver",
        "independent_reviewer_reference": "synthetic://review",
        "approved_test_safety_plan_reference": "synthetic://not-a-real-approval",
        "envelope": {
            "ambient_temperature_c": [0, 40], "air_density_kg_m3": [1, 1.4],
            "wind_speed_m_s": [0, 2], "payload_kg": [0, 1], "altitude_m": [0, 20],
        },
        "hardware": [
            *[{"role": "motor", "model": "fixture_motor", "serial_or_lot": f"motor_{k}",
                "geometry_or_firmware_revision": "v1", "quantity": 1} for k in range(3)],
            *[{"role": "propeller", "model": "fixture_prop", "serial_or_lot": f"prop_{k}",
                "geometry_or_firmware_revision": "v1", "quantity": 1} for k in range(3)],
        ],
        "instruments": [
            {"channel": ch, "manufacturer_model": "synthetic meter",
             "serial": f"meter_{ch}", "calibration_reference": "synthetic://certificate",
             "calibration_date_utc": "2026-11-17", "bandwidth_hz": 50,
             "clock_alignment_bound_s": 0} for ch in ("thrust_n", "current_a")
        ],
        "uncertainties": [
            {"channel": ch, "name": "fixture bound", "absolute_value": .01,
             "type": "hard_absolute_bound", "source_reference": "synthetic://bound"}
            for ch in ("thrust_n", "current_a")
        ],
        "acceptance_metrics": [
            {"channel": "thrust_n", "maximum_absolute_prediction_error": .15,
             "minimum_holdout_samples": 5, "maximum_sampling_gap_s": 1},
            {"channel": "current_a", "maximum_absolute_prediction_error": .15,
             "minimum_holdout_samples": 5, "maximum_sampling_gap_s": 1},
        ],
        "experiments": [
            {"experiment_id": f"exp_{k}", "recording_id": f"rec_{k}",
             "vehicle_id": f"vehicle_{k}", "battery_id": f"pack_{k}",
             "role": "calibration" if k == 0 else "holdout",
             "scenario": "synthetic motor bench"} for k in range(3)
        ],
    }


def trace(k, *, physical=False, motor=None, bias_thrust=0):
    d = motor or dataset()
    rows = ["rpm,voltage_v,thrust_n,current_a"]
    for rpm in (1150, 1250, 1350, 1450, 1550, 1650):
        thrust = d.thrust_gf(rpm).value * 0.00980665 + bias_thrust + .0001 * k
        current = d.current_a(rpm, 11.0).value + .001 * k
        rows.append(f"{rpm},11,{thrust:.9f},{current:.9f}")
    raw = "\n".join(rows) + "\n"
    return {
        "dataset_id": f"fixture_{k}",
        "dataset_kind": (
            "reported_physical_measurements" if physical else "synthetic_fixture"
        ),
        "partition_role": "calibration" if k == 0 else "holdout",
        "recording_id": f"rec_{k}", "experiment_id": f"exp_{k}",
        "vehicle_id": f"vehicle_{k}", "battery_id": f"pack_{k}",
        "motor_serial": f"motor_{k}", "propeller_serial": f"prop_{k}",
        "esc_serial": f"esc_{k}", "fixture_id": f"fixture_id_{k}",
        "source_reference": "synthetic analytical observations, NOT measured",
        "source_permission": "self-generated fixture",
        "fixture_description": "synthetic mathematical verification, not a real stand",
        "source_sha256": sha256(raw.encode()).hexdigest(),
        "csv_text": raw,
        "hardware_match_self_reported": True,
        "unused_for_model_calibration_self_reported": k != 0,
        "ambient_air_density_kg_m3": 1.225,
        "ambient_temperature_c": 25,
    }


def request(*, physical=False, p=None):
    proto_json = p or proto()
    return {
        "motor_id": "fixture_motor", "propeller_id": "fixture_prop",
        "frozen_protocol": proto_json,
        "expected_frozen_sha256": protocol_sha256(
            ValidationProtocol.model_validate(proto_json)
        ),
        "runs": [trace(k, physical=physical) for k in range(3)],
    }


def score(body=None, dataset_reference=None):
    return audit_propulsion_campaign(
        dataset_reference or dataset(),
        PropulsionCampaignRequest.model_validate(body or request())
    )


def test_synthetic_study_reports_comparisons_but_not_physical_validation():
    d = dataset()
    original = d.motor.model_dump_json()
    report = score(dataset_reference=d)
    assert report["status"] == "PHYSICAL_PROPULSION_VALIDATION_NOT_ESTABLISHED"
    assert report["run_count"] == 3
    assert report["holdout_count"] == 2
    assert not report["independent_static_propulsion_validation_established"]
    assert not report["dynamic_propulsion_validation_established"]
    assert not report["flight_readiness_established"]
    assert not report["model_or_components_modified"]
    assert all(r["scored_count"] == 6 for r in report["runs"])
    assert all(r["unsupported"] == [] for r in report["runs"])
    assert all(r["overlaps_reference_manufacturer_operating_points"] == 0 for r in report["runs"])
    assert d.motor.model_dump_json() == original


def test_fake_physical_provenance_cannot_validate_motor():
    report = score(request(physical=True))
    assert report["all_holdout_samples_compatible_declared_bounds_only"] is True
    assert report["independent_static_propulsion_validation_established"] is False
    assert report["flight_readiness_established"] is False
    assert report["blockers"]


def test_source_hash_tampering_rejected_before_comparison():
    body = request()
    body["runs"][1]["csv_text"] += "\n"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        score(body)


def test_unmatched_rpm_fails_without_extrapolating():
    body = request(physical=True)
    run = body["runs"][1]
    run["csv_text"] = run["csv_text"].replace("1150,11", "99999,11")
    run["source_sha256"] = sha256(run["csv_text"].encode()).hexdigest()
    report = score(body)
    assert report["runs"][1]["unsupported"]
    assert not report["runs"][1]["samplewise_compatible"]
    assert not report["all_holdout_samples_compatible_declared_bounds_only"]


def test_large_independent_thrust_discrepancy_is_not_a_pass():
    body = request(physical=True)
    body["runs"][1] = trace(1, physical=True, bias_thrust=.5)
    report = score(body)
    assert not report["all_holdout_samples_compatible_declared_bounds_only"]
    assert any("discrepancy exceeds" in reason for reason in report["runs"][1]["blockers"])


def test_same_test_fixture_cross_partition_leaks():
    body = request(physical=True)
    body["runs"][1]["fixture_id"] = body["runs"][0]["fixture_id"]
    report = score(body)
    assert report["calibration_holdout_collisions"]
    assert "fixture_id" in report["calibration_holdout_collisions"][0]["shared_groups"]
    assert not report["all_holdout_samples_compatible_declared_bounds_only"]


def test_frozen_registration_mutation_cannot_be_silent():
    body = request(physical=True)
    body["frozen_protocol"]["acceptance_metrics"][0]["maximum_absolute_prediction_error"] = 10
    report = score(body)
    assert not report["matches_supplied_frozen_protocol_digest"]
    assert not report["all_holdout_samples_compatible_declared_bounds_only"]
    assert not report["independent_static_propulsion_validation_established"]


@pytest.mark.parametrize("change,match", [
    (lambda r: r["csv_text"].replace("rpm,voltage_v,thrust_n,current_a", "rpm,thrust_n,current_a,voltage_v"), "exactly"),
    (lambda r: r["csv_text"].replace("1150,11", "nan,11"), "nonfinite"),
    (lambda r: r["csv_text"].replace("1150,11", "-1150,11"), "nonfinite"),
    (lambda r: r["csv_text"].replace("1250,11", "1150,11"), "duplicated RPM"),
    (lambda r: "rpm,voltage_v,thrust_n,current_a\n" + "1,1,1,1\n"*4, "5"),
])
def test_bad_reported_data_cannot_be_scored(change, match):
    run = trace(0)
    run["csv_text"] = change(run)
    run["source_sha256"] = sha256(run["csv_text"].encode()).hexdigest()
    with pytest.raises(ValueError, match=match):
        read_static_bench(PropulsionCampaignRequest.model_validate({
            **request(), "runs": [run],
        }).runs[0])


def test_negative_or_missing_protocol_fields_block_conclusion():
    body = request(physical=True)
    body["runs"][0]["source_sha256"] = "z" * 64
    with pytest.raises(ValidationError):
        PropulsionCampaignRequest.model_validate(body)
    body = request(physical=True)
    body["runs"][1]["recording_id"] = body["runs"][0]["recording_id"]
    with pytest.raises(ValidationError):
        PropulsionCampaignRequest.model_validate(body)


def test_model_and_request_are_unchanged():
    data = request(physical=True)
    d = dataset()
    snapshot = copy.deepcopy(data)
    before = d.motor.model_dump_json()
    score(data, d)
    assert data == snapshot
    assert d.motor.model_dump_json() == before


def test_preregistered_minimum_holdout_points_cannot_be_bypassed():
    body = request(physical=True)
    # Six supplied physical-labelled operating points are fewer than
    # the frozen requirement of seven, even if all six match the model.
    body["frozen_protocol"]["acceptance_metrics"][0]["minimum_holdout_samples"] = 7
    body["expected_frozen_sha256"] = protocol_sha256(
        ValidationProtocol.model_validate(body["frozen_protocol"])
    )
    report = score(body)
    assert not report["all_holdout_samples_compatible_declared_bounds_only"]
    for run in report["runs"]:
        if run["role"] == "holdout":
            assert any("Insufficient holdout operating points for thrust_n" in b
                       for b in run["blockers"])
    assert not report["independent_static_propulsion_validation_established"]
