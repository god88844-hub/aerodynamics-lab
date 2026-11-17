"""Simulation routes: run a stored design snapshot and fetch stored results."""

from __future__ import annotations

import json
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.persistence.database import get_db
from app.persistence.models import Design, SimulationRun, SimulationRunInput
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
        result, inputs = simulation_service.run_simulation(snapshot, body.scenario, body.params)
        frozen_json = json.dumps(inputs, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    input_sha256 = sha256(frozen_json.encode("utf-8")).hexdigest()
    run = SimulationRun(design_id=design_id, scenario=body.scenario,
                        status=result.get("status", "completed"),
                        result_json=json.dumps(result),
                        frozen_input=SimulationRunInput(
                            input_json=frozen_json,
                            input_sha256=input_sha256,
                        ))
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"simulation_id": run.id, "design_id": design_id, **result,
            "input_sha256": input_sha256}


@router.get("/simulations/{run_id}")
def get_simulation(run_id: int, db: Session = Depends(get_db)) -> dict:
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(404, f"simulation {run_id} not found")
    return {"simulation_id": run.id, "design_id": run.design_id, "scenario": run.scenario,
            "status": run.status, "created_at": run.created_at.isoformat(),
            **json.loads(run.result_json),
            "input_sha256": run.frozen_input.input_sha256 if run.frozen_input else None}


@router.get("/simulations/{run_id}/inputs", response_class=Response)
def download_simulation_inputs(run_id: int, db: Session = Depends(get_db)) -> Response:
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(404, f"simulation {run_id} not found")
    frozen = run.frozen_input
    if frozen is None:
        raise HTTPException(404, "inputs were not recorded for this simulation")
    payload = frozen.input_json.encode("utf-8")
    if sha256(payload).hexdigest() != frozen.input_sha256:
        raise HTTPException(409, "stored simulation inputs failed their SHA-256 check")
    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="aeroforge-run-{run_id}-inputs.json"',
            "X-AeroForge-Input-SHA256": frozen.input_sha256,
        },
    )
