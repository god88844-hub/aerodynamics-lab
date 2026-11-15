"""Alembic environment (apps/api/alembic). The DB URL comes from
AEROFORGE_DB_URL or the development SQLite default."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # apps/api on path

from alembic import context  # noqa: E402
from sqlalchemy import create_engine, pool  # noqa: E402

from app.persistence.database import Base, DB_URL  # noqa: E402
from app.persistence import models  # noqa: E402, F401 — register mappers

target_metadata = Base.metadata


def _db_url() -> str:
    return os.environ.get("AEROFORGE_DB_URL", DB_URL)


def run_migrations_offline() -> None:
    context.configure(
        url=_db_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_db_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite-friendly ALTERs
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
