"""ORM models: designs (immutable snapshots) and simulation runs.

Traceability rule: a stored design's ``snapshot_json`` is the EXACT input the
simulator executed; a stored run's ``result_json`` is the exact report the
simulator produced.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Design(Base):
    __tablename__ = "designs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow,
                                                 onupdate=_utcnow)

    simulations: Mapped[list["SimulationRun"]] = relationship(
        back_populates="design", cascade="all, delete-orphan"
    )


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    design_id: Mapped[int] = mapped_column(ForeignKey("designs.id"), index=True)
    scenario: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    design: Mapped[Design] = relationship(back_populates="simulations")
