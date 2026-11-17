"""Read-only controller/HIL trajectory evidence, never hardware control."""
from fastapi import APIRouter, HTTPException
from physics.validation.hil_evidence import HILCampaignRequest, audit_hil_campaign

router = APIRouter(prefix="/components", tags=["components"])

@router.post("/hil-evidence")
def hil_evidence(body: HILCampaignRequest) -> dict:
    """Check immutable reported comparison files; no hardware command path."""
    try:
        return audit_hil_campaign(body)
    except (ValueError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
