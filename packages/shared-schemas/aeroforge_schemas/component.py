"""Component evidence-database schemas and provenance validation (P0A-016).

Every component entry carries a `source` block (provenance), physical identity,
explicit SI units, declared operating limits, and parameter-level evidence.
Unsourced typical values and assumed uncertainty bands must be flagged
`UNVERIFIED_ESTIMATE`; missing required limits or missing density/source
refuse acceptance rather than inventing defaults ("no fake data" rule).
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

UNVERIFIED_ESTIMATE = "UNVERIFIED_ESTIMATE"
SOURCED = "SOURCED"

_ESTIMATE_HINTS = (
    "typical",
    "assumed",
    "placeholder",
    "estimate",
    "estimated",
    "unsourced",
    "generic",
    "unlisted",
)


def _has_estimate_hint(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(hint in lowered for hint in _ESTIMATE_HINTS)


class SourceInfo(BaseModel):
    """Provenance of a datum or dataset. `estimated=True` marks values that
    are NOT sourced measurements (large uncertainty, flagged in reports)."""

    source: str = Field(description="human-readable provenance, e.g. 'T-Motor test report MN.00011'")
    url: str | None = None
    report_id: str | None = None
    evidence_id: str | None = Field(
        default=None,
        description="registry/campaign or datasheet evidence identifier in data/research/registry.json",
    )
    retrieved: str | None = Field(default=None, description="ISO date the data was captured")
    uncertainty_pct: float = Field(default=5.0, ge=0.0)
    estimated: bool = Field(
        default=False, description="True when the value is an estimate, not measured/sourced"
    )
    status: Literal["SOURCED", "UNVERIFIED_ESTIMATE"] | None = None
    notes: str | None = None

    @property
    def effective_status(self) -> Literal["SOURCED", "UNVERIFIED_ESTIMATE"]:
        if self.status == UNVERIFIED_ESTIMATE or self.estimated:
            return UNVERIFIED_ESTIMATE
        if _has_estimate_hint(self.source) or _has_estimate_hint(self.notes):
            return UNVERIFIED_ESTIMATE
        return SOURCED


class ParameterProvenance(BaseModel):
    """Parameter-level unit, citation, uncertainty band, and UNVERIFIED_ESTIMATE status."""

    unit: str = Field(min_length=1, description="Explicit SI unit (or '1' for dimensionless)")
    source: str = Field(min_length=1, description="Parameter-level datasheet/measurement citation")
    uncertainty_pct: float = Field(ge=0.0)
    estimated: bool = False
    status: Literal["SOURCED", "UNVERIFIED_ESTIMATE"] = SOURCED
    evidence_id: str | None = Field(
        default=None,
        description="Link to data/research/registry.json entry or report identifier",
    )
    notes: str | None = None

    @model_validator(mode="after")
    def _enforce_unverified_estimate_rule(self) -> "ParameterProvenance":
        if not math.isfinite(self.uncertainty_pct):
            raise ValueError("parameter uncertainty_pct must be finite")
        if not self.source.strip() or not self.unit.strip():
            raise ValueError("parameter unit and source must be non-empty")
        inferred_estimated = self.estimated or _has_estimate_hint(self.source) or _has_estimate_hint(self.notes)
        if inferred_estimated and self.status != UNVERIFIED_ESTIMATE:
            raise ValueError(
                "unsourced, typical, placeholder, or assumed parameter values must carry status='UNVERIFIED_ESTIMATE'"
            )
        if self.status == UNVERIFIED_ESTIMATE and not self.estimated:
            self.estimated = True
        return self


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
    physical_identity: dict[str, Any] | None = None
    units: dict[str, str] | None = None
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
    operating_limits: dict[str, float | int] | None = None
    source: SourceInfo
    parameter_provenance: dict[str, ParameterProvenance] | None = None
    test_data: list[TestDataPoint] = Field(default_factory=list)


class PropellerSpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    physical_identity: dict[str, Any] | None = None
    units: dict[str, str] | None = None
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
    operating_limits: dict[str, float | int] | None = None
    source: SourceInfo
    parameter_provenance: dict[str, ParameterProvenance] | None = None


class OcvPoint(BaseModel):
    soc_pct: float = Field(ge=0.0, le=100.0)
    cell_voltage_v: float = Field(gt=0.0)


class BatterySpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    physical_identity: dict[str, Any] | None = None
    units: dict[str, str] | None = None
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
    operating_limits: dict[str, float | int] | None = None
    source: SourceInfo
    parameter_provenance: dict[str, ParameterProvenance] | None = None


class EscSpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    physical_identity: dict[str, Any] | None = None
    units: dict[str, str] | None = None
    max_continuous_current_a: float = Field(gt=0.0)
    max_voltage_v: float | None = None
    mass_kg: float | None = None
    operating_limits: dict[str, float | int] | None = None
    source: SourceInfo
    parameter_provenance: dict[str, ParameterProvenance] | None = None


class WiringSpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    physical_identity: dict[str, Any]
    units: dict[str, str]
    conductor_material: str
    awg: int | None = None
    cross_section_m2: float = Field(gt=0.0)
    resistance_ohm_per_m: float = Field(gt=0.0)
    mass_kg_per_m: float = Field(gt=0.0)
    max_continuous_current_a: float = Field(gt=0.0)
    max_voltage_v: float = Field(gt=0.0)
    max_temperature_c: float
    operating_limits: dict[str, float | int]
    source: SourceInfo
    parameter_provenance: dict[str, ParameterProvenance]


class SensorSpec(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    id: str
    name: str
    sensor_kind: Literal["imu", "barometer", "gnss", "magnetometer", "current_voltage"]
    physical_identity: dict[str, Any]
    units: dict[str, str]
    sample_rate_hz: float = Field(gt=0.0)
    latency_s: float = Field(ge=0.0)
    noise_density: float = Field(ge=0.0)
    bias_instability: float = Field(ge=0.0)
    mass_kg: float = Field(gt=0.0)
    operating_limits: dict[str, float | int]
    source: SourceInfo
    parameter_provenance: dict[str, ParameterProvenance]


class MaterialRecord(BaseModel):
    id: str
    name: str
    category: str
    physical_identity: dict[str, Any]
    units: dict[str, str]
    density_kg_m3: float = Field(gt=0.0)
    youngs_modulus_pa: float = Field(gt=0.0)
    yield_strength_pa: float = Field(gt=0.0)
    ultimate_tensile_strength_pa: float = Field(gt=0.0)
    operating_limits: dict[str, float | int]
    notes: str
    source: str = Field(min_length=1)
    evidence_id: str | None = None
    uncertainty_pct: float = Field(ge=0.0)
    estimated: bool = False
    status: Literal["SOURCED", "UNVERIFIED_ESTIMATE"] = SOURCED
    parameter_provenance: dict[str, ParameterProvenance]

    @model_validator(mode="after")
    def _validate_finite_and_status(self) -> "MaterialRecord":
        for fname in (
            "density_kg_m3",
            "youngs_modulus_pa",
            "yield_strength_pa",
            "ultimate_tensile_strength_pa",
            "uncertainty_pct",
        ):
            val = getattr(self, fname)
            if not math.isfinite(val):
                raise ValueError(f"material {self.id!r} field {fname} must be finite")
        if not self.source.strip():
            raise ValueError(f"material {self.id!r} missing source")
        if (self.estimated or _has_estimate_hint(self.source) or _has_estimate_hint(self.notes)) and self.status != UNVERIFIED_ESTIMATE:
            raise ValueError(f"material {self.id!r} typical/estimated values must use status='UNVERIFIED_ESTIMATE'")
        return self


class MaterialsCatalog(BaseModel):
    schema_version: str = Field(default="aeroforge/materials@0.1", alias="$schema")
    description: str
    units: dict[str, str]
    materials: list[MaterialRecord]


_REQUIRED_FIELDS_BY_KIND: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # (required top-level/limit keys in operating_limits, required provenance keys)
    "battery": (
        ("cutoff_cell_voltage_v", "warning_cell_voltage_v", "max_cell_voltage_v", "max_discharge_c", "min_temp_c", "max_temp_c"),
        ("capacity_ah", "internal_resistance_ohm", "mass_kg", "max_discharge_c", "ocv_curve", "cutoff_cell_voltage_v"),
    ),
    "motor": (
        ("max_continuous_current_a", "max_continuous_power_w", "cells_min", "cells_max", "max_winding_temp_c"),
        ("kv_rpm_per_v", "internal_resistance_ohm", "max_continuous_current_a", "max_continuous_power_w", "mass_kg"),
    ),
    "esc": (
        ("max_continuous_current_a", "max_voltage_v", "max_temp_c"),
        ("max_continuous_current_a", "max_voltage_v", "mass_kg"),
    ),
    "propeller": (
        ("max_rpm", "min_temp_c", "max_temp_c"),
        ("diameter_in", "pitch_in", "mass_kg"),
    ),
    "wiring": (
        ("max_continuous_current_a", "max_voltage_v", "max_temperature_c"),
        ("cross_section_m2", "resistance_ohm_per_m", "mass_kg_per_m", "max_continuous_current_a", "max_voltage_v"),
    ),
    "sensor": (
        ("min_voltage_v", "max_voltage_v", "min_temp_c", "max_temp_c", "sample_rate_hz"),
        ("sample_rate_hz", "latency_s", "noise_density", "bias_instability", "mass_kg"),
    ),
    "material": (
        ("min_service_temp_c", "max_service_temp_c"),
        ("density_kg_m3", "youngs_modulus_pa", "yield_strength_pa", "ultimate_tensile_strength_pa"),
    ),
}


def collect_unverified_estimates(record: BaseModel) -> list[str]:
    """Return every parameter or record field flagged UNVERIFIED_ESTIMATE."""
    flagged: list[str] = []
    source = getattr(record, "source", None)
    if isinstance(source, SourceInfo):
        if source.effective_status == UNVERIFIED_ESTIMATE:
            flagged.append("record.source")
    elif isinstance(record, MaterialRecord):
        if record.status == UNVERIFIED_ESTIMATE or record.estimated:
            flagged.append("record.source")
    provenance = getattr(record, "parameter_provenance", None) or {}
    for param, entry in sorted(provenance.items()):
        if entry.status == UNVERIFIED_ESTIMATE or entry.estimated:
            flagged.append(param)
    return flagged


def validate_component_record_acceptance(record: BaseModel, kind: str) -> dict[str, Any]:
    """Refuse acceptance when units, identity, source, limits, or provenance are incomplete."""
    if kind not in _REQUIRED_FIELDS_BY_KIND:
        raise ValueError(f"unknown component kind {kind!r}")
    ident = getattr(record, "physical_identity", None)
    if not ident or not any(str(v).strip() for v in ident.values() if v is not None):
        raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: missing physical_identity")
    units = getattr(record, "units", None)
    if not units or not all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in units.items()):
        raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: missing explicit SI units")
    limits = getattr(record, "operating_limits", None)
    if not limits:
        raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: missing operating_limits")
    req_limits, req_prov = _REQUIRED_FIELDS_BY_KIND[kind]
    for limit_key in req_limits:
        if limit_key not in limits or limits[limit_key] is None:
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: missing required operating limit {limit_key!r}")
        val = float(limits[limit_key])
        if not math.isfinite(val):
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: nonfinite limit {limit_key!r}")
        if any(tok in limit_key for tok in ("current", "power", "voltage", "discharge", "rpm", "rate", "cells")) and "min_temp" not in limit_key and val <= 0.0:
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: limit {limit_key!r} must be > 0")
    if "min_temp_c" in limits and "max_temp_c" in limits:
        if float(limits["min_temp_c"]) >= float(limits["max_temp_c"]):
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: min_temp_c must be < max_temp_c")
    if "min_service_temp_c" in limits and "max_service_temp_c" in limits:
        if float(limits["min_service_temp_c"]) >= float(limits["max_service_temp_c"]):
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: min_service_temp_c must be < max_service_temp_c")
    if "min_voltage_v" in limits and "max_voltage_v" in limits:
        if float(limits["min_voltage_v"]) >= float(limits["max_voltage_v"]):
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: min_voltage_v must be < max_voltage_v")
    if isinstance(record, BatterySpec):
        if record.warning_cell_voltage_v <= record.cutoff_cell_voltage_v:
            raise ValueError(f"battery/{record.id}: warning_cell_voltage_v must exceed cutoff_cell_voltage_v")
    prov = getattr(record, "parameter_provenance", None)
    if not prov:
        raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: missing parameter_provenance")
    for pkey in req_prov:
        if pkey not in prov:
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: missing parameter provenance for {pkey!r}")
        entry = prov[pkey]
        if not entry.evidence_id and not (isinstance(getattr(record, "source", None), SourceInfo) and (record.source.evidence_id or record.source.url or record.source.report_id)):
            raise ValueError(f"{kind}/{getattr(record, 'id', '?')}: parameter {pkey!r} lacks evidence link")
    unverified = collect_unverified_estimates(record)
    return {
        "accepted": True,
        "kind": kind,
        "id": record.id,
        "provenance_status": UNVERIFIED_ESTIMATE if unverified else SOURCED,
        "unverified_estimates": unverified,
    }
