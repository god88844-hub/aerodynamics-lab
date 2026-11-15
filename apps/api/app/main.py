"""AeroForge API entrypoint.

Run from ``apps/api``:  uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI

from app.routes import health

app = FastAPI(
    title="AeroForge API",
    version="0.1.0",
    description=(
        "Backend for the AeroForge physics-based drone simulation lab. "
        "Every simulation result is reported with best estimate, uncertainty, "
        "credibility rating, and explicit caveats (NASA-STD-7009 / ASME V&V 10)."
    ),
)

app.include_router(health.router, prefix="/api")
