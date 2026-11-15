"""API integration tests: designs CRUD, component listing, simulation runs.

Uses the ASGI TestClient with get_db overridden to a temporary SQLite DB."""

import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_MN = REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json"


@pytest.fixture(scope="module")
def client():
    import sys

    sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
    from fastapi.testclient import TestClient

    from app.main import app
    from app.persistence.database import Base, get_db

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    test_engine = create_engine(
        f"sqlite:///{tmp.name}", connect_args={"check_same_thread": False}, future=True
    )
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def design_payload() -> dict:
    import json

    return json.loads(DESIGN_MN.read_text(encoding="utf-8"))


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_components_listed(client):
    r = client.get("/api/components")
    assert r.status_code == 200
    body = r.json()
    assert any(m["id"] == "tmotor_mn3508_kv380" for m in body["motors"])
    assert any(p["id"] == "tmotor_p15x5_cf" for p in body["propellers"])
    assert any(m["id"] == "cfrp_quasi_iso" for m in body["materials"])
    motor = next(m for m in body["motors"] if m["id"] == "tmotor_mn3508_kv380")
    assert motor["estimated"] is False and motor["source"]


def test_design_crud_cycle(client, design_payload):
    r = client.post("/api/designs", json={"snapshot": design_payload})
    assert r.status_code == 200
    design_id = r.json()["id"]

    r = client.get(f"/api/designs/{design_id}")
    assert r.status_code == 200
    assert r.json()["snapshot"]["name"] == "quad_mn3508_6s_15x5"

    modified = {**design_payload, "name": "quad_mn3508_6s_15x5_v2"}
    r = client.put(f"/api/designs/{design_id}", json={"snapshot": modified})
    assert r.status_code == 200
    assert r.json()["snapshot"]["name"].endswith("_v2")

    r = client.get("/api/designs")
    assert any(d["id"] == design_id for d in r.json())

    r = client.delete(f"/api/designs/{design_id}")
    assert r.status_code == 200
    assert client.get(f"/api/designs/{design_id}").status_code == 404


def test_invalid_snapshot_rejected(client):
    r = client.post("/api/designs", json={"snapshot": {"name": "broken", "parts": []}})
    assert r.status_code == 422
    assert "invalid design snapshot" in r.json()["detail"]


def test_preview_returns_mass_properties(client, design_payload):
    r = client.post("/api/designs/preview", json={"snapshot": design_payload})
    assert r.status_code == 200
    body = r.json()
    assert body["mass_kg"] == pytest.approx(3.708, abs=1e-6)
    assert len(body["principal_axes"]) == 3
    assert body["hover_trim_error"] is None


def test_flight_simulation_end_to_end(client, design_payload):
    r = client.post("/api/designs", json={"snapshot": design_payload})
    design_id = r.json()["id"]

    r = client.post(f"/api/designs/{design_id}/simulate",
                    json={"scenario": "flight", "params": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["mission"]["aborted"] is False
    assert body["results"]["time_to_5m_s"] is not None
    assert body["results"]["energy_used_wh"] > 0
    assert body["success"]["reached_5m"] is True
    # Telemetry decimated but present.
    assert len(body["telemetry"]["t"]) > 10
    assert len(body["telemetry"]["motor_current_a"]) == len(body["telemetry"]["t"])

    # Stored and retrievable.
    r = client.get(f"/api/simulations/{body['simulation_id']}")
    assert r.status_code == 200
    assert "flight" in r.json()["scenario"]

    r = client.get(f"/api/designs/{design_id}/simulations")
    assert len(r.json()) == 1


def test_hover_static_end_to_end(client, design_payload):
    r = client.post("/api/designs", json={"snapshot": design_payload})
    design_id = r.json()["id"]
    r = client.post(f"/api/designs/{design_id}/simulate",
                    json={"scenario": "hover-static", "params": {"max_duration_s": 7200}})
    body = r.json()
    assert body["status"] == "completed"
    assert body["endurance"]["to_warning_s"] > 1200
    benchmarks = {b["name"]: b["status"] for b in body["benchmarks"]}
    assert "pass" in benchmarks.values()


def test_simulation_failure_is_reported_not_crashing(client):
    """A design that physics refuses (no powertrain + flight) returns a
    failed-status result with the error message — an engineering outcome."""
    r = client.post("/api/designs", json={"snapshot": {
        "schema_version": "0.1", "name": "no_powertrain",
        "parts": [{"name": "frame", "mass_kg": 1.0, "position_m": [0, 0, 0]}],
        "rotors": [{"position_m": [0.25, 0, 0]}],
    }})
    design_id = r.json()["id"]
    r = client.post(f"/api/designs/{design_id}/simulate",
                    json={"scenario": "flight", "params": {}})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert "powertrain" in body["error"]
