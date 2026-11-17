"""M27.3 read-only paired original-byte holdout evidence assessment.

All reported provenance and physics-origin labels remain unauthenticated.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from physics.validation.source_pinned_holdouts import audit_source_pinned_holdouts

router = APIRouter(prefix="/components", tags=["components"])


class OriginalHoldoutRun(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    run_id: str = Field(min_length=1, max_length=80)
    group_id: str = Field(min_length=1, max_length=300)
    dataset_kind: str = Field(min_length=1, max_length=80)
    hardware_match: bool
    unused_for_calibration: bool
    observed_csv: str = Field(min_length=1, max_length=1_000_000)
    observed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    prediction_csv: str = Field(min_length=1, max_length=1_000_000)
    prediction_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourcePinnedAuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    frozen_model_git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    frozen_protocol_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    channel: str = Field(min_length=1, max_length=100)
    maximum_absolute_error: float = Field(gt=0)
    minimum_robust_coverage_fraction: float = Field(gt=0, le=1)
    calibration_group_ids: list[str] = Field(min_length=1, max_length=60)
    runs: list[OriginalHoldoutRun] = Field(min_length=2, max_length=60)


@router.post("/source-pinned-holdout-audit")
def source_pinned_holdout_audit(body: SourcePinnedAuditRequest) -> dict:
    """Integrity and pointwise error screens; no physical-origin authentication."""
    try:
        return audit_source_pinned_holdouts(
            frozen_model_git_sha=body.frozen_model_git_sha,
            frozen_protocol_sha256=body.frozen_protocol_sha256,
            channel=body.channel,
            maximum_absolute_error=body.maximum_absolute_error,
            minimum_robust_coverage_fraction=body.minimum_robust_coverage_fraction,
            calibration_group_ids=body.calibration_group_ids,
            runs=[x.model_dump() for x in body.runs],
        )
    except (ValueError, TypeError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
