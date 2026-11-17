"""M19 endpoint integration: all test measurements are SYNTHETIC fixtures."""
from hashlib import sha256

from fastapi.testclient import TestClient

from app.main import app


def fake_bundle(id="fixture_a", kind="synthetic_fixture", role="calibration",
                tag="A", voltage=12):
    csv_text = "t_s,terminal_voltage_v,current_a\n" + "".join(
        f"{x},{voltage},2\n" for x in range(6)
    )
    return {
        "manifest": {
            "schema_version": "1.0",
            "dataset_id": id,
            "dataset_kind": kind,
            "partition_role": role,
            "experiment_id": f"exp-{tag}",
            "recording_id": f"rec-{tag}",
            "vehicle_id": f"vehicle-{tag}",
            "battery_id": f"pack-{tag}",
            "source_reference": "synthetic math fixture; not flight data",
            "license_or_permission": "self-generated synthetic fixture",
            "filename": "trace.csv",
            "raw_sha256": sha256(csv_text.encode("utf-8")).hexdigest(),
            "expected_samples": 6,
            "predeclared_max_sample_gap_s": 2,
            "columns": ["t_s", "terminal_voltage_v", "current_a"],
        },
        "csv_text": csv_text,
    }


def test_api_ingests_original_sha_pinned_trace_without_promoting_physical_validation():
    with TestClient(app) as client:
        r = client.post("/api/components/telemetry-audit", json={
            "datasets": [fake_bundle()]
        })
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["datasets"][0]["rows"] == 6
        assert out["datasets"][0]["status"] == "SYNTHETIC_VERIFICATION_ONLY"
        assert out["datasets"][0]["observations"]["trapezoidal_reported_energy_wh"] > 0
        assert out["partition"]["status"] == "NO_COMPLETE_CALIBRATION_HOLDOUT_SPLIT"
        assert out["near_real_world_simulation_accuracy_established"] is False


def test_api_cross_recording_leakage_never_becomes_validation():
    a = fake_bundle(kind="reported_physical_measurements")
    b = fake_bundle(id="fixture_b", kind="reported_physical_measurements",
                    role="holdout", tag="B", voltage=11)
    b["manifest"]["vehicle_id"] = a["manifest"]["vehicle_id"]
    with TestClient(app) as client:
        r = client.post("/api/components/telemetry-audit", json={
            "datasets": [a, b],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["partition"]["status"] == "CROSS_PARTITION_LEAKAGE_DECLARED"
        assert body["partition"]["cross_partition_collisions"]
        assert body["partition"]["physical_validation_established"] is False


def test_api_returns_422_for_tampering_and_missing_timestamps():
    with TestClient(app) as client:
        a = fake_bundle()
        a["csv_text"] = a["csv_text"].replace("1,12,2", "1,13,2")
        r = client.post("/api/components/telemetry-audit", json={
            "datasets": [a]
        })
        assert r.status_code == 422
        assert "SHA-256" in r.json()["detail"]
        a = fake_bundle()
        a["manifest"]["columns"] = [
            "terminal_voltage_v", "current_a", "wind_speed_m_s",
        ]
        assert client.post("/api/components/telemetry-audit", json={
            "datasets": [a]
        }).status_code == 422
        a = fake_bundle()
        a["manifest"]["filename"] = "../../secrets.csv"
        assert client.post("/api/components/telemetry-audit", json={
            "datasets": [a]
        }).status_code == 422
