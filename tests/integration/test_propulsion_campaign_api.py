"""M22 endpoint uses manufacturer-table synthetic fixtures, NOT physical holdouts."""
from hashlib import sha256
from fastapi.testclient import TestClient
from app.main import app


def payload():
    rows = [
        (1719, 47.91, 2850, 4.97),
        (1783, 47.90, 3108, 5.54),
        (1849, 47.88, 3331, 6.07),
        (1913, 47.87, 3571, 6.65),
        (1981, 47.87, 3859, 7.29),
    ]
    raw = "rpm,voltage_v,thrust_n,current_a\n" + "".join(
        f"{rpm},{v},{gf*.00980665:.9f},{current}\n"
        for rpm, v, gf, current in rows
    )
    return {
        "motor_id": "tmotor_p80iii_kv100",
        "propeller_id": "tmotor_g30x105_cf",
        "frozen_protocol": {
            "schema_version": "1.0", "protocol_id": "synthetic_p80_api",
            "intended_engineering_decision": "Numerical verification of static powertrain benchmark only",
            "frozen_model_git_sha": "a" * 40, "frozen_design_sha256": "b" * 64,
            "frozen_controller_configuration_sha256": "c" * 64,
            "envelope": {
                "ambient_temperature_c": [0, 40], "air_density_kg_m3": [1, 1.4],
                "wind_speed_m_s": [0, 5], "payload_kg": [0, 2], "altitude_m": [0, 30],
            },
            "hardware": [
                {"role": "motor", "model": "tmotor_p80iii_kv100",
                 "serial_or_lot": "synthetic_motor", "quantity": 1},
                {"role": "propeller", "model": "tmotor_g30x105_cf",
                 "serial_or_lot": "synthetic_prop", "quantity": 1},
            ],
            "instruments": [
                {"channel": ch, "manufacturer_model": "synthetic instrument"}
                for ch in ("thrust_n", "current_a")
            ],
            "uncertainties": [
                {"channel": ch, "name": "synthetic uncertainty",
                 "absolute_value": .01, "type": "hard_absolute_bound",
                 "source_reference": "synthetic://math only"}
                for ch in ("thrust_n", "current_a")
            ],
            "acceptance_metrics": [
                {"channel": ch, "maximum_absolute_prediction_error": 1,
                 "minimum_holdout_samples": 5, "maximum_sampling_gap_s": 1}
                for ch in ("thrust_n", "current_a")
            ],
            "experiments": [
                {"experiment_id": "fake_exp", "recording_id": "fake_record",
                 "vehicle_id": "fake_vehicle", "battery_id": "fake_battery",
                 "role": "holdout", "scenario": "synthetic manufacturer replay"}
            ],
        },
        "runs": [{
            "dataset_id": "synthetic_api",
            "dataset_kind": "synthetic_fixture", "partition_role": "holdout",
            "recording_id": "fake_record", "experiment_id": "fake_exp",
            "vehicle_id": "fake_vehicle", "battery_id": "fake_battery",
            "motor_serial": "synthetic_motor", "propeller_serial": "synthetic_prop",
            "esc_serial": "synthetic_esc", "fixture_id": "synthetic_fixture",
            "source_reference": "manufacturer table numbers copied for synthetic software test",
            "source_permission": "software verification fixture",
            "fixture_description": "synthetic example, no independent bench",
            "source_sha256": sha256(raw.encode()).hexdigest(),
            "csv_text": raw,
            "hardware_match_self_reported": False,
            "unused_for_model_calibration_self_reported": False,
        }],
    }


def test_real_model_static_campaign_endpoint_refuses_manufacturer_data_promotion():
    with TestClient(app) as client:
        r = client.post("/api/components/propulsion-campaign-audit", json=payload())
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["status"] == "PHYSICAL_PROPULSION_VALIDATION_NOT_ESTABLISHED"
    assert result["run_count"] == 1
    assert result["manufacturer_reference_is_calibration_not_validation"] is True
    assert result["independent_static_propulsion_validation_established"] is False
    assert result["flight_readiness_established"] is False
    assert result["model_or_components_modified"] is False


def test_bad_original_csv_digest_and_unknown_motor_are_rejected():
    with TestClient(app) as client:
        data = payload()
        data["runs"][0]["csv_text"] += "\n"
        r = client.post("/api/components/propulsion-campaign-audit", json=data)
        assert r.status_code == 422, r.text
        assert "SHA-256 mismatch" in str(r.json()["detail"])
        data = payload()
        data["motor_id"] = "does_not_exist"
        assert client.post("/api/components/propulsion-campaign-audit", json=data).status_code == 404
        data = payload()
        data["runs"][0]["source_sha256"] = "123"
        assert client.post("/api/components/propulsion-campaign-audit", json=data).status_code == 422
