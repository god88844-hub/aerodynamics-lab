"""Database engine/session (SQLite for development, Postgres-ready via
AEROFORGE_DB_URL)."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[4]  # app/persistence -> aeroforge root
_DEFAULT_URL = f"sqlite:///{(_REPO_ROOT / 'aeroforge.db').as_posix()}"
DB_URL = os.environ.get("AEROFORGE_DB_URL", _DEFAULT_URL)

_connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if missing (dev convenience; Alembic owns migrations)."""
    from app.persistence import models  # noqa: F401 — register mappers

    Base.metadata.create_all(engine)
