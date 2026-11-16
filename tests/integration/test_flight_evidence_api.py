"""M13 HTTP/DB acceptance; synthetic telemetry only, not flight evidence."""
import json
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="module")
def evidence_client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.persistence.database import Base, get_db
    from app.persistence.models import Design, SimulationRun

    with tempfile.TemporaryDirectory() as directory:
        engine = create_engine(
            f"sqlite:///{Path(directory) / 'm13.db'}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, autoflush=False)

        def override_db():
            with Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        try:
            with Session() as db:
                design = Design(name="synthetic_m13", snapshot_json='{"fixture":true}')
                db.add(design)
                db.flush()
                data = {
                    "status": "completed",
                    "telemetry": {
                        "t": [i / 2 for i in range(21)],
                        "z": [-i for i in range(21)],
                        "vz": [-2] * 21,
                        "v_bus_v": [24 - .05*i for i in range(21)],
                        "motor_current_a": [[2, 3]] * 21,
                    },
                }
                run = SimulationRun(design_id=design.id, scenario="flight",
                                    status="completed", result_json=json.dumps(data))
                db.add(run)
                db.commit()
                run_id = run.id
                original = run.result_json
            with TestClient(app) as client:
                yield client, run_id, Session, original
        finally:
            app.dependency_overrides.pop(get_db, None)
            engine.dispose()


def request_payload():
    return {
        "dataset_kind": "synthetic_fixture",
        "vehicle_id": "fixture_multirotor", "flight_log_id": "synthetic_run_B",
        "log_source": "calculated mathematical verification fixture",
        "hardware_matches_simulated_design": False,
        "unused_for_model_calibration": True,
        "measurement_to_sim_time_offset_s": 0,
        "tolerances": {"altitude_m": .1, "bus_voltage_v": .01},
        "observations": [
            {"t_s": t, "altitude_m": 2*t, "bus_voltage_v": 24-.1*t}
            for t in (0, 2, 4, 6, 8, 10)
        ],
    }


def test_api_predicts_against_stored_run_no_mutation(evidence_client):
    from app.persistence.models import SimulationRun

    client, run_id, session_factory, original = evidence_client
    r = client.post(f"/api/simulations/{run_id}/flight-evidence", json=request_payload())
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["simulation_id"] == run_id
    assert report["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
    assert report["channels"]["altitude_m"]["metrics"]["rmse"] == pytest.approx(0)
    assert report["channels"]["bus_voltage_v"]["metrics"]["mae"] == pytest.approx(0, abs=1e-12)
    assert report["simulation_modified"] is False
    with session_factory() as db:
        assert db.get(SimulationRun, run_id).result_json == original


def test_api_missing_run_bad_time_and_unknown_channel_fail_closed(evidence_client):
    client, run_id, _, _ = evidence_client
    assert client.post("/api/simulations/999999/flight-evidence", json=request_payload()).status_code == 404
    payload = request_payload()
    payload["observations"][-1]["t_s"] = 99
    assert client.post(f"/api/simulations/{run_id}/flight-evidence", json=payload).status_code == 422
    payload = request_payload()
    payload["tolerances"] = {"unknown_metric": 1}
    assert client.post(f"/api/simulations/{run_id}/flight-evidence", json=payload).status_code == 422


def test_api_reported_physical_data_not_treated_as_authenticated(evidence_client):
    client, run_id, _, _ = evidence_client
    payload = request_payload()
    payload.update({"dataset_kind": "physical_measurements", "hardware_matches_simulated_design": True})
    r = client.post(f"/api/simulations/{run_id}/flight-evidence", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] == "REPORTED_FLIGHT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"
    assert r.json()["provenance"]["independence_and_instrumentation_not_authenticated"]
