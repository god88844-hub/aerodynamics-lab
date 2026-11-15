"""Design snapshot schemas.

A design snapshot is the complete, exact input to a simulation: parts with
masses/inertias, rotor placement, and model settings. Saving a design saves
this snapshot; the simulator executes the snapshot verbatim (traceability —
re-running a snapshot must reproduce the result). Units are SI throughout and
unit-bearing field names make this explicit.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1"


class PartInstance(BaseModel):
    """A physical part with mass and (optionally) its own inertia."""

    name: str
    mass_kg: float = Field(gt=0.0, description="part mass [kg]")
    position_m: tuple[float, float, float] = Field(
        description="body-frame position of the part's own CoG [m]"
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


class DroneDesign(BaseModel):
    """Full design snapshot — the exact input to a simulation run."""

    schema_version: Literal["0.1"] = "0.1"
    name: str
    parts: list[PartInstance] = Field(min_length=1)
    rotors: list[RotorInstance] = Field(min_length=1)
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
