"""Read-only isotropic metal tube combined-stress screening; no certification."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from aeroforge_schemas.design import DroneDesign
from app.services import component_service
from physics.structures.combined_metal import evaluate_combined_metal_screen
from physics.structures.materials import load_materials

router = APIRouter(prefix="/components", tags=["components"])


class CombinedCase(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=80)
    thrusts_n: list[float] = Field(min_length=1, max_length=32)
    axial_torques_n_m: list[float] = Field(min_length=1, max_length=32)


class CombinedScreenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    design: DroneDesign
    cases: list[CombinedCase] = Field(min_length=1, max_length=32)
    safety_factor: float = Field(ge=1, le=10)
    load_case_source: str = Field(min_length=1, max_length=500)


@router.post("/combined-metal-screen")
def combined_metal_screen(body: CombinedScreenRequest) -> dict:
    """No component mutation, composite strength pass or aircraft approval."""
    materials = load_materials(component_service.REPO_ROOT / "data/components/materials.json")
    try:
        return evaluate_combined_metal_screen(
            body.design,
            [(x.name, x.thrusts_n, x.axial_torques_n_m) for x in body.cases],
            materials,
            safety_factor=body.safety_factor,
            load_case_source=body.load_case_source,
        )
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
