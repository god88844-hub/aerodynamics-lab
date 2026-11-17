"""M28.2 API fixtures are synthetic; no physical clearance validation."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def payload():
    design = json.loads(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )
    return {
        "design": design,
        "installed_propeller_diameters_m": [.381] * 4,
        "minimum_declared_tip_clearance_m": .02,
        "geometry_and_diameter_source": "synthetic exercise only, not observed actual installed rotors",
    }


def test_api_reports_projected_clearance_without_certification():
    with TestClient(app) as client:
        res = client.post("/api/components/rotor-clearance-screen", json=payload())
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["screen_passed"] is True
    assert result["status"] == "ANALYTIC_PROJECTED_TIP_CLEARANCE_ONLY"
    assert len(result["pairs"]) == 6
    assert result["independently_measured_geometry_validated"] is False
    assert result["physical_interference_or_flightworthiness_established"] is False


def test_reported_projected_contact_is_blocked():
    data = payload()
    data["installed_propeller_diameters_m"] = [.55] * 4
    with TestClient(app) as client:
        res = client.post("/api/components/rotor-clearance-screen", json=data)
    assert res.status_code == 200, res.text
    assert res.json()["screen_passed"] is False
    assert res.json()["status"] == "PROJECTED_DISK_TOUCH_OR_OVERLAP_POTENTIAL"


def test_missing_unsourced_and_bad_input_rejected():
    with TestClient(app) as client:
        for patch in (
            {"installed_propeller_diameters_m": [.381]},
            {"installed_propeller_diameters_m": ["NaN"] * 4},
            {"installed_propeller_diameters_m": [.0] * 4},
            {"minimum_declared_tip_clearance_m": -1},
            {"geometry_and_diameter_source": ""},
            {"unknown_proof_of_flight": True},
        ):
            data = payload()
            data.update(patch)
            result = client.post("/api/components/rotor-clearance-screen", json=data)
            assert result.status_code == 422, (patch, result.text)
