"""Verify previous database state and durable revision transactions."""

import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.persistence import database

ROOT = Path(__file__).resolve().parents[2]


def test_legacy_design_history_and_failed_write(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    monkeypatch.setenv("AEROFORGE_DB_URL", url)
    engine = create_engine(url)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    config = Config(str(ROOT / "apps/api/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "apps/api/alembic"))
    command.upgrade(config, "0002")
    snapshot = json.loads((ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8"))
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO designs (id, name, snapshot_json, created_at, updated_at) "
            "VALUES (1, :name, :snapshot, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"name": snapshot["name"], "snapshot": json.dumps(snapshot)})
    command.upgrade(config, "head")
    path = "/api/designs/1"
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            initial = client.get(f"{path}/revisions/1").json()
            assert initial["snapshot"] == snapshot
            with engine.begin() as connection:
                connection.execute(text("""
                    CREATE TRIGGER fail_revision_write BEFORE INSERT ON design_revisions
                    WHEN NEW.number = 2 BEGIN SELECT RAISE(ABORT, 'test rollback'); END
                """))
            updated = {**snapshot, "name": "First edit to legacy design"}
            assert client.put(path, json={"snapshot": updated}).status_code == 500
            assert client.get(path).json()["snapshot"] == snapshot
            assert len(client.get(f"{path}/revisions").json()) == 1
            with engine.begin() as connection:
                assert connection.execute(text("SELECT COUNT(*) FROM design_revisions")).scalar_one() == 0
                connection.execute(text("DROP TRIGGER fail_revision_write"))

            assert client.put(path, json={"snapshot": updated}).status_code == 200
            assert client.get(f"{path}/revisions/1").json() == initial
            assert client.post(f"{path}/revisions/1/restore").json()["snapshot"] == snapshot
            with engine.begin() as connection:
                assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 0
                connection.execute(text("DELETE FROM designs WHERE id = 1"))
                assert connection.execute(text("SELECT COUNT(*) FROM design_revisions")).scalar_one() == 0
            replacement = client.post("/api/designs", json={"snapshot": updated}).json()
            assert replacement["id"] == 1
            assert client.get(f"{path}/revisions/2").status_code == 404
    finally:
        engine.dispose()
