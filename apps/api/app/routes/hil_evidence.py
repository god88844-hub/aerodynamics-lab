"""M23 read-only controller-in-the-loop source/quality audit."""
from fastapi import APIRouter, HTTPException

from physics.validation.hil_evidence import HILCampaignRequest, audit_hil_campaign

router = APIRouter(prefix="/components", tags=["components"])


@router.post("/hil-campaign-audit")
def hil_campaign_audit(body: HILCampaignRequest) -> dict:
    """Check held-out operator telemetry without certifying control performance."""
    try:
        return audit_hil_campaign(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
