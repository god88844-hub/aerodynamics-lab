"""M23 controller API only tests synthetic trajectory evidence."""
from hashlib import sha256

from fastapi.testclient import TestClient
from app.main import app


def request():
    rows = "t_s,altitude_m\n" + "".join(f"{t},{t/2}\n" for t in range(6))
    digest = sha256(rows.encode("utf-8")).hexdigest()
    return {
        "frozen_protocol": {
            "schema_version": "1.0", "protocol_id": "synthetic_api_hil",
            "intended_engineering_decision": "Software-only trajectory comparison, not actual controller qualification",
            "frozen_model_git_sha": "a" * 40,
            "frozen_design_sha256": "b" * 64,
            "frozen_controller_configuration_sha256": "c" * 64,
            "envelope": {
                "ambient_temperature_c": [0, 40], "air_density_kg_m3": [1, 1.3],
                "wind_speed_m_s": [0, 4], "payload_kg": [0, 2], "altitude_m": [0, 20],
            },
            "hardware": [{"role": "controller", "model": "synthetic",
                          "serial_or_lot": "synthetic_controller", "quantity": 1}],
            "instruments": [{"channel": "altitude_m", "manufacturer_model": "synthetic sensor"}],
            "uncertainties": [{"channel": "altitude_m", "name": "mathematical",
                               "absolute_value": .01, "type": "hard_absolute_bound"}],
            "acceptance_metrics": [{"channel": "altitude_m", "maximum_absolute_prediction_error": .2,
                                    "minimum_holdout_samples": 6, "maximum_sampling_gap_s": 1}],
            "experiments": [{"experiment_id": "synthetic_exp", "recording_id": "synthetic_rec",
                             "vehicle_id": "synthetic_vehicle", "battery_id": "synthetic_pack",
                             "role": "holdout", "scenario": "synthetic"}],
        },
        "channels": ["altitude_m"],
        "runs": [{
            "dataset_id": "synthetic_run",
            "dataset_kind": "synthetic_fixture", "role": "holdout",
            "experiment_id": "synthetic_exp", "recording_id": "synthetic_rec",
            "vehicle_id": "synthetic_vehicle", "battery_id": "synthetic_pack",
            "controller_serial": "synthetic_controller", "firmware_version": "synthetic_v1",
            "controller_config_sha256": "c" * 64,
            "source_reference": "software-generated data", "instrument_reference": "none",
            "hardware_match_self_reported": False,
            "unused_for_calibration_self_reported": True,
            "observation_sha256": digest, "prediction_sha256": digest,
            "observed_csv": rows, "predicted_csv": rows,
        }],
    }


def test_hil_api_never_grants_real_hardware_control_or_flight_safety():
    with TestClient(app) as client:
        resp = client.post("/api/components/hil-evidence", json=request())
    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j["simulation_only_test_mode"] is True
    assert j["status"] == "HIL_CONTROLLER_PHYSICAL_VALIDATION_NOT_ESTABLISHED"
    assert j["commands_sent_to_hardware"] is False
    assert j["independent_physical_flight_validation_established"] is False
    assert j["all_reported_holdouts_compatible_declared_samplewise_bounds"] is False


def test_hil_api_detects_sha_corruption_and_invalid_headers():
    with TestClient(app) as client:
        payload = request()
        payload["runs"][0]["predicted_csv"] += "\n"
        assert client.post("/api/components/hil-evidence", json=payload).status_code == 422
        payload = request()
        payload["runs"][0]["prediction_sha256"] = "oops"
        assert client.post("/api/components/hil-evidence", json=payload).status_code == 422
