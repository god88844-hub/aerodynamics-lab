"""API tests use SYNTHETIC discharge data only, never physical evidence."""
from pathlib import Path

from fastapi.testclient import TestClient

from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import BatteryPack

ROOT = Path(__file__).resolve().parents[2]


def _body():
    from physics.propulsion.loader import ComponentLibrary
    spec = ComponentLibrary(ROOT / "data" / "components").battery("generic_6s_lipo_16000mah")
    pack = BatteryPack(spec)
    points = []
    for i in range(6):
        t = i * 60
        soc = 100 - 100 * (5 * t / (3600 * spec.capacity_ah))
        points.append({
            "t_s": t, "current_a": 5,
            "terminal_voltage_v": pack.voltage_under_load(soc, 5),
        })
    return {
        "battery_id": spec.id,
        "dataset_kind": "synthetic_fixture",
        "battery_serial_or_id": "synthetic_pack_fixture",
        "run_id": "synthetic_run_1",
        "data_source": "synthetic numerical verification, not physical measurement",
        "model_unused_for_calibration": True,
        "hardware_matches_reference_spec": True,
        "initial_soc_pct": 100,
        "predeclared_max_abs_voltage_error_v": .2,
        "predeclared_max_endpoint_time_error_pct": 5,
        "predeclared_max_sample_gap_s": 65,
        "samples": points,
    }


def test_discharge_replay_endpoint_is_read_only_and_reports_accounting():
    from app.main import app
    with TestClient(app) as client:
        body = _body()
        r = client.post("/api/components/discharge-replay", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
        assert out["accounting"]["charge_consumed_ah"] == 5 * 300 / 3600
        assert out["existing_component_modified"] is False
        assert out["existing_flight_predictions_modified"] is False


def test_discharge_replay_invalid_and_unknown_reference_are_rejected():
    from app.main import app
    with TestClient(app) as client:
        body = _body()
        body["samples"][1]["t_s"] = body["samples"][0]["t_s"]
        assert client.post("/api/components/discharge-replay", json=body).status_code == 422
        body = _body()
        body["battery_id"] = "nonexistent"
        assert client.post("/api/components/discharge-replay", json=body).status_code == 404
        body["battery_id"] = "../../unsafe"
        assert client.post("/api/components/discharge-replay", json=body).status_code == 422
