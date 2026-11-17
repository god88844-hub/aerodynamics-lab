"""M28.4 read-only bounded rotor tip screening; nominal and hard bounds explicit."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_tolerance import evaluate_bounded_rotor_clearance

router = APIRouter(prefix="/components", tags=["components"])


class BoundedRotorClearanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    design: DroneDesign
    installed_propeller_diameters_m: list[float] = Field(min_length=2, max_length=32)
    xy_center_position_hard_bounds_m: list[float] = Field(min_length=2, max_length=32)
    diameter_hard_bounds_m: list[float] = Field(min_length=2, max_length=32)
    geometry_source: str = Field(min_length=1, max_length=500)
    hard_bound_source: str = Field(min_length=1, max_length=500)
    minimum_declared_tip_clearance_m: float = Field(ge=0)


@router.post("/bounded-rotor-clearance")
def bounded_rotor_clearance(body: BoundedRotorClearanceRequest) -> dict:
    """Never grants physical CAD or flight safety certification."""
    try:
        return evaluate_bounded_rotor_clearance(
            body.design,
            body.installed_propeller_diameters_m,
            body.xy_center_position_hard_bounds_m,
            body.diameter_hard_bounds_m,
            geometry_source=body.geometry_source,
            hard_bound_source=body.hard_bound_source,
            minimum_declared_tip_clearance_m=body.minimum_declared_tip_clearance_m,
        )
    except (ValueError, OverflowError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
