"""M25 analytic metal stress API is not flightworthiness evidence."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def payload(material="alu_6061_t6"):
    design = json.loads(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )
    design["frame"]["material_id"] = material
    return {
        "design": design,
        "cases": [{
            "name": "synthetic_static",
            "thrusts_n": [5, 5, 5, 5],
            "axial_torques_n_m": [.1, .1, .1, .1],
        }],
        "safety_factor": 1.5,
        "load_case_source": "synthetic math only, not a real flight load",
    }


def test_isotropic_metal_api_never_certifies_structural_strength():
    with TestClient(app) as client:
        res = client.post("/api/components/combined-metal-screen", json=payload())
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["status"] == "ANALYTICAL_ISOTROPIC_STATIC_SCREEN_ONLY"
    assert result["screen_passed"] is True
    assert result["independent_structural_validation_established"] is False
    assert result["flightworthiness_established"] is False
    assert result["cases"][0]["rotors"][0]["von_mises_pa"] > 0


def test_reference_composite_cannot_be_promoted_to_ductile_metal():
    with TestClient(app) as client:
        res = client.post("/api/components/combined-metal-screen",
                          json=payload("cfrp_quasi_iso"))
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "UNSUPPORTED_MATERIAL_FAILURE_MODEL"
    assert res.json()["screen_passed"] is False
    assert res.json()["flightworthiness_established"] is False


def test_unsourced_or_malformed_loads_rejected():
    with TestClient(app) as client:
        data = payload()
        data["cases"][0]["axial_torques_n_m"] = [float("nan")] * 4
        assert client.post("/api/components/combined-metal-screen", json=data).status_code == 422
        data = payload()
        data["cases"][0]["axial_torques_n_m"] = [.1, .1]
        assert client.post("/api/components/combined-metal-screen", json=data).status_code == 422
        data = payload()
        data["load_case_source"] = ""
        assert client.post("/api/components/combined-metal-screen", json=data).status_code == 422
