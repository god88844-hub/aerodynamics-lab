"""Design CRUD routes. Snapshots are validated against the shared schema on
every write — a design that doesn't validate cannot be saved or simulated."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from aeroforge_schemas.design import DroneDesign
from app.persistence.database import get_db
from app.persistence.models import Design, SimulationRun

router = APIRouter(prefix="/designs", tags=["designs"])


class DesignCreate(BaseModel):
    snapshot: dict


class DesignUpdate(BaseModel):
    snapshot: dict


class StructuralLoadCase(BaseModel):
    name: str
    thrusts_n: list[float]


class StructuralEnvelopeRequest(BaseModel):
    snapshot: dict
    cases: list[StructuralLoadCase]


def _design_summary(design: Design) -> dict:
    return {"id": design.id, "name": design.name,
            "created_at": design.created_at.isoformat(),
            "updated_at": design.updated_at.isoformat()}


def _validated_snapshot(snapshot: dict) -> DroneDesign:
    try:
        return DroneDesign.model_validate(snapshot)
    except ValidationError as exc:
        raise HTTPException(422, f"invalid design snapshot: {exc}")


@router.get("")
def list_designs(db: Session = Depends(get_db)) -> list[dict]:
    return [_design_summary(d) for d in db.query(Design).order_by(Design.updated_at.desc()).all()]


@router.get("/reference")
def reference_design() -> dict:
    """The reference design snapshot (data/designs/quad_mn3508_6s.json) —
    seeds the editor on first load."""
    import json

    from app.services.component_service import REPO_ROOT

    path = REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json"
    if not path.is_file():
        raise HTTPException(404, "reference design not found")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    return {"name": snapshot.get("name", "reference"), "snapshot": snapshot}


@router.post("")
def create_design(body: DesignCreate, db: Session = Depends(get_db)) -> dict:
    design = _validated_snapshot(body.snapshot)
    row = Design(name=design.name, snapshot_json=design.model_dump_json())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "snapshot": json.loads(row.snapshot_json)}


@router.post("/preview")
def preview_design(body: DesignCreate) -> dict:
    """Mass properties / principal axes / trim feasibility for the editor
    (no persistence, no run). Registered before the /{design_id} routes."""
    from physics.scenarios import service

    design = _validated_snapshot(body.snapshot)
    return service.design_preview(design)


@router.post("/structural-envelope")
def structural_envelope(body: StructuralEnvelopeRequest) -> dict:
    """Analyze caller-supplied static rotor loads against declared arm geometry.

    This is analytical verification, not a statement of flight safety.
    """
    from app.services.component_service import REPO_ROOT
    from physics.structures.envelope import evaluate_load_envelope
    from physics.structures.materials import load_materials

    design = _validated_snapshot(body.snapshot)
    material_file = REPO_ROOT / "data" / "components" / "materials.json"
    materials = load_materials(material_file)
    try:
        return evaluate_load_envelope(
            design,
            [(case.name, case.thrusts_n) for case in body.cases],
            materials,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{design_id}")
def get_design(design_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(Design, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    return {"id": row.id, "name": row.name, "snapshot": json.loads(row.snapshot_json),
            "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat()}


@router.put("/{design_id}")
def update_design(design_id: int, body: DesignUpdate, db: Session = Depends(get_db)) -> dict:
    row = db.get(Design, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    design = _validated_snapshot(body.snapshot)
    row.name = design.name
    row.snapshot_json = design.model_dump_json()
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "snapshot": json.loads(row.snapshot_json)}


@router.delete("/{design_id}")
def delete_design(design_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(Design, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    db.delete(row)
    db.commit()
    return {"deleted": design_id}


@router.get("/{design_id}/simulations")
def list_simulations(design_id: int, db: Session = Depends(get_db)) -> list[dict]:
    row = db.get(Design, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    runs = db.query(SimulationRun).filter_by(design_id=design_id).order_by(
        SimulationRun.created_at.desc()).all()
    return [{"id": r.id, "design_id": r.design_id, "scenario": r.scenario,
             "status": r.status, "created_at": r.created_at.isoformat()} for r in runs]
