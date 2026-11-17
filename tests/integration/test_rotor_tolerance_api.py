"""API tests are synthetic geometry fixtures, not measured rotor assembly evidence."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def request():
    return {
        "design": json.loads((ROOT / "data/designs/quad_mn3508_6s.json").read_text()),
        "installed_propeller_diameters_m": [0.381] * 4,
        "xy_center_position_hard_bounds_m": [0.01] * 4,
        "diameter_hard_bounds_m": [0.005] * 4,
        "geometry_source": "synthetic CAD dimensions, not independently measured",
        "hard_bound_source": "synthetic assumed hard errors, not qualified tolerance measurements",
        "minimum_declared_tip_clearance_m": 0.02,
    }


def test_bounded_clearance_endpoint_reports_math_without_physical_validation():
    with TestClient(app) as client:
        response = client.post("/api/components/bounded-rotor-clearance", json=request())
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["status"] == "ANALYTICAL_HARD_BOUND_PROJECTED_CLEARANCE_ONLY"
    assert report["minimum_worst_case_projected_tip_clearance_m"] == 0.094 or abs(report["minimum_worst_case_projected_tip_clearance_m"] - 0.094) < 1e-12
    assert report["analytical_screen_passed"]
    assert report["source_hard_bounds_independently_authenticated"] is False
    assert report["actual_3d_interference_validated"] is False
    assert report["flightworthiness_established"] is False


def test_nominally_clear_but_conservatively_bad_is_not_promoted():
    req = request()
    req["xy_center_position_hard_bounds_m"] = [0.06] * 4
    with TestClient(app) as client:
        response = client.post("/api/components/bounded-rotor-clearance", json=req)
    assert response.status_code == 200
    assert response.json()["status"] == "HARD_BOUND_PROJECTED_CLEARANCE_NOT_ESTABLISHED"
    assert not response.json()["analytical_screen_passed"]


def test_invalid_hard_bounds_and_untraceable_source_blocked():
    with TestClient(app) as client:
        for key, value in (
            ("xy_center_position_hard_bounds_m", [-0.1] * 4),
            ("diameter_hard_bounds_m", ["NaN"] * 4),
            ("xy_center_position_hard_bounds_m", [0.01]),
            ("hard_bound_source", ""),
            ("geometry_source", ""),
            ("unknown_physical_proof", True),
        ):
            req = request()
            req[key] = value
            result = client.post("/api/components/bounded-rotor-clearance", json=req)
            assert result.status_code == 422, (key, result.text)
