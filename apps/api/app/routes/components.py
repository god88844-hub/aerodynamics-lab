"""Component evidence database routes (editor pickers)."""

from fastapi import APIRouter, HTTPException

from app.services import component_service
from physics.propulsion.loader import ComponentLibrary
from physics.validation.public_evidence import (
    audit_quadplane_battery, get_public_source_inventory,
)
from physics.validation.discharge_replay import DischargeReplayRequest, replay_discharge
from physics.validation.battery_evidence import (
    BatteryEvidenceRequest, evaluate_battery_evidence,
)

router = APIRouter(prefix="/components", tags=["components"])


@router.get("")
def components() -> dict:
    return component_service.list_components()


@router.post("/battery-evidence")
def battery_evidence(body: BatteryEvidenceRequest) -> dict:
    """Score independently tagged discharge evidence; no library mutation.

    User reports measured values and run provenance; neither is authenticated.
    """
    library = ComponentLibrary(component_service.REPO_ROOT / "data" / "components")
    try:
        spec = library.battery(body.battery_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="battery component not found") from exc
    try:
        return evaluate_battery_evidence(spec, body)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/discharge-replay")
def discharge_replay(body: DischargeReplayRequest) -> dict:
    """Read-only comparison conditioned on operator-supplied discharge current.

    Sources, instrumentation and independence are self-declared, not verified.
    """
    library = ComponentLibrary(component_service.REPO_ROOT / "data" / "components")
    try:
        spec = library.battery(body.battery_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="battery component not found") from exc
    try:
        return replay_discharge(spec, body)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/public-evidence")
def public_evidence() -> dict:
    """Read-only physical source registry and audited third-party battery log.

    The observations are not validation of an AeroForge hardware model.
    """
    try:
        return {
            "registry": get_public_source_inventory(),
            "quadplane_battery_audit": audit_quadplane_battery(),
            "model_physically_validated_by_these_public_sources": False,
        }
    except (ValueError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail=f"public evidence audit unavailable or source integrity failed: {exc}",
        ) from exc
