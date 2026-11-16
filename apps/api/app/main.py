"""AeroForge API entrypoint.

Run from ``apps/api``:  uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.persistence.database import init_db
from app.routes import components, designs, flight_evidence, health, propulsion_evidence, simulations


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # dev convenience; Alembic owns schema in production
    yield


app = FastAPI(
    title="AeroForge API",
    version="0.1.0",
    description=(
        "Backend for the AeroForge physics-based drone simulation lab. "
        "Every simulation result is reported with best estimate, uncertainty, "
        "credibility rating, and explicit caveats (NASA-STD-7009 / ASME V&V 10)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(components.router, prefix="/api")
app.include_router(designs.router, prefix="/api")
app.include_router(simulations.router, prefix="/api")
app.include_router(flight_evidence.router, prefix="/api")
app.include_router(propulsion_evidence.router, prefix="/api")
