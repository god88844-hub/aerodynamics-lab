"""Simulation routes: run a stored design snapshot and fetch stored results."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.persistence.database import get_db
from app.persistence.models import Design, SimulationRun
from app.services import simulation_service

router = APIRouter(tags=["simulations"])


class SimulateRequest(BaseModel):
    scenario: str
    params: dict | None = None


@router.post("/designs/{design_id}/simulate")
def simulate(design_id: int, body: SimulateRequest, db: Session = Depends(get_db)) -> dict:
    row = db.get(Design, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    snapshot = json.loads(row.snapshot_json)
    try:
        result = simulation_service.run_simulation(snapshot, body.scenario, body.params)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    run = SimulationRun(design_id=design_id, scenario=body.scenario,
                        status=result.get("status", "completed"),
                        result_json=json.dumps(result))
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"simulation_id": run.id, "design_id": design_id, **result}


@router.get("/simulations/{run_id}")
def get_simulation(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(404, f"simulation {run_id} not found")
    return {"simulation_id": run.id, "design_id": run.design_id, "scenario": run.scenario,
            "status": run.status, "created_at": run.created_at.isoformat(),
            **json.loads(run.result_json)}
