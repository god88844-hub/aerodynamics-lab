"""AeroForge shared Pydantic schemas.

Used by the FastAPI backend and by the physics packages to guarantee that a
saved design snapshot is exactly what the simulator executes (traceability).
"""

from aeroforge_schemas.component import (
    BatterySpec,
    EscSpec,
    MotorSpec,
    OcvPoint,
    PropellerSpec,
    SourceInfo,
    TestDataPoint,
)
from aeroforge_schemas.design import DroneDesign, PartInstance, RotorInstance

__all__ = [
    "BatterySpec",
    "DroneDesign",
    "EscSpec",
    "MotorSpec",
    "OcvPoint",
    "PartInstance",
    "PropellerSpec",
    "RotorInstance",
    "SourceInfo",
    "TestDataPoint",
]
