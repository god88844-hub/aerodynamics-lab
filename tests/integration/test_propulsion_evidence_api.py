"""M14 HTTP contract tests; synthetic fixtures are not physical evidence."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from physics.propulsion.loader import ComponentLibrary
from physics.propulsion.dataset import PowertrainDataset

ROOT = Path(__file__).resolve().parents[2]


def case():
    lib = ComponentLibrary(ROOT / "data" / "components")
    motor = lib.motor("tmotor_mn3508_kv380")
    prop = lib.propeller("tmotor_p15x5_cf")
    ds = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    points = []
    for i, rpm in enumerate([4000, 4100, 4200, 4300, 4400]):
        voltage = 14.8
        points.append({
            "id": f"math{i}", "rpm": rpm, "voltage_v": voltage,
            "thrust_gf": ds.thrust_gf(rpm).value,
            "current_a": ds.current_a(rpm, voltage).value,
        })
    return {
        "motor_id": motor.id, "propeller_id": prop.id,
        "dataset_kind": "synthetic_fixture",
        "independent_run_id": "generated_math_holdout", 
        "evidence_source": "synthetic API verification only",
        "hardware_matches_selected_components": True,
        "unused_for_model_calibration": True,
        "predeclared_max_thrust_error_pct": 5,
        "predeclared_max_current_error_pct": 5,
        "observations": points,
    }


def test_http_prediction_report_and_readonly_reference_model():
    body = case()
    with TestClient(app) as c:
        r = c.post("/api/components/propulsion-evidence", json=body)
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
        assert out["model_of_record"]["reference_dataset_is_calibration_not_validation"]
        assert out["evidence"]["scored_count"] == 5
        assert not out["simulation_modified"]
        body["motor_id"] = "not_existing"
        assert c.post("/api/components/propulsion-evidence", json=body).status_code == 404
        body["motor_id"] = "tmotor_mn3508_kv380"
        body["observations"][0]["rpm"] = -50
        assert c.post("/api/components/propulsion-evidence", json=body).status_code == 422
