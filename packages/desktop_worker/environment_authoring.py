"""Repeatable engineering test-ground authoring and fail-closed validation (P0A-021)."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator

from aeroforge_schemas.project import EngineeringProject, Environment


class TestGroundObstacle(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=80)
    center_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    size_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat]

    @field_validator("size_m")
    @classmethod
    def _positive_size(cls, value):
        if any(v <= 0.0 for v in value):
            raise ValueError("obstacle size_m components must be > 0")
        return value


class LandingSurface(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=80)
    center_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat] = (0.0, 0.0, 0.0)
    size_m: tuple[FiniteFloat, FiniteFloat] = (2.0, 2.0)
    friction_coeff: FiniteFloat = Field(default=0.8, gt=0.0, le=5.0)
    contact_model: Literal["rigid_plane"] = "rigid_plane"


class TestGroundSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    units: Literal["SI"] = "SI"
    world_frame: Literal["local_right_handed_z_up"] = "local_right_handed_z_up"
    origin_m: tuple[FiniteFloat, FiniteFloat, FiniteFloat] = (0.0, 0.0, 0.0)
    terrain_kind: Literal["flat_plane", "graded_pad"] = "flat_plane"
    wind_world_m_s: tuple[FiniteFloat, FiniteFloat, FiniteFloat] = (0.0, 0.0, 0.0)
    temperature_k: FiniteFloat = Field(default=288.15, gt=150.0, lt=360.0)
    pressure_pa: FiniteFloat = Field(default=101325.0, gt=1000.0, lt=200000.0)
    relative_humidity: FiniteFloat = Field(default=0.0, ge=0.0, le=1.0)
    rain_mm_h: FiniteFloat = Field(default=0.0, ge=0.0)
    snow_water_equivalent_mm_h: FiniteFloat = Field(default=0.0, ge=0.0)
    icing_requested: bool = False
    landing_surfaces: list[LandingSurface] = Field(default_factory=lambda: [LandingSurface(id="primary_pad")])
    obstacles: list[TestGroundObstacle] = Field(default_factory=list)


def validate_supported_environment(env: Environment, ground: TestGroundSpec | None = None) -> None:
    """Refuse unsupported wet/snow/icing/contact mechanisms explicitly (fail closed)."""
    if env.world_frame != "local_right_handed_z_up":
        raise ValueError(f"unsupported world_frame {env.world_frame!r}")
    if env.rain_mm_h > 0.0 or (ground is not None and ground.rain_mm_h > 0.0):
        raise ValueError("unsupported atmospheric mechanism: rain/wet operation requires Slice 0D physical models")
    if env.snow_water_equivalent_mm_h > 0.0 or (ground is not None and ground.snow_water_equivalent_mm_h > 0.0):
        raise ValueError("unsupported atmospheric mechanism: snow accumulation requires Slice 0D physical models")
    if env.icing_requested or (ground is not None and ground.icing_requested):
        raise ValueError("unsupported atmospheric mechanism: rotor/airframe icing requires Slice 0D physical models")
    if any(not math.isfinite(float(v)) for v in env.wind_world_m_s):
        raise ValueError("wind_world_m_s must be finite")


def author_test_ground(project: EngineeringProject, spec: dict[str, Any]) -> EngineeringProject:
    """Validate and serialize an authored engineering test ground into an EngineeringProject."""
    ground = TestGroundSpec.model_validate(spec)
    env = Environment(
        world_frame=ground.world_frame,
        wind_world_m_s=ground.wind_world_m_s,
        temperature_k=ground.temperature_k,
        pressure_pa=ground.pressure_pa,
        relative_humidity=ground.relative_humidity,
        rain_mm_h=ground.rain_mm_h,
        snow_water_equivalent_mm_h=ground.snow_water_equivalent_mm_h,
        icing_requested=ground.icing_requested,
        terrain_asset_id=project.environment.terrain_asset_id,
    )
    validate_supported_environment(env, ground)
    params = dict(project.experiment.parameters)
    params["test_ground"] = ground.model_dump(mode="json")
    updated_exp = project.experiment.model_copy(update={"parameters": params})
    return project.model_copy(update={"environment": env, "experiment": updated_exp})
