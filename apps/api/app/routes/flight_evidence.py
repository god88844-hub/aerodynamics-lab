"""M13: read-only comparison of a saved flight trajectory to an external log."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.persistence.database import get_db
from app.persistence.models import SimulationRun
from physics.validation.flight_evidence import (
    FlightEvidenceRequest, evaluate_flight_evidence,
)

router = APIRouter(tags=["flight-evidence"])


@router.post("/simulations/{run_id}/flight-evidence")
def compare_flight_evidence(
    run_id: int, body: FlightEvidenceRequest, db: Session = Depends(get_db),
) -> dict:
    """Score operator-provided telemetry against *stored* predictions only.

    Neither logs nor fitted parameters are persisted. Physical provenance and
    independent calibration status are *declared*, never authenticated.
    """
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="stored simulation not found")
    try:
        return evaluate_flight_evidence(
            json.loads(run.result_json), body,
            simulation_id=run.id,
            design_id=run.design_id,
            scenario=run.scenario,
            saved_result_json=run.result_json,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
