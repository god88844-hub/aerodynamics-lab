"""Versioned engineering projects shared by desktop and headless callers."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import PurePosixPath
from typing import Annotated, Literal
from uuid import UUID, NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, JsonValue, field_validator, model_validator

from aeroforge_schemas.design import DroneDesign

Family = Literal["multirotor", "fixed_wing", "helicopter", "vtol"]
Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]
Vector3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class ProjectModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class GeometryAsset(ProjectModel):
    id: Identifier
    path: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: Literal["exact_geometry", "display_mesh", "drawing", "parametric_source"]

    @field_validator("path")
    @classmethod
    def relative_asset(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
            raise ValueError("asset paths must be project-relative POSIX paths")
        if value in ("", "."):
            raise ValueError("asset path must identify a file")
        return value


class AssemblyNode(ProjectModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=200)
    parent_id: Identifier | None = None
    geometry_asset_id: Identifier | None = None
    component_reference: str | None = Field(default=None, max_length=300)
    position_m: Vector3 = (0.0, 0.0, 0.0)
    orientation_wxyz: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat] = (1.0, 0.0, 0.0, 0.0)

    @field_validator("orientation_wxyz")
    @classmethod
    def unit_quaternion(cls, value):
        if not math.isclose(sum(x * x for x in value), 1.0, abs_tol=1e-8):
            raise ValueError("orientation must be a unit quaternion")
        return value


class AssemblyVehicle(ProjectModel):
    format: Literal["assembly_1"] = "assembly_1"
    nodes: list[AssemblyNode] = Field(default_factory=list, max_length=4096)

    @model_validator(mode="after")
    def valid_hierarchy(self):
        parents = {node.id: node.parent_id for node in self.nodes}
        if len(parents) != len(self.nodes):
            raise ValueError("assembly node IDs must be unique")
        completed = set()
        for node in self.nodes:
            chain = set()
            current = node.id
            while current is not None and current not in completed:
                if current not in parents:
                    raise ValueError(f"missing parent node {current}")
                if current in chain:
                    raise ValueError("assembly hierarchy contains a cycle")
                chain.add(current)
                current = parents[current]
            completed.update(chain)
        return self


class LegacyMultirotorVehicle(ProjectModel):
    format: Literal["legacy_multirotor_0.1"] = "legacy_multirotor_0.1"
    snapshot: DroneDesign


class Environment(ProjectModel):
    """Stored settings. Backend capability checks govern their physical use."""

    world_frame: Literal["local_right_handed_z_up"] = "local_right_handed_z_up"
    wind_world_m_s: Vector3 = (0.0, 0.0, 0.0)
    temperature_k: FiniteFloat = Field(default=288.15, gt=0)
    pressure_pa: FiniteFloat = Field(default=101325.0, gt=0)
    relative_humidity: FiniteFloat = Field(default=0.0, ge=0, le=1)
    rain_mm_h: FiniteFloat = Field(default=0.0, ge=0)
    snow_water_equivalent_mm_h: FiniteFloat = Field(default=0.0, ge=0)
    icing_requested: bool = False
    terrain_asset_id: Identifier | None = None


class Experiment(ProjectModel):
    backend_id: Literal["unassigned", "legacy_python"] = "unassigned"
    scenario: str = Field(default="hover-ideal", min_length=1, max_length=80)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    seed: int = Field(default=0, ge=0, le=2**32 - 1)

    @field_validator("parameters")
    @classmethod
    def finite_parameters(cls, value):
        json.dumps(value, allow_nan=False)
        return value


class EngineeringProject(ProjectModel):
    document_version: Literal["1.0"] = "1.0"
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    aircraft_family: Family
    units: Literal["SI"] = "SI"
    vehicle: Annotated[LegacyMultirotorVehicle | AssemblyVehicle, Field(discriminator="format")]
    assets: list[GeometryAsset] = Field(default_factory=list, max_length=4096)
    environment: Environment = Field(default_factory=Environment)
    experiment: Experiment = Field(default_factory=Experiment)

    @model_validator(mode="after")
    def consistent_references(self):
        if isinstance(self.vehicle, LegacyMultirotorVehicle) and self.aircraft_family != "multirotor":
            raise ValueError("legacy snapshots describe multirotors")
        assets = {asset.id for asset in self.assets}
        if len(assets) != len(self.assets):
            raise ValueError("geometry asset IDs must be unique")
        required = {self.environment.terrain_asset_id} - {None}
        if isinstance(self.vehicle, AssemblyVehicle):
            required.update(node.geometry_asset_id for node in self.vehicle.nodes if node.geometry_asset_id)
        if not required.issubset(assets):
            raise ValueError("project references a missing geometry asset")
        return self

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")

    def fingerprint(self) -> str:
        return sha256(self.canonical_bytes()).hexdigest()


def import_legacy_project(snapshot: dict) -> EngineeringProject:
    design = DroneDesign.model_validate(snapshot)
    normalized = design.model_dump(mode="json")
    identity = sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return EngineeringProject(
        id=uuid5(NAMESPACE_URL, "aerodynamics-lab:legacy:" + identity),
        name=design.name,
        aircraft_family="multirotor",
        vehicle=LegacyMultirotorVehicle(snapshot=design),
        experiment=Experiment(backend_id="legacy_python"),
    )
