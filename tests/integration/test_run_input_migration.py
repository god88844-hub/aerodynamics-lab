"""Exercise the additive revision on existing SQLite databases."""

import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.persistence import database

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("already_created_at_startup", [False, True])
def test_upgrade_preserves_legacy_run_without_inventing_inputs(tmp_path, monkeypatch, already_created_at_startup):
    url = f"sqlite:///{(tmp_path / 'previous.db').as_posix()}"
    monkeypatch.setenv("AEROFORGE_DB_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    config = Config(str(ROOT / "apps/api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
    command.upgrade(config, "0001")
    assert not inspect(engine).has_table("simulation_run_inputs")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO designs (id, name, snapshot_json, created_at, updated_at) "
            "VALUES (1, 'legacy', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        connection.execute(text(
            "INSERT INTO simulation_runs (id, design_id, scenario, status, result_json, created_at) "
            "VALUES (1, 1, 'hover-ideal', 'completed', :report, CURRENT_TIMESTAMP)"
        ), {"report": json.dumps({"legacy": "original result"})})
    if already_created_at_startup:
        database.init_db()
    command.upgrade(config, "head")
    assert inspect(engine).has_table("simulation_run_inputs")

    with TestClient(app) as client:
        report = client.get("/api/simulations/1")
        assert report.status_code == 200, report.text
        assert report.json()["legacy"] == "original result"
        assert report.json()["input_sha256"] is None
        unavailable = client.get("/api/simulations/1/inputs")
        assert unavailable.status_code == 404
        assert unavailable.json()["detail"] == "inputs were not recorded for this simulation"

        snapshot = json.loads((ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8"))
        saved_design = client.post("/api/designs", json={"snapshot": snapshot})
        assert saved_design.status_code == 200, saved_design.text
        run = client.post(f"/api/designs/{saved_design.json()['id']}/simulate", json={
            "scenario": "hover-ideal", "params": {"dt_s": "bad"},
        })
        assert run.status_code == 200, run.text
        assert run.json()["status"] == "failed"
        run_id = run.json()["simulation_id"]
        frozen = client.get(f"/api/simulations/{run_id}/inputs")
        assert frozen.status_code == 200, frozen.text
        assert frozen.json()["effective_parameters"] is None
        assert frozen.json()["requested_parameters"] == {"dt_s": "bad"}

        with engine.begin() as connection:
            connection.execute(text(
                "UPDATE simulation_run_inputs SET input_json = '{}' WHERE run_id = :id"
            ), {"id": run_id})
        assert client.get(f"/api/simulations/{run_id}/inputs").status_code == 409
        assert client.get(f"/api/simulations/{run_id}").json()["status"] == "failed"
    engine.dispose()
