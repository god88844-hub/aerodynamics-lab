"""M21 API: synthetic software evidence only, not a battery experiment."""
from hashlib import sha256

from fastapi.testclient import TestClient
from app.main import app


def payload():
    csv = "t_s,terminal_voltage_v,current_a,temperature_c\n" + "".join(
        f"{i*60},{25-i*.05},5,25\n" for i in range(6)
    )
    return {
        "battery_model_id": "generic_6s_lipo_16000mah",
        "frozen_protocol": {
            "schema_version": "1.0", "protocol_id": "synthetic_api",
            "intended_engineering_decision": "Synthetic voltage audit, not real-world validation",
            "frozen_model_git_sha": "a" * 40,
            "frozen_design_sha256": "b" * 64,
            "frozen_controller_configuration_sha256": "c" * 64,
            "envelope": {
                "ambient_temperature_c": [0, 40], "air_density_kg_m3": [1, 1.3],
                "wind_speed_m_s": [0, 4], "payload_kg": [0, 2], "altitude_m": [0, 50],
            },
            "hardware": [{
                "role": "battery", "model": "generic_6s_lipo_16000mah",
                "serial_or_lot": "fake_pack", "quantity": 1,
                "geometry_or_firmware_revision": "none",
            }],
            "instruments": [{
                "channel": "terminal_voltage_v",
                "manufacturer_model": "synthetic instrument",
            }],
            "uncertainties": [{
                "name": "numerical fixture", "channel": "terminal_voltage_v",
                "absolute_value": .05, "type": "hard_absolute_bound",
            }],
            "acceptance_metrics": [{
                "channel": "terminal_voltage_v",
                "maximum_absolute_prediction_error": .2,
                "minimum_holdout_samples": 6,
                "maximum_sampling_gap_s": 65,
            }],
            "experiments": [{
                "experiment_id": "fake_exp", "recording_id": "fake_record",
                "vehicle_id": "fake_vehicle", "battery_id": "fake_pack",
                "role": "holdout", "scenario": "fake bench",
            }],
        },
        "runs": [{
            "evidence": {
                "manifest": {
                    "schema_version": "1.0", "dataset_id": "synthetic_api",
                    "dataset_kind": "synthetic_fixture",
                    "partition_role": "holdout",
                    "experiment_id": "fake_exp", "recording_id": "fake_record",
                    "vehicle_id": "fake_vehicle", "battery_id": "fake_pack",
                    "source_reference": "generated synthetic data, not an actual experiment",
                    "license_or_permission": "synthetic test",
                    "filename": "trace.csv",
                    "raw_sha256": sha256(csv.encode()).hexdigest(),
                    "expected_samples": 6, "predeclared_max_sample_gap_s": 65,
                    "columns": ["t_s", "terminal_voltage_v", "current_a", "temperature_c"],
                },
                "csv_text": csv,
            },
            "initial_soc_pct": 100,
            "hardware_match_self_reported": False,
            "unused_for_calibration_self_reported": False,
            "illustrative_endpoint_error_limit_pct": 5,
        }],
    }


def test_campaign_route_reports_missing_evidence_never_releases_aircraft():
    with TestClient(app) as client:
        r = client.post("/api/components/battery-campaign-audit", json=payload())
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["campaign_status"] == "PHYSICAL_BATTERY_VALIDATION_NOT_ESTABLISHED"
    assert report["generic_or_estimated_pack_reference"] is True
    assert report["decision_equivalent_to_physical_testing"] is False
    assert report["source_count"] == 1
    assert report["blockers"]
    assert report["existing_battery_model_modified"] is False


def test_campaign_route_rejects_unverified_source_and_unknown_pack():
    with TestClient(app) as client:
        b = payload()
        b["runs"][0]["evidence"]["csv_text"] += "\n"
        r = client.post("/api/components/battery-campaign-audit", json=b)
        assert r.status_code == 422, r.text
        assert "SHA-256" in str(r.json()["detail"])
        b = payload()
        b["battery_model_id"] = "pack_does_not_exist"
        assert client.post("/api/components/battery-campaign-audit", json=b).status_code == 404
        b = payload()
        b["runs"][0]["initial_soc_pct"] = 101
        assert client.post("/api/components/battery-campaign-audit", json=b).status_code == 422
