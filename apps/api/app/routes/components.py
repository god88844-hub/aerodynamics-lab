"""Component evidence database routes (editor pickers)."""

from fastapi import APIRouter, HTTPException

from app.services import component_service
from physics.propulsion.loader import ComponentLibrary
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
