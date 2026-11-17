"""Editable designs, saved simulation results, and their frozen inputs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DDL, DateTime, ForeignKey, Integer, String, Text, event
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
    frozen_input: Mapped[SimulationRunInput | None] = relationship(
        cascade="all, delete-orphan",
    )


class SimulationRunInput(Base):
    __tablename__ = "simulation_run_inputs"

    run_id: Mapped[int] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), primary_key=True,
    )
    input_json: Mapped[str] = mapped_column(Text)
    input_sha256: Mapped[str] = mapped_column(String(64))


# Older SQLite app versions can delete a run with foreign keys disabled.
# Remove its inputs before SQLite can reuse the integer run ID.
event.listen(
    SimulationRunInput.__table__,
    "after_create",
    DDL("""
        CREATE TRIGGER IF NOT EXISTS delete_simulation_run_inputs
        AFTER DELETE ON simulation_runs
        BEGIN
            DELETE FROM simulation_run_inputs WHERE run_id = OLD.id;
        END
    """).execute_if(dialect="sqlite"),
)
