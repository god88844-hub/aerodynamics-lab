"""API contract uses synthetic controller measurements only."""
from hashlib import sha256

from fastapi.testclient import TestClient
from app.main import app


def payload():
    csv = ("t_s,command_roll_deg,observed_roll_deg,command_pitch_deg,observed_pitch_deg,saturation_flag\n"
           + "".join(f"{i*.01:.3f},10,10.1,2,2.1,0\n" for i in range(6)))
    return {
        "frozen_protocol": {
            "schema_version": "1.0", "protocol_id": "api_hil_synthetic",
            "intended_engineering_decision": "Synthetic control tracking QA; not real hardware evidence",
            "frozen_model_git_sha": "a"*40,
            "frozen_design_sha256": "b"*64,
            "frozen_controller_configuration_sha256": "c"*64,
            "envelope": {
                "ambient_temperature_c": [0, 40], "air_density_kg_m3": [1, 1.3],
                "wind_speed_m_s": [0, 4], "payload_kg": [0, 2], "altitude_m": [0, 20],
            },
            "hardware": [{"role": "controller", "model": "synthetic controller",
                          "serial_or_lot": "synthetic_controller", "quantity": 1,
                          "geometry_or_firmware_revision": "test firmware"}],
            "instruments": [{"channel": "attitude_error_deg",
                             "manufacturer_model": "synthetic IMU"}],
            "uncertainties": [{"channel": "attitude_error_deg", "name": "fixture",
                               "absolute_value": .1, "type": "hard_absolute_bound"}],
            "acceptance_metrics": [{
                "channel": "attitude_error_deg",
                "maximum_absolute_prediction_error": 2,
                "minimum_holdout_samples": 6, "maximum_sampling_gap_s": .02,
            }],
            "experiments": [{
                "experiment_id": "synthetic_exp", "recording_id": "synthetic_record",
                "vehicle_id": "synthetic_vehicle", "battery_id": "synthetic_pack",
                "role": "holdout", "scenario": "synthetic tracking",
            }],
        },
        "recordings": [{
            "dataset_id": "synthetic_hil",
            "dataset_kind": "synthetic_fixture",
            "role": "holdout", "experiment_id": "synthetic_exp",
            "recording_id": "synthetic_record", "vehicle_id": "synthetic_vehicle",
            "battery_id": "synthetic_pack", "controller_serial": "synthetic_controller",
            "firmware_revision": "test firmware",
            "controller_configuration_sha256": "c"*64,
            "sensor_serial": "synthetic_sensor",
            "source_reference": "numerically generated fixture",
            "source_permission": "self-generated synthetic",
            "source_sha256": sha256(csv.encode()).hexdigest(),
            "csv_text": csv, "expected_samples": 6,
            "declared_max_sampling_gap_s": .02,
            "unused_for_calibration_self_reported": True,
            "hardware_matches_frozen_controller_self_reported": False,
        }],
    }


def test_controller_hil_endpoint_is_always_explicitly_unvalidated():
    with TestClient(app) as client:
        response = client.post("/api/components/hil-tracking-quality", json=payload())
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "HIL_PHYSICAL_VALIDATION_NOT_ESTABLISHED"
    assert result["run_count"] == 1
    assert result["runs"][0]["count"] == 6
    assert result["simulation_prediction_error_measured"] is False
    assert result["aircraft_flight_readiness"] is False


def test_invalid_controller_trace_is_rejected_before_scoring():
    with TestClient(app) as client:
        data = payload()
        data["recordings"][0]["csv_text"] += "\n"
        response = client.post("/api/components/hil-tracking-quality", json=data)
        assert response.status_code == 422, response.text
        assert "SHA-256" in str(response.json()["detail"])
        data = payload()
        data["recordings"][0]["expected_samples"] = 3
        assert client.post("/api/components/hil-tracking-quality", json=data).status_code == 422
