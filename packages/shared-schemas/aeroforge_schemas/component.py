"""Component evidence-database schemas.

Every component entry carries a `source` block (provenance) and per-datum
uncertainty. Unknown values are `null` and flagged — never guessed: a design
that needs an unknown datum cannot pass validation until the user supplies it
with an explicit uncertainty ("no fake data" rule).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    """Provenance of a datum or dataset. `estimated=True` marks values that
    are NOT sourced measurements (large uncertainty, flagged in reports)."""

    source: str = Field(description="human-readable provenance, e.g. 'T-Motor test report MN.00011'")
    url: str | None = None
    report_id: str | None = None
    retrieved: str | None = Field(default=None, description="ISO date the data was captured")
    uncertainty_pct: float = Field(default=5.0, ge=0.0)
    estimated: bool = Field(
        default=False, description="True when the value is an estimate, not measured/sourced"
    )
    notes: str | None = None


class TestDataPoint(BaseModel):
    """One row of a manufacturer thrust-bench table (static conditions)."""

    throttle_pct: float = Field(ge=0.0, le=100.0)
    voltage_v: float = Field(
        gt=0.0,
        description="bus voltage of the interpolation plane this row belongs to "
        "(rows are grouped into voltage planes by this value)",
    )
    voltage_measured_v: float | None = Field(
        default=None,
        description="actual measured bus voltage of the row, when the source "
        "publishes per-row sag (provenance; the plane uses voltage_v)",
    )
    current_a: float = Field(gt=0.0)
    power_w: float = Field(gt=0.0)
    thrust_gf: float = Field(ge=0.0, description="grams-force, as published")
    torque_nm: float | None = Field(
        default=None, description="shaft torque [N·m] when the source publishes it"
    )
    rpm: float = Field(gt=0.0)
    prop: str = Field(description="prop identifier used in the bench test, verbatim from source")
    source: SourceInfo


class MotorSpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    kv_rpm_per_v: float | None = None
    internal_resistance_ohm: float | None = Field(
        default=None,
        description="manufacturer-measured winding resistance; note: the lumped DC "
        "model using this value does NOT reproduce loaded bench points (inductive/"
        "timing effects) — see physics/propulsion/dataset.py",
    )
    idle_current_a: float | None = None
    idle_current_voltage_v: float | None = None
    max_continuous_current_a: float | None = None
    max_continuous_power_w: float | None = None
    max_continuous_duration_s: float | None = None
    mass_kg: float | None = None
    cells_min: int | None = None
    cells_max: int | None = None
    configuration: str | None = Field(default=None, description="e.g. '12N14P'")
    source: SourceInfo
    test_data: list[TestDataPoint] = Field(default_factory=list)


class PropellerSpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    diameter_in: float = Field(gt=0.0)
    pitch_in: float = Field(gt=0.0)
    mass_kg: float | None = Field(
        default=None, description="null = unknown; design assembly then requires a user-supplied value"
    )
    material: str | None = None
    motor_test_data_key: str | None = Field(
        default=None,
        description="selects the matching prop key in the motor's test_data rows",
    )
    source: SourceInfo


class OcvPoint(BaseModel):
    soc_pct: float = Field(ge=0.0, le=100.0)
    cell_voltage_v: float = Field(gt=0.0)


class BatterySpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    chemistry: Literal["LiPo", "Li-ion"]
    cells_series: int = Field(ge=1)
    capacity_ah: float = Field(gt=0.0)
    internal_resistance_ohm: float | None = Field(
        default=None, description="pack-level DC internal resistance; null = unknown"
    )
    mass_kg: float | None = None
    max_discharge_c: float | None = None
    ocv_curve: list[OcvPoint] = Field(
        description="open-circuit voltage per CELL vs state of charge, ascending in SOC"
    )
    cutoff_cell_voltage_v: float = Field(default=3.30, description="damage threshold per cell")
    warning_cell_voltage_v: float = Field(default=3.50, description="land-now threshold per cell")
    source: SourceInfo


class EscSpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    max_continuous_current_a: float = Field(gt=0.0)
    max_voltage_v: float | None = None
    mass_kg: float | None = None
    source: SourceInfo
