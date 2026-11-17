"""Read-only projected-rotor clearance screen; no physical CAD certification."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_clearance import evaluate_rotor_sweep_clearance

router = APIRouter(prefix="/components", tags=["components"])


class RotorClearanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    design: DroneDesign
    installed_propeller_diameters_m: list[float] = Field(min_length=2, max_length=32)
    minimum_declared_tip_clearance_m: float = Field(ge=0)
    geometry_and_diameter_source: str = Field(min_length=1, max_length=500)


@router.post("/rotor-clearance-screen")
def rotor_clearance_screen(body: RotorClearanceRequest) -> dict:
    """Screen declared projected disks; does not change designs or models."""
    try:
        return evaluate_rotor_sweep_clearance(
            body.design,
            body.installed_propeller_diameters_m,
            geometry_and_diameter_source=body.geometry_and_diameter_source,
            minimum_declared_tip_clearance_m=body.minimum_declared_tip_clearance_m,
        )
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
