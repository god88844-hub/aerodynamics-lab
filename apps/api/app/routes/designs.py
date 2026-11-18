"""Design CRUD routes. Snapshots are validated against the shared schema on
every write — a design that doesn't validate cannot be saved or simulated."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, defer

from aeroforge_schemas.design import DroneDesign
from app.persistence.database import get_db
from app.persistence.design_history import canonical_snapshot, lock_design, make_revision, record_update, snapshot_digest
from app.persistence.models import Design, DesignRevision, SimulationRun
from app.services.cad_layout import MAX_DRAWING_BYTES, export_layout, import_layout

router = APIRouter(prefix="/designs", tags=["designs"])


class DesignCreate(BaseModel):
    snapshot: dict


class DesignUpdate(BaseModel):
    snapshot: dict


class StructuralLoadCase(BaseModel):
    name: str
    thrusts_n: list[float]
    # Explicit torque ABOUT THE ARM AXIS, not rotor reaction torque about body Z.
    axial_torques_n_m: list[float] | None = None


class JointAllowables(BaseModel):
    bending_moment_n_m: float
    axial_torque_n_m: float
    evidence_source: str


class StructuralEnvelopeRequest(BaseModel):
    snapshot: dict
    cases: list[StructuralLoadCase]
    shear_allowable_pa: float | None = None
    shear_allowable_source: str | None = None
    joint_allowables: JointAllowables | None = None


def _design_summary(design: Design) -> dict:
    return {"id": design.id, "name": design.name,
            "created_at": design.created_at.isoformat(),
            "updated_at": design.updated_at.isoformat()}


def _validated_snapshot(snapshot: dict) -> DroneDesign:
    try:
        return DroneDesign.model_validate(snapshot)
    except ValidationError as exc:
        raise HTTPException(422, f"invalid design snapshot: {exc}")


def _design_record(row: Design) -> dict:
    return {"id": row.id, "name": row.name, "snapshot": json.loads(row.snapshot_json)}


def _snapshot_json(design: DroneDesign) -> str:
    try:
        return canonical_snapshot(design.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(422, "design snapshot contains a non-finite value") from exc


def _revision_summary(revision: DesignRevision) -> dict:
    return {"number": revision.number, "name": revision.name,
            "created_at": revision.created_at.isoformat(), "snapshot_sha256": revision.snapshot_sha256}


def _revision(db: Session, row: Design, number: int) -> DesignRevision:
    revision = db.get(DesignRevision, (row.id, number))
    if revision is None and number == 1:
        # Designs created before this feature have no saved history. Their
        # current snapshot is the initial revision until the first edit.
        revision = make_revision(row, 1, row.updated_at)
    if revision is None:
        raise HTTPException(404, f"revision {number} not found for design {row.id}")
    if snapshot_digest(revision.snapshot_json) != revision.snapshot_sha256:
        raise HTTPException(409, "stored revision failed snapshot integrity check")
    return revision


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
    row = Design(name=design.name, snapshot_json=_snapshot_json(design))
    db.add(row)
    db.flush()
    db.add(make_revision(row, 1, row.created_at))
    db.commit()
    return _design_record(row)


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
    from physics.structures.advanced import evaluate_advanced_envelope
    from physics.structures.materials import load_materials

    design = _validated_snapshot(body.snapshot)
    material_file = REPO_ROOT / "data" / "components" / "materials.json"
    materials = load_materials(material_file)
    try:
        return evaluate_advanced_envelope(
            design,
            [(case.name, case.thrusts_n, case.axial_torques_n_m)
             for case in body.cases],
            materials,
            shear_allowable_pa=body.shear_allowable_pa,
            shear_allowable_source=body.shear_allowable_source,
            joint_allowables=body.joint_allowables.model_dump()
            if body.joint_allowables else None,
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
    row = lock_design(db, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    design = _validated_snapshot(body.snapshot)
    record_update(db, row, design.name, _snapshot_json(design))
    db.commit()
    return _design_record(row)


@router.get("/{design_id}/revisions")
def list_design_revisions(design_id: int, db: Session = Depends(get_db)) -> list[dict]:
    statement = (
        select(Design, DesignRevision)
        .outerjoin(DesignRevision, DesignRevision.design_id == Design.id)
        .where(Design.id == design_id)
        .options(defer(DesignRevision.snapshot_json))
        .order_by(DesignRevision.number.desc())
    )
    # Read the current design and history together so a concurrent update
    # cannot turn an initial snapshot into a different revision in this read.
    rows = db.execute(statement).all()
    if not rows:
        raise HTTPException(404, f"design {design_id} not found")
    design, latest = rows[0]
    if latest is None:
        return [_revision_summary(make_revision(design, 1, design.updated_at))]
    return [_revision_summary(revision) for _, revision in rows]


@router.get("/{design_id}/revisions/{number}")
def get_design_revision(design_id: int, number: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(Design, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    revision = _revision(db, row, number)
    return {**_revision_summary(revision), "snapshot": json.loads(revision.snapshot_json)}


@router.post("/{design_id}/revisions/{number}/restore")
def restore_design_revision(design_id: int, number: int, db: Session = Depends(get_db)) -> dict:
    row = lock_design(db, design_id)
    if row is None:
        raise HTTPException(404, f"design {design_id} not found")
    revision = _revision(db, row, number)
    design = _validated_snapshot(json.loads(revision.snapshot_json))
    record_update(db, row, design.name, revision.snapshot_json)
    db.commit()
    return _design_record(row)


@router.get("/{design_id}/revisions/{number}/layout.dxf")
def download_layout(design_id: int, number: int, db: Session = Depends(get_db)) -> Response:
    revision = get_design_revision(design_id, number, db)
    try:
        data = export_layout(_validated_snapshot(revision["snapshot"]), revision["snapshot_sha256"])
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    filename = f"aeroforge-{design_id}-r{number}-{revision['snapshot_sha256'][:12]}.dxf"
    return Response(content=data, media_type="application/dxf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/{design_id}/revisions/{number}/layout-preview")
async def preview_layout(design_id: int, number: int, request: Request, db: Session = Depends(get_db)) -> dict:
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_DRAWING_BYTES:
            raise HTTPException(413, "DXF exceeds the 1 MiB exchange limit")
        data.extend(chunk)
    revision = await run_in_threadpool(get_design_revision, design_id, number, db)
    try:
        design, changes = await run_in_threadpool(import_layout, _validated_snapshot(revision["snapshot"]),
                                                  revision["snapshot_sha256"], bytes(data))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"snapshot": design.model_dump(mode="json"), "changes": changes, "source_sha256": revision["snapshot_sha256"]}


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
