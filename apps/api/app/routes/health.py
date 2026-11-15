"""Health / liveness endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Service identity for monitoring and the web app's connectivity check."""
    return {"status": "ok", "service": "aeroforge-api", "version": "0.1.0"}
