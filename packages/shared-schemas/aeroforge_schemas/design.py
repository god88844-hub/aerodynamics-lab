"""Design snapshot schemas.

A design snapshot is the complete, exact input to a simulation: parts with
masses/inertias, rotor placement, and model settings. Saving a design saves
this snapshot; the simulator executes the snapshot verbatim (traceability —
re-running a snapshot must reproduce the result). Units are SI throughout and
unit-bearing field names make this explicit.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import model_validator

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1"


class PrimitiveGeometry(BaseModel):
    """Optional, *declared* uniform-density primitive geometry.

    dimensions_m = (x, y, z), aligned to the design body frame. For a solid
    cylinder, x == y == diameter and z is height; cylinder axis is body +z.
    Geometry is not a manufacturer's measured mass or inertia.
    """

    shape: Literal["box", "cylinder"]
    dimensions_m: tuple[float, float, float]

    @model_validator(mode="after")
    def physical_dimensions(self) -> "PrimitiveGeometry":
        dims = self.dimensions_m
        if any(not math.isfinite(d) or d <= 0.0 for d in dims):
            raise ValueError("primitive dimensions must be finite and > 0 m")
        if self.shape == "cylinder" and not math.isclose(
            dims[0], dims[1], rel_tol=1e-9, abs_tol=1e-12
        ):
            raise ValueError("cylinder x/y dimensions must be equal diameters")
        return self


class FrameMount(BaseModel):
    """A named frame anchor in body coordinates, not a fastener model."""

    id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    position_m: tuple[float, float, float]

    @model_validator(mode="after")
    def finite_position(self) -> "FrameMount":
        if any(not math.isfinite(v) for v in self.position_m):
            raise ValueError("mount position must be finite")
        return self


class PartInstance(BaseModel):
    """A physical part with mass and (optionally) its own inertia."""

    name: str
    mount_id: str | None = Field(default=None, description="optional frame mount id; "
        "attached part CoG position must match mount coordinates")
    mass_kg: float = Field(gt=0.0, description="part mass [kg]")
    position_m: tuple[float, float, float] = Field(
        description="body-frame position of the part's own CoG [m]"
    )
    geometry: PrimitiveGeometry | None = Field(
        default=None,
        description="optional dimensions for schematic 3D rendering and a "
        "uniform-density own-CoG inertia *estimate* when measured inertia is absent",
    )
    inertia_about_own_cog_kg_m2: list[list[float]] | None = Field(
        default=None,
        description="3x3 symmetric inertia tensor about the part's own CoG [kg·m²]; "
        "point-mass treatment when omitted",
    )


class RotorInstance(BaseModel):
    """A rotor (motor + propeller) placement in the design frame."""

    position_m: tuple[float, float, float] = Field(
        description="body-frame position of the rotor thrust center [m]"
    )
    spin_direction: Literal[1, -1] = Field(
        default=1, description="sign of the prop's angular momentum about body +z"
    )
    motor_id: str | None = Field(default=None, description="motor component id from the evidence DB")
    propeller_id: str | None = Field(
        default=None, description="propeller component id from the evidence DB"
    )


class PowertrainConfig(BaseModel):
    """Uniform powertrain selection for all rotors (v1 multirotor scope).

    Component ids resolve through the component evidence database
    (data/components/**); every component file is schema-validated and
    carries its own provenance and uncertainty.
    """

    motor_id: str
    propeller_id: str
    esc_id: str
    battery_id: str


class FrameSpec(BaseModel):
    """Structural frame description for arm stress checks.

    Arms are modeled as cantilever circular tubes from the CoG to each rotor;
    the material id must exist in data/components/materials.json (fail-closed:
    a frame referencing an unknown material cannot pass structural checks).
    """

    arm_length_m: float = Field(gt=0.0, description="horizontal distance CoG -> rotor axis [m]")
    tube_od_m: float = Field(gt=0.0)
    tube_id_m: float = Field(gt=0.0)
    material_id: str
    plate_dimensions_m: tuple[float, float, float] | None = Field(
        default=None, description="declared visual plate envelope in meters; "
        "does not override measured frame mass/inertia")
    mount_points: list[FrameMount] = Field(default_factory=list)

    @model_validator(mode="after")
    def frame_dimensions(self) -> "FrameSpec":
        if not all(math.isfinite(v) and v > 0 for v in
                   (self.arm_length_m, self.tube_od_m, self.tube_id_m)):
            raise ValueError("frame tube dimensions must be positive and finite")
        if self.tube_id_m >= self.tube_od_m:
            raise ValueError("frame tube ID must be smaller than OD")
        if self.plate_dimensions_m is not None and any(
            not math.isfinite(v) or v <= 0 for v in self.plate_dimensions_m
        ):
            raise ValueError("plate dimensions must be finite positive meters")
        ids = [mount.id for mount in self.mount_points]
        if len(ids) != len(set(ids)):
            raise ValueError("frame mount ids must be unique")
        return self


class DroneDesign(BaseModel):
    """Full design snapshot — the exact input to a simulation run."""

    schema_version: Literal["0.1"] = "0.1"
    name: str
    parts: list[PartInstance] = Field(min_length=1)
    rotors: list[RotorInstance] = Field(min_length=1)
    powertrain: PowertrainConfig | None = Field(
        default=None,
        description="sourced powertrain for static/performance analysis; when "
        "absent, only ideal-actuator dynamics scenarios can run",
    )
    frame: FrameSpec | None = Field(
        default=None,
        description="frame geometry for structural checks; when absent the "
        "structure monitor is skipped and flagged in reports",
    )
    drag_cd_a_m2: float | None = Field(
        default=None,
        gt=0.0,
        description="equivalent airframe drag area [m²]; omit for no drag model",
    )
    rotor_torque_per_thrust_n_m_per_n: float = Field(
        default=0.0,
        ge=0.0,
        description="uniform rotor reaction torque per unit thrust [N·m/N]; M1 "
        "approximation, per-component values arrive with the propulsion DB (M2)",
    )
    notes: str | None = Field(default=None, description="free-form notes; include data provenance")

    @model_validator(mode="after")
    def consistent_attachments(self) -> "DroneDesign":
        positions = {m.id: m.position_m for m in self.frame.mount_points} if self.frame else {}
        occupied: set[str] = set()
        for p in self.parts:
            if p.mount_id is None:
                continue
            if not (p.name.startswith("payload_") or "battery" in p.name.lower()):
                raise ValueError("only batteries and payloads can reference frame mounts")
            if p.mount_id not in positions:
                raise ValueError(f"part {p.name}: unknown frame mount {p.mount_id}")
            if p.mount_id in occupied:
                raise ValueError(f"mount {p.mount_id} assigned to more than one part")
            occupied.add(p.mount_id)
            if any(not math.isclose(x, y, rel_tol=0, abs_tol=1e-8)
                   for x, y in zip(p.position_m, positions[p.mount_id])):
                raise ValueError(f"part {p.name} differs from frame mount position")
        return self
