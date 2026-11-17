"""M23 HIL software tests use SYNTHETIC data, not a real hardware run."""
from hashlib import sha256
import copy

import pytest
from pydantic import ValidationError

from physics.validation.hil_evidence import (
    HILCampaignRequest, _read_csv, audit_hil_campaign,
)
from physics.validation.validation_protocol import ValidationProtocol, protocol_sha256

CH = ["altitude_m", "vertical_speed_m_s", "attitude_error_deg"]


def protocol():
    return {
        "schema_version": "1.0",
        "protocol_id": "synthetic_controller_hil",
        "intended_engineering_decision": "Test an uncrewed multirotor controller only within a declared operating envelope",
        "frozen_model_git_sha": "a" * 40,
        "frozen_design_sha256": "b" * 64,
        "frozen_controller_configuration_sha256": "c" * 64,
        "envelope": {
            "ambient_temperature_c": [10, 40], "air_density_kg_m3": [1, 1.3],
            "wind_speed_m_s": [0, 5], "payload_kg": [0, 2], "altitude_m": [0, 30],
        },
        "hardware": [
            {"role": "controller", "model": "synthetic_firmware", "quantity": 1,
             "serial_or_lot": f"controller_{k}", "geometry_or_firmware_revision": "v1"}
            for k in range(3)
        ],
        "instruments": [
            {"channel": ch, "manufacturer_model": f"synthetic_meter_{ch}",
             "serial": f"sensor_{ch}", "calibration_reference": "synthetic://no-actual-certificate",
             "calibration_date_utc": "2026-11-17", "bandwidth_hz": 50,
             "clock_alignment_bound_s": 0}
            for ch in CH
        ],
        "uncertainties": [
            {"channel": ch, "name": "synthetic_absolute", "absolute_value": .01,
             "type": "hard_absolute_bound", "source_reference": "synthetic://math"}
            for ch in CH
        ],
        "acceptance_metrics": [
            {"channel": ch, "maximum_absolute_prediction_error": .2,
             "minimum_holdout_samples": 6, "maximum_sampling_gap_s": 1}
            for ch in CH
        ],
        "experiments": [
            {"experiment_id": f"exp_{k}", "recording_id": f"rec_{k}",
             "vehicle_id": f"vehicle_{k}", "battery_id": f"battery_{k}",
             "role": "calibration" if k == 0 else "holdout",
             "scenario": "synthetic controller trajectory"}
            for k in range(3)
        ],
    }


def record(k, *, fake_physical=False, offset=0):
    rows = ["t_s,altitude_m,vertical_speed_m_s,attitude_error_deg"]
    predicted = rows[:]
    for t in range(6):
        rows.append(f"{t},{k+t*.5:.3f},{.5+.01*k:.3f},{1+.02*k:.3f}")
        predicted.append(
            f"{t},{k+t*.5+offset:.3f},{.5+.01*k:.3f},{1+.02*k:.3f}"
        )
    o = "\n".join(rows) + "\n"
    p = "\n".join(predicted) + "\n"
    return {
        "dataset_id": f"fixture_{k}",
        "dataset_kind": "reported_physical_measurements" if fake_physical else "synthetic_fixture",
        "role": "calibration" if k == 0 else "holdout",
        "experiment_id": f"exp_{k}", "recording_id": f"rec_{k}",
        "vehicle_id": f"vehicle_{k}", "battery_id": f"battery_{k}",
        "controller_serial": f"controller_{k}",
        "firmware_version": "synthetic_v1",
        "controller_config_sha256": "c" * 64,
        "source_reference": "synthetic code fixture, no actual instrument",
        "instrument_reference": "synthetic uncalibrated instruments",
        "hardware_match_self_reported": True,
        "unused_for_calibration_self_reported": k != 0,
        "observation_sha256": sha256(o.encode()).hexdigest(),
        "prediction_sha256": sha256(p.encode()).hexdigest(),
        "observed_csv": o, "predicted_csv": p,
    }


def body(physical=False):
    p = protocol()
    return {
        "frozen_protocol": p,
        "expected_frozen_sha256": protocol_sha256(ValidationProtocol.model_validate(p)),
        "channels": CH,
        "runs": [record(k, fake_physical=physical) for k in range(3)],
    }


def score(data=None):
    return audit_hil_campaign(HILCampaignRequest.model_validate(data or body()))


def test_perfect_synthetic_trajectory_not_physical_validation():
    result = score()
    assert result["status"] == "HIL_CONTROLLER_PHYSICAL_VALIDATION_NOT_ESTABLISHED"
    assert result["simulation_only_test_mode"]
    assert not result["all_reported_holdouts_compatible_declared_samplewise_bounds"]
    assert not result["independent_physical_flight_validation_established"]
    assert not result["flight_safety_certified"]
    assert not result["commands_sent_to_hardware"]
    assert len(result["runs"]) == 3
    assert result["runs"][1]["channel_errors"]["altitude_m"]["mae"] == 0
    assert result["runs"][2]["channel_errors"]["altitude_m"]["sample_count"] == 6


def test_spoofed_physical_labels_only_grant_reported_samplewise_screen():
    report = score(body(physical=True))
    assert report["all_reported_holdouts_compatible_declared_samplewise_bounds"]
    assert not report["independent_physical_flight_validation_established"]
    assert not report["flight_safety_certified"]
    assert report["blockers"]


def test_time_mismatch_and_hash_tampering_fail_closed():
    p = body(physical=True)
    p["runs"][1]["observed_csv"] += "\n"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        score(p)
    p = body(physical=True)
    p["runs"][1]["predicted_csv"] = p["runs"][1]["predicted_csv"].replace(
        "1,1.500", "1,1.550", 1
    )
    p["runs"][1]["prediction_sha256"] = sha256(p["runs"][1]["predicted_csv"].encode()).hexdigest()
    res = score(p)
    assert "Prediction and observation clocks" not in str(res["runs"][1]["blockers"])
    assert res["runs"][1]["channel_errors"]["altitude_m"]["mae"] > 0


def test_unaligned_timestamps_do_not_score():
    p = body(physical=True)
    changed = p["runs"][1]["predicted_csv"].replace("1,1.500", "1.1,1.500", 1)
    p["runs"][1]["predicted_csv"] = changed
    p["runs"][1]["prediction_sha256"] = sha256(changed.encode()).hexdigest()
    res = score(p)
    assert not res["all_reported_holdouts_compatible_declared_samplewise_bounds"]
    assert any("clocks" in x for x in res["runs"][1]["blockers"])


def test_large_controller_discrepancy_blocks_reported_compatibility():
    p = body(physical=True)
    p["runs"][1] = record(1, fake_physical=True, offset=5)
    res = score(p)
    assert not res["all_reported_holdouts_compatible_declared_samplewise_bounds"]
    assert "Undemonstrated preregistered bounds or sampling for altitude_m" in res["runs"][1]["blockers"]


def test_calibration_holdout_overlap_exposed():
    p = body(physical=True)
    p["runs"][1]["controller_serial"] = p["runs"][0]["controller_serial"]
    res = score(p)
    assert res["calibration_holdout_collisions"]
    assert not res["all_reported_holdouts_compatible_declared_samplewise_bounds"]


def test_model_freeze_and_instrument_clock_uncertainty_are_blockers():
    p = body(physical=True)
    p["frozen_protocol"]["instruments"][0]["clock_alignment_bound_s"] = .05
    res = score(p)
    assert not res["matches_supplied_preregistration_digest"]
    assert any("positive clock uncertainty" in s for s in res["blockers"])
    assert not res["independent_physical_flight_validation_established"]


def test_minimum_holdout_sample_gate_enforced():
    p = body(physical=True)
    p["frozen_protocol"]["acceptance_metrics"][0]["minimum_holdout_samples"] = 8
    p["expected_frozen_sha256"] = protocol_sha256(
        ValidationProtocol.model_validate(p["frozen_protocol"])
    )
    res = score(p)
    assert not res["all_reported_holdouts_compatible_declared_samplewise_bounds"]


@pytest.mark.parametrize("changed,reason", [
    (lambda rows: rows.replace("0,0.000", "1,0.000", 1), "timestamps"),
    (lambda rows: rows.replace("1,0.500", "0,0.500", 1), "timestamps"),
    (lambda rows: rows.replace("1,0.500", "1,nan", 1), "nonfinite"),
    (lambda rows: rows.replace("1,0.500", "1,inf", 1), "nonfinite"),
    (lambda rows: rows.replace("1,0.500", "1,0.500,0", 1), "incomplete"),
    (lambda rows: rows.replace("t_s,altitude_m", "t_s,wrong_units", 1), "CSV header"),
])
def test_untrusted_csv_rejected_with_correct_original_hash(changed, reason):
    p = body()
    run = p["runs"][0]
    run["observed_csv"] = changed(run["observed_csv"])
    run["observation_sha256"] = sha256(run["observed_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match=reason):
        score(p)


@pytest.mark.parametrize("change", [
    lambda d: d.update({"expected_frozen_sha256": "z" * 64}),
    lambda d: d["runs"][0].update({"controller_config_sha256": "bad"}),
    lambda d: d.update({"channels": ["altitude_m", "altitude_m"]}),
    lambda d: d["runs"][1].update({"dataset_id": d["runs"][0]["dataset_id"]}),
])
def test_schema_rejects_bad_frozen_identifiers(change):
    p = body()
    change(p)
    with pytest.raises(ValidationError):
        HILCampaignRequest.model_validate(p)


def test_inputs_never_mutated():
    p = body()
    original = copy.deepcopy(p)
    score(p)
    assert p == original
