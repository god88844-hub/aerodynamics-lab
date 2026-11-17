"""All HIL recordings are synthetic, even when their kind is spoofed 'physical'."""
from hashlib import sha256
import copy

import pytest
from pydantic import ValidationError

from physics.validation.hil_tracking_quality import (
    HILCampaignRequest, audit_hil_campaign,
)
from physics.validation.validation_protocol import ValidationProtocol, protocol_sha256


def protocol():
    return {
        "schema_version": "1.0", "protocol_id": "synthetic_hil_protocol",
        "intended_engineering_decision": "Measure synthetic controller tracking, not aircraft prediction",
        "frozen_model_git_sha": "a"*40, "frozen_design_sha256": "b"*64,
        "frozen_controller_configuration_sha256": "c"*64,
        "preregistration_record_reference": "synthetic://precommit",
        "numerical_convergence_report_reference": "synthetic://convergence",
        "independent_reviewer_reference": "synthetic://review",
        "approved_test_safety_plan_reference": "synthetic://approval-not-real",
        "envelope": {
            "ambient_temperature_c": [0, 40], "air_density_kg_m3": [1, 1.3],
            "wind_speed_m_s": [0, 5], "payload_kg": [0, 2], "altitude_m": [0, 40],
        },
        "hardware": [
            {"role": "controller", "model": "fixture_flight_controller",
             "serial_or_lot": f"controller_{k}", "quantity": 1,
             "geometry_or_firmware_revision": "fixture_fw_1"}
            for k in range(3)
        ],
        "instruments": [
            {"channel": "attitude_error_deg", "manufacturer_model": "synthetic IMU",
             "serial": "synthetic_master", "calibration_reference": "synthetic://imu-cal",
             "calibration_date_utc": "2026-11-17", "bandwidth_hz": 100,
             "clock_alignment_bound_s": 0}
        ],
        "uncertainties": [
            {"channel": "attitude_error_deg", "name": "synthetic bound",
             "absolute_value": .1, "type": "hard_absolute_bound",
             "source_reference": "synthetic://bound"}
        ],
        "acceptance_metrics": [
            {"channel": "attitude_error_deg",
             "maximum_absolute_prediction_error": 2.0,
             "minimum_holdout_samples": 6, "maximum_sampling_gap_s": .05}
        ],
        "experiments": [
            {"experiment_id": f"experiment_{k}", "recording_id": f"recording_{k}",
             "vehicle_id": f"vehicle_{k}", "battery_id": f"battery_{k}",
             "role": "calibration" if k == 0 else "holdout",
             "scenario": "synthetic HIL mathematical fixture"}
            for k in range(3)
        ],
    }


def recording(k, *, physical=False):
    rows = ["t_s,command_roll_deg,observed_roll_deg,command_pitch_deg,observed_pitch_deg,saturation_flag"]
    rows += [f"{i*.01:.3f},{10+.01*k:.3f},{10.1+.01*k:.3f},2,2.1,0" for i in range(10)]
    csv = "\n".join(rows) + "\n"
    return {
        "dataset_id": f"fixture_{k}", "dataset_kind": (
            "reported_physical_hil" if physical else "synthetic_fixture"),
        "role": "calibration" if k == 0 else "holdout",
        "experiment_id": f"experiment_{k}", "recording_id": f"recording_{k}",
        "vehicle_id": f"vehicle_{k}", "battery_id": f"battery_{k}",
        "controller_serial": f"controller_{k}", "firmware_revision": "fixture_fw_1",
        "controller_configuration_sha256": "c"*64, "sensor_serial": f"sensor_{k}",
        "calibration_reference": "synthetic://imu-cal",
        "source_reference": "synthetic source, not recorded hardware",
        "source_permission": "self-generated mathematical fixture",
        "source_sha256": sha256(csv.encode()).hexdigest(),
        "csv_text": csv, "expected_samples": 10,
        "declared_max_sampling_gap_s": .05,
        "clock_alignment_error_bound_s": 0,
        "unused_for_calibration_self_reported": k > 0,
        "hardware_matches_frozen_controller_self_reported": True,
    }


def request(physical=False):
    p = protocol()
    return {
        "frozen_protocol": p,
        "expected_frozen_sha256": protocol_sha256(ValidationProtocol.model_validate(p)),
        "recordings": [recording(k, physical=physical) for k in range(3)],
    }


def run(data=None):
    return audit_hil_campaign(HILCampaignRequest.model_validate(data or request()))


def test_synthetic_controller_tracking_is_never_model_accuracy_validation():
    report = run()
    assert report["run_count"] == 3
    assert report["holdout_count"] == 2
    assert report["status"] == "HIL_PHYSICAL_VALIDATION_NOT_ESTABLISHED"
    assert all(x["count"] == 10 for x in report["runs"])
    assert all(x["max_roll_or_pitch_tracking_error_deg"] == pytest.approx(.1)
               for x in report["runs"])
    assert all(x["saturation_count"] == 0 for x in report["runs"])
    assert not report["independent_controller_hardware_validation"]
    assert not report["simulation_prediction_error_measured"]
    assert not report["aircraft_flight_readiness"]
    assert not report["components_or_flight_model_modified"]


def test_physical_metadata_spoof_cannot_validate_flight():
    result = run(request(physical=True))
    assert result["reported_samplewise_tracking_compatible_only"] is True
    assert result["matches_supplied_frozen_digest"] is True
    assert result["independent_controller_hardware_validation"] is False
    assert result["simulation_prediction_error_measured"] is False
    assert result["aircraft_flight_readiness"] is False
    assert result["blockers"]


def test_original_trace_tampering_blocked_before_any_report():
    body = request()
    body["recordings"][1]["csv_text"] += "\n"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        run(body)


@pytest.mark.parametrize("replace,reason", [
    (("command_roll_deg", "wrong_roll"), "exact SI"),
    (("0.010", "0.000"), "strictly increase"),
    (("10.100", "nan"), "nonfinite"),
    (("0.000", "1.000"), "start at zero"),
    ((",0\n", ",2\n"), "saturation flag"),
])
def test_bad_csv_rejected_after_valid_hash(replace, reason):
    body = request()
    r = body["recordings"][1]
    r["csv_text"] = r["csv_text"].replace(*replace, 1)
    r["source_sha256"] = sha256(r["csv_text"].encode()).hexdigest()
    with pytest.raises(ValueError, match=reason):
        run(body)


def test_controller_saturation_blocks_declared_holdout_tracking_compatibility():
    body = request(physical=True)
    r = body["recordings"][1]
    r["csv_text"] = r["csv_text"].replace(",0\n", ",1\n", 1)
    r["source_sha256"] = sha256(r["csv_text"].encode()).hexdigest()
    result = run(body)
    assert result["runs"][1]["saturation_count"] == 1
    assert not result["reported_samplewise_tracking_compatible_only"]


def test_large_tracking_error_fails_frozen_maximum():
    body = request(physical=True)
    r = body["recordings"][1]
    r["csv_text"] = r["csv_text"].replace("10.100", "15.100", 1)
    r["source_sha256"] = sha256(r["csv_text"].encode()).hexdigest()
    result = run(body)
    assert result["runs"][1]["max_roll_or_pitch_tracking_error_deg"] > 2
    assert not result["reported_samplewise_tracking_compatible_only"]


def test_model_digest_and_firmware_mismatch_blocks_consistency():
    body = request(physical=True)
    body["recordings"][1]["controller_configuration_sha256"] = "d"*64
    report = run(body)
    assert not report["reported_samplewise_tracking_compatible_only"]
    assert any("configuration digest" in b for b in report["runs"][1]["blockers"])


def test_cross_holdout_source_and_controller_leakage():
    body = request(physical=True)
    body["recordings"][1]["controller_serial"] = body["recordings"][0]["controller_serial"]
    report = run(body)
    assert report["experiment_group_collisions"]
    assert "controller_serial" in report["experiment_group_collisions"][0]["shared_identifiers"]
    assert not report["reported_samplewise_tracking_compatible_only"]


def test_nonzero_clock_bound_blocks_continuous_time_claim():
    body = request(physical=True)
    body["recordings"][1]["clock_alignment_error_bound_s"] = .02
    report = run(body)
    assert not report["reported_samplewise_tracking_compatible_only"]
    assert any("Clock alignment" in b for b in report["runs"][1]["blockers"])


@pytest.mark.parametrize("edit", [
    lambda r: r["recordings"][1].update({"recording_id": "recording_0"}),
    lambda r: r["recordings"][1].update({"expected_samples": 2}),
    lambda r: r["recordings"][1].update({"source_sha256": "bad"}),
    lambda r: r.update({"not_a_real_certificate": True}),
])
def test_source_schema_rejects_invalid_data(edit):
    body = request()
    edit(body)
    with pytest.raises(ValidationError):
        HILCampaignRequest.model_validate(body)


def test_fixed_original_request_is_not_modified():
    body = request(physical=True)
    original = copy.deepcopy(body)
    run(body)
    assert body == original


def test_duplicate_original_holdout_bytes_fail_independence():
    data = request(physical=True)
    one, two = data["recordings"][1], data["recordings"][2]
    two["csv_text"] = one["csv_text"]
    two["source_sha256"] = one["source_sha256"]
    report = run(data)
    assert any(
        "source_sha256" in x["shared_identifiers"]
        for x in report["experiment_group_collisions"]
    )
    assert report["reported_samplewise_tracking_compatible_only"] is False
    assert report["independent_controller_hardware_validation"] is False
