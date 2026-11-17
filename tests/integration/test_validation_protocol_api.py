"""M20 read-only API; fixtures contain no real physical experimental evidence."""
from fastapi.testclient import TestClient
from app.main import app


def plan():
    return {
        "schema_version": "1.0", "protocol_id": "synthetic_protocol",
        "intended_engineering_decision": "Predict a multirotor hover inside bounded experiments",
        "frozen_model_git_sha": "a" * 40, "frozen_design_sha256": "b" * 64,
        "frozen_controller_configuration_sha256": "c" * 64,
        "envelope": {
            "ambient_temperature_c": [0, 30], "air_density_kg_m3": [1, 1.3],
            "wind_speed_m_s": [0, 3], "payload_kg": [0, 2], "altitude_m": [0, 40],
        },
        "hardware": [{"role": "battery", "model": "synthetic-pack", "quantity": 1}],
        "instruments": [{"channel": "current_a", "manufacturer_model": "synthetic-meter"}],
        "uncertainties": [{"channel": "current_a", "name": "fixture",
                           "absolute_value": .01, "type": "hard_absolute_bound"}],
        "acceptance_metrics": [{
            "channel": "current_a", "maximum_absolute_prediction_error": .2,
            "minimum_holdout_samples": 6, "maximum_sampling_gap_s": 1,
        }],
        "experiments": [{
            "experiment_id": "fixture_experiment", "recording_id": "fixture_recording",
            "vehicle_id": "fixture_vehicle", "battery_id": "fixture_battery",
            "role": "calibration", "scenario": "synthetic",
        }],
    }


def test_preregistration_endpoint_fails_closed_without_real_evidence():
    with TestClient(app) as client:
        response = client.post("/api/components/validation-protocol-audit", json={"protocol": plan()})
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["readiness_status"] == "PREREGISTRATION_GAPS"
    assert report["blockers"]
    assert report["independently_approved"] is False
    assert report["independent_physical_accuracy_demonstrated"] is False
    assert report["decision_equivalent_to_physical_testing"] is False
    assert len(report["canonical_protocol_sha256"]) == 64


def test_bad_schema_or_unknown_fields_are_rejected():
    data = plan()
    data["uncertainties"][0]["absolute_value"] = -1
    with TestClient(app) as client:
        assert client.post("/api/components/validation-protocol-audit", json={"protocol": data}).status_code == 422
        data = plan()
        data["frozen_model_git_sha"] = "../../bad"
        assert client.post("/api/components/validation-protocol-audit", json={"protocol": data}).status_code == 422
        data = plan()
        data["not_a_real_signature"] = True
        assert client.post("/api/components/validation-protocol-audit", json={"protocol": data}).status_code == 422


def test_supplied_mismatching_lock_detected():
    with TestClient(app) as client:
        response = client.post("/api/components/validation-protocol-audit", json={
            "protocol": plan(), "expected_frozen_sha256": "0" * 64,
        })
    assert response.status_code == 200, response.text
    assert response.json()["readiness_status"] == "FROZEN_PROTOCOL_TAMPERED"
