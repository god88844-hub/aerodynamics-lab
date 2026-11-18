"""Canonical snapshots and serialized history writes for saved designs."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.persistence.models import Design, DesignRevision


def canonical_snapshot(snapshot: dict) -> str:
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False)


def snapshot_digest(snapshot_json: str) -> str:
    return sha256(snapshot_json.encode("utf-8")).hexdigest()


def lock_design(db: Session, design_id: int) -> Design | None:
    # SQLite ignores FOR UPDATE. Take its write lock before reading the saved
    # snapshot so concurrent workers cannot derive the same revision number.
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
    return db.get(Design, design_id, with_for_update=True)


def make_revision(design: Design, number: int, when: datetime) -> DesignRevision:
    snapshot_json = canonical_snapshot(json.loads(design.snapshot_json))
    return DesignRevision(
        design_id=design.id,
        number=number,
        name=design.name,
        snapshot_json=snapshot_json,
        snapshot_sha256=snapshot_digest(snapshot_json),
        created_at=when,
    )


def record_update(db: Session, design: Design, name: str, snapshot_json: str) -> None:
    last_number = db.scalar(
        select(DesignRevision.number)
        .where(DesignRevision.design_id == design.id)
        .order_by(DesignRevision.number.desc())
        .limit(1)
    )
    if last_number is None:
        last_number = 1
        db.add(make_revision(design, last_number, design.updated_at))
    if snapshot_json == canonical_snapshot(json.loads(design.snapshot_json)) and name == design.name:
        return

    design.name = name
    design.snapshot_json = snapshot_json
    db.flush()
    db.add(make_revision(design, last_number + 1, design.updated_at))
