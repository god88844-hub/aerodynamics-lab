"""Read-only independent static propulsion evidence comparison endpoint (M14)."""
from fastapi import APIRouter, HTTPException

from app.services import component_service
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.loader import ComponentLibrary
from physics.validation.propulsion_evidence import (
    PropulsionEvidenceRequest, evaluate_propulsion_evidence,
)

router = APIRouter(prefix="/components", tags=["components"])


@router.post("/propulsion-evidence")
def propulsion_evidence(body: PropulsionEvidenceRequest) -> dict:
    library = ComponentLibrary(component_service.REPO_ROOT / "data" / "components")
    try:
        motor = library.motor(body.motor_id)
        propeller = library.propeller(body.propeller_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="motor or propeller component not found") from exc
    try:
        dataset = PowertrainDataset(motor, propeller.motor_test_data_key or propeller.id)
        return evaluate_propulsion_evidence(dataset, body)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
