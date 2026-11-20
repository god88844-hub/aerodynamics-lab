"""WP1–WP3 boundary contracts. Validation of a document grants no physical claim."""
from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat, StrictInt, field_validator, model_validator

from aeroforge_schemas.project import GeometryAsset, Identifier, ProjectModel, Vector3

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Positive = Annotated[FiniteFloat, Field(gt=0)]


class Frames(ProjectModel):
    units: Literal["SI"] = "SI"
    world: Literal["local_right_handed_z_up"] = "local_right_handed_z_up"
    body: Literal["right_handed_x_forward_y_left_z_up"] = "right_handed_x_forward_y_left_z_up"
    quaternion: Literal["wxyz_body_to_world"] = "wxyz_body_to_world"
    relative_air_velocity: Literal["vehicle_minus_air"] = "vehicle_minus_air"
    angles: Literal["rad"] = "rad"


class Transform(ProjectModel):
    translation_body_m: Vector3 = (0, 0, 0)
    rotation_surface_to_body_wxyz: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat] = (1, 0, 0, 0)

    @field_validator("rotation_surface_to_body_wxyz")
    @classmethod
    def unit_rotation(cls, value):
        if not math.isclose(sum(x*x for x in value), 1, abs_tol=1e-8):
            raise ValueError("surface rotation must be a unit quaternion")
        return value


class ModelIdentity(ProjectModel):
    model_id: Identifier
    version: str = Field(min_length=1, max_length=100)
    source_sha256: Digest
    environment_sha256: Digest
    parameter_sha256: Digest


class Solver(ProjectModel):
    contract_version: Literal["solver_1"] = "solver_1"
    backend_id: Literal["legacy_python", "cad_torque_1", "bemt_planned", "vlm_planned", "cfd_planned"]
    algorithm: Literal["rk4_fixed_step", "bemt", "vlm", "cfd"]
    step_s: Positive
    model: ModelIdentity
    frames: Frames = Field(default_factory=Frames)

    @model_validator(mode="after")
    def backend_algorithm(self):
        required = {"legacy_python": "rk4_fixed_step", "cad_torque_1": "rk4_fixed_step",
                    "bemt_planned": "bemt", "vlm_planned": "vlm", "cfd_planned": "cfd"}
        if self.algorithm != required[self.backend_id]:
            raise ValueError("algorithm does not match the declared backend")
        return self


class ResourceLimits(ProjectModel):
    contract_version: Literal["local_cad_resources_1"] = "local_cad_resources_1"
    memory_bytes: StrictInt = Field(default=1024**3, ge=16*1024**2, le=1024**4)
    workspace_bytes: StrictInt = Field(default=256*1024**2, ge=1024**2, le=1024**4)
    wall_time_s: FiniteFloat = Field(default=60, ge=0.01, le=900)

    @field_validator("wall_time_s", mode="before")
    @classmethod
    def real_seconds(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("wall time must be a finite number")
        return value


class PolarEnvelope(ProjectModel):
    reynolds_min: Positive
    reynolds_max: Positive
    mach_min: FiniteFloat = Field(ge=0)
    mach_max: FiniteFloat = Field(ge=0)
    alpha_min_rad: FiniteFloat
    alpha_max_rad: FiniteFloat

    @model_validator(mode="after")
    def ordered(self):
        for name in ("reynolds", "mach", "alpha"):
            suffix = "_rad" if name == "alpha" else ""
            if getattr(self, name+"_max"+suffix) < getattr(self, name+"_min"+suffix):
                raise ValueError("polar envelope bounds must be ordered")
        return self


class PolarReference(ProjectModel):
    asset: GeometryAsset
    source_class: Literal["independent_measurement", "manufacturer", "cfd", "synthetic"]
    envelope: PolarEnvelope
    coefficients: Literal["cl_cd_cm_dimensionless"] = "cl_cd_cm_dimensionless"
    moment_reference: Literal["quarter_chord"] = "quarter_chord"
    evidence_sha256: Digest | None = None

    @model_validator(mode="after")
    def data_not_lod(self):
        if self.asset.role != "parametric_source":
            raise ValueError("polar data must be a source asset, never a display mesh")
        return self


class AeroStation(ProjectModel):
    span_or_radius_m: FiniteFloat = Field(ge=0)
    chord_m: Positive
    twist_rad: FiniteFloat
    leading_edge_surface_m: Vector3
    polar_asset_id: Identifier


class AeroSurface(ProjectModel):
    contract_version: Literal["geometry_aero_1"] = "geometry_aero_1"
    id: Identifier
    kind: Literal["lifting_surface", "rotating_blade", "body_surface"]
    geometry: GeometryAsset
    frames: Frames = Field(default_factory=Frames)
    placement: Transform = Field(default_factory=Transform)
    surface_axes: Literal["x_chord_forward_y_span_z_up"] = "x_chord_forward_y_span_z_up"
    reference_area_m2: Positive
    reference_span_m: Positive
    reference_chord_m: Positive
    moment_datum_body_m: Vector3
    stations: list[AeroStation] = Field(default_factory=list, max_length=4096)
    polars: list[PolarReference] = Field(default_factory=list, max_length=4096)
    execution_backend: Literal["bemt_planned", "vlm_planned", "cfd_planned"]
    physical_validation_status: Literal["unvalidated"] = "unvalidated"

    @model_validator(mode="after")
    def source_and_stations(self):
        if self.geometry.role != "exact_geometry":
            raise ValueError("aerodynamics requires exact geometry; display LOD is not an input")
        ids = {polar.asset.id for polar in self.polars}
        if len(ids) != len(self.polars) or self.geometry.id in ids:
            raise ValueError("source asset IDs must be unique")
        if any(s.polar_asset_id not in ids for s in self.stations):
            raise ValueError("station references a missing polar asset")
        if self.kind != "body_surface" and len(self.stations) < 2:
            raise ValueError("lifting surfaces and blades need at least two stations")
        if any(b.span_or_radius_m <= a.span_or_radius_m for a,b in zip(self.stations, self.stations[1:])):
            raise ValueError("span/radius stations must increase strictly")
        if self.kind == "body_surface" and self.execution_backend != "cfd_planned":
            raise ValueError("body surfaces have no BEMT/VLM adapter")
        return self


class AeroLoads(ProjectModel):
    contract_version: Literal["aero_loads_1"] = "aero_loads_1"
    surface_sha256: Digest
    solver: Solver
    time_s: FiniteFloat = Field(ge=0)
    relative_air_velocity_body_m_s: Vector3
    density_kg_m3: Positive
    force_body_n: Vector3
    moment_body_nm: Vector3
    moment_datum_body_m: Vector3
    axes_rule: Literal["force_and_moment_in_body_axes_about_declared_datum"] = "force_and_moment_in_body_axes_about_declared_datum"
    physical_validation_status: Literal["unvalidated"] = "unvalidated"


class JobRecord(ProjectModel):
    contract_version: Literal["job_1"] = "job_1"
    job_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    state: Literal["created", "admitted", "running", "prepared", "succeeded", "failed", "cancelled"]
    request_sha256: Digest
    solver: Solver
    resources: ResourceLimits
    output_sha256: Digest | None = None
    resource_approval_sha256: Digest | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=4096)

    @model_validator(mode="after")
    def terminal_binding(self):
        if self.state == "succeeded" and (self.output_sha256 is None or self.resource_approval_sha256 is None):
            raise ValueError("success requires output and supervisor resource approval hashes")
        if self.state in ("failed", "cancelled") and self.reason is None:
            raise ValueError("failure/cancellation requires a reason")
        return self


class EvidenceRecord(ProjectModel):
    contract_version: Literal["evidence_1"] = "evidence_1"
    dataset_sha256: Digest
    source_url: str = Field(min_length=1, max_length=2000)
    license: str = Field(min_length=1, max_length=1000)
    source_class: Literal["independent_measurement", "manufacturer", "cfd", "synthetic"]
    role: Literal["development", "calibration", "confirmatory"]
    experiment_ids: list[Identifier] = Field(min_length=1, max_length=10000)
    hardware_configuration_sha256: Digest | None = None
    calibration_record_sha256: Digest | None = None
    uncertainty_budget_sha256: Digest | None = None
    protocol_sha256: Digest | None = None
    model_sha256: Digest | None = None
    partition_registration_sha256: Digest | None = None
    preregistration_attestation_sha256: Digest | None = None
    reviewed_by: str | None = Field(default=None, min_length=1, max_length=300)
    previously_revealed: bool
    physical_validation_status: Literal["unvalidated"] = "unvalidated"

    @model_validator(mode="after")
    def confirmatory_prerequisites(self):
        if len(set(self.experiment_ids)) != len(self.experiment_ids):
            raise ValueError("partition whole independent experiments with unique IDs")
        if self.role == "confirmatory":
            if self.previously_revealed or self.source_class != "independent_measurement":
                raise ValueError("revealed or non-independent physical data cannot be confirmatory")
            required = (self.hardware_configuration_sha256, self.calibration_record_sha256,
                        self.uncertainty_budget_sha256, self.protocol_sha256, self.model_sha256,
                        self.partition_registration_sha256, self.preregistration_attestation_sha256, self.reviewed_by)
            if not all(required):
                raise ValueError("confirmatory data require hardware, instruments, uncertainty, prior protocol/partition and review")
        return self


CAPABILITIES = {
    "legacy_python": {"implemented": True, "scope": "legacy multirotor; fixed default atmosphere/seed"},
    "cad_torque_1": {"implemented": True, "scope": "single exact solid; isolated torque; no flight/aero forces"},
    "bemt_planned": {"implemented": False, "scope": "surface contract only"},
    "vlm_planned": {"implemented": False, "scope": "surface contract only"},
    "cfd_planned": {"implemented": False, "scope": "surface contract only"},
}


def require_backend(backend_id: str) -> None:
    if not CAPABILITIES.get(backend_id, {}).get("implemented"):
        raise ValueError("UNSUPPORTED execution backend: " + backend_id)
