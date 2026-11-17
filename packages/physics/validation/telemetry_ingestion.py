"""M19: traceable, fail-closed ingestion of *reported* flight electrical telemetry.

This is an evidence-quality audit, not aircraft-model validation. Source identity,
hardware match, calibration status and clock uncertainty are operator assertions
unless independently verified outside this module.

CSV format: t_s,terminal_voltage_v,current_a[,temperature_c,altitude_m,
vertical_speed_m_s,wind_speed_m_s]. Units are SI and are NOT inferred.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import re
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVIDENCE_ROOT = REPO_ROOT / "data" / "benchmarks" / "telemetry"
MAX_CSV_BYTES = 5_000_000
MAX_SAMPLES = 50_000

Channel = Literal[
    "t_s", "terminal_voltage_v", "current_a", "temperature_c",
    "altitude_m", "vertical_speed_m_s", "wind_speed_m_s",
]
_UNITS = {
    "t_s": "s", "terminal_voltage_v": "V", "current_a": "A",
    "temperature_c": "degC", "altitude_m": "m",
    "vertical_speed_m_s": "m/s", "wind_speed_m_s": "m/s",
}
_SAFENAME = re.compile(r"^[a-zA-Z0-9_.-]{1,116}\.csv$")


class TelemetryManifest(BaseModel):
    """One frozen source recording, not an individual sample or flight segment."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    schema_version: Literal["1.0"]
    dataset_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    dataset_kind: Literal["synthetic_fixture", "reported_physical_measurements"]
    partition_role: Literal["calibration", "holdout", "unassigned"]
    experiment_id: str = Field(min_length=1, max_length=120)
    recording_id: str = Field(min_length=1, max_length=120)
    vehicle_id: str = Field(min_length=1, max_length=120)
    battery_id: str = Field(min_length=1, max_length=120)
    source_reference: str = Field(min_length=1, max_length=1000)
    license_or_permission: str = Field(min_length=1, max_length=200)
    instrument_calibration_reference: str | None = Field(default=None, max_length=500)
    clock_alignment_error_bound_s: float | None = Field(default=None, ge=0, le=2)
    filename: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,116}\.csv$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_samples: int = Field(ge=6, le=MAX_SAMPLES)
    predeclared_max_sample_gap_s: float = Field(gt=0, le=300)
    columns: list[Channel] = Field(min_length=3, max_length=len(_UNITS))

    @model_validator(mode="after")
    def check_schema(self) -> "TelemetryManifest":
        if self.columns[0] != "t_s":
            raise ValueError("first telemetry column must be t_s")
        if len(self.columns) != len(set(self.columns)):
            raise ValueError("duplicate telemetry channel")
        if not {"terminal_voltage_v", "current_a"}.issubset(self.columns):
            raise ValueError("must include voltage and current channels")
        for attr in ("experiment_id", "recording_id", "vehicle_id", "battery_id",
                     "source_reference", "license_or_permission"):
            if not getattr(self, attr).strip():
                raise ValueError(f"{attr} cannot be blank")
        if (self.instrument_calibration_reference is not None
                and not self.instrument_calibration_reference.strip()):
            raise ValueError("instrument calibration reference cannot be empty")
        return self


class InlineTelemetryDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: TelemetryManifest
    csv_text: str = Field(min_length=1, max_length=MAX_CSV_BYTES)


class TelemetryAuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    datasets: list[InlineTelemetryDataset] = Field(min_length=1, max_length=16)


def audit_telemetry_csv(manifest: TelemetryManifest, raw: bytes) -> dict:
    """Never replace, resample, retime, correct or fit user-supplied observations."""
    if not raw or len(raw) > MAX_CSV_BYTES:
        raise ValueError("telemetry CSV must be 1 to 5,000,000 bytes")
    digest = sha256(raw).hexdigest()
    if digest != manifest.raw_sha256:
        raise ValueError(f"{manifest.dataset_id}: raw telemetry SHA-256 mismatch")
    try:
        decoded = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("telemetry must be valid UTF-8") from exc
    if decoded.startswith("\ufeff"):
        raise ValueError("UTF-8 BOM is not accepted; keep canonical raw bytes")
    rows = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        header = next(rows)
    except StopIteration as exc:
        raise ValueError("telemetry CSV is empty") from exc
    if header != manifest.columns:
        raise ValueError(
            f"{manifest.dataset_id}: actual columns differ from explicitly declared columns"
        )
    first_time = None
    previous_time = None
    previous_voltage = None
    previous_current = None
    consumed_charge_ah = 0.0
    delivered_energy_wh = 0.0
    max_gap = 0.0
    voltage_min = math.inf
    voltage_max = -math.inf
    current_min = math.inf
    current_max = -math.inf
    count = 0
    first_row = None
    for values in rows:
        count += 1
        if count > MAX_SAMPLES:
            raise ValueError("more than 50,000 telemetry samples")
        if len(values) != len(header) or any(not value.strip() for value in values):
            raise ValueError(f"row {count + 1}: missing or extra field")
        try:
            readings = [float(value) for value in values]
        except ValueError as exc:
            raise ValueError(f"row {count + 1}: nonnumeric telemetry field") from exc
        if not all(math.isfinite(value) for value in readings):
            raise ValueError(f"row {count + 1}: nonfinite telemetry field")
        row = dict(zip(header, readings))
        t, v, i = row["t_s"], row["terminal_voltage_v"], row["current_a"]
        if t < 0 or v <= 0 or i < 0:
            raise ValueError(f"row {count + 1}: time/current/voltage outside physical bounds")
        if "wind_speed_m_s" in row and row["wind_speed_m_s"] < 0:
            raise ValueError(f"row {count + 1}: negative wind speed")
        if previous_time is None:
            if t != 0:
                raise ValueError("elapsed time must start at exactly zero")
            first_time, first_row = t, row
        else:
            delta = t - previous_time
            if delta <= 0:
                raise ValueError(f"row {count + 1}: timestamps not strictly increasing")
            max_gap = max(max_gap, delta)
            consumed_charge_ah += (previous_current + i) * delta / 7200.0
            delivered_energy_wh += (
                previous_voltage * previous_current + v * i
            ) * delta / 7200.0
            if not math.isfinite(consumed_charge_ah) or not math.isfinite(delivered_energy_wh):
                raise ValueError("integrated charge or energy exceeded finite numeric range")
        voltage_min = min(voltage_min, v)
        voltage_max = max(voltage_max, v)
        current_min = min(current_min, i)
        current_max = max(current_max, i)
        previous_time, previous_voltage, previous_current = t, v, i
    if count != manifest.expected_samples:
        raise ValueError(
            f"{manifest.dataset_id}: expected {manifest.expected_samples} samples, found {count}"
        )
    # Counts and energy depend on samples and sensor properties, not proof
    # of independent measurement or physical prediction accuracy.
    sampling_ok = max_gap <= manifest.predeclared_max_sample_gap_s
    return {
        "dataset_id": manifest.dataset_id,
        "dataset_kind": manifest.dataset_kind,
        "partition_role": manifest.partition_role,
        "experiment_id": manifest.experiment_id,
        "recording_id": manifest.recording_id,
        "vehicle_id": manifest.vehicle_id,
        "battery_id": manifest.battery_id,
        "source_reference": manifest.source_reference,
        "license_or_permission": manifest.license_or_permission,
        "raw_sha256_verified_against_manifest": digest,
        "raw_bytes": len(raw),
        "rows": count,
        "columns_with_declared_units": {col: _UNITS[col] for col in header},
        "quality": {
            "finite_values": True,
            "strictly_increasing_timestamps": True,
            "max_gap_s": max_gap,
            "sampling_interval_within_predeclared_bound": sampling_ok,
            "sampling_adequacy_verified": False,
            "instrument_calibration_reference_supplied": bool(
                manifest.instrument_calibration_reference
            ),
            "clock_alignment_error_bound_declared": (
                manifest.clock_alignment_error_bound_s is not None
            ),
        },
        "observations": {
            "duration_s": previous_time - first_time,
            "voltage_range_v": [voltage_min, voltage_max],
            "current_range_a": [current_min, current_max],
            # Reject energy integration from samples too sparse for
            # the operator's predeclared time-resolution requirement.
            "trapezoidal_reported_charge_ah": consumed_charge_ah if sampling_ok else None,
            "trapezoidal_reported_energy_wh": delivered_energy_wh if sampling_ok else None,
        },
        "status": (
            "SYNTHETIC_VERIFICATION_ONLY"
            if manifest.dataset_kind == "synthetic_fixture"
            else ("OBSERVATIONS_AUDITED_PROVENANCE_UNAUTHENTICATED"
                  if sampling_ok else "SPARSE_TIMESTAMPS_UNSUITABLE_FOR_ENERGY_ACCOUNTING")
        ),
        "predicted_aircraft_performance_error": None,
        "physically_validated_model": False,
    }


def audit_partition(items: list[tuple[TelemetryManifest, dict]]) -> dict:
    """Audit split *by entire experiment, recording, pack and vehicle*.

    The "physical" label and declared group IDs are user-controlled. Passing
    here only checks manifest claims for leakage; it never authenticates
    independent blind experiments.
    """
    if not items:
        return {
            "status": "NO_EVIDENCE_IMPORTED", "cross_partition_collisions": [],
            "physical_validation_established": False,
        }
    seen = set()
    for m, _ in items:
        if m.dataset_id in seen:
            raise ValueError(f"duplicate dataset ID {m.dataset_id}")
        seen.add(m.dataset_id)
    calibration = [m for m, _ in items if m.partition_role == "calibration"]
    holdout = [m for m, _ in items if m.partition_role == "holdout"]
    collisions = []
    fields = (
        "recording_id", "experiment_id", "battery_id", "vehicle_id", "raw_sha256",
    )
    for cal in calibration:
        for val in holdout:
            overlapping = [f for f in fields if getattr(cal, f) == getattr(val, f)]
            if overlapping:
                collisions.append({
                    "calibration_dataset_id": cal.dataset_id,
                    "holdout_dataset_id": val.dataset_id,
                    "shared_identifiers": overlapping,
                })
    physical = [m for m, _ in items if m.dataset_kind == "reported_physical_measurements"]
    all_dense = all(x["quality"]["sampling_interval_within_predeclared_bound"]
                    for _, x in items)
    if collisions:
        status = "CROSS_PARTITION_LEAKAGE_DECLARED"
    elif not calibration or not holdout:
        status = "NO_COMPLETE_CALIBRATION_HOLDOUT_SPLIT"
    elif len(physical) != len(items):
        status = "SYNTHETIC_OR_MIXED_DATASET_NO_PHYSICAL_VALIDATION"
    elif not all_dense:
        status = "INSUFFICIENT_DECLARED_SAMPLING"
    else:
        status = "DECLARED_DISJOINT_SPLIT_NOT_INDEPENDENTLY_AUTHENTICATED"
    return {
        "status": status,
        "calibration_count": len(calibration),
        "holdout_count": len(holdout),
        "unassigned_count": len(items) - len(calibration) - len(holdout),
        "cross_partition_collisions": collisions,
        "same_vehicle_and_battery_disjoint_required": True,
        "operator_metadata_not_authenticated": True,
        "physical_validation_established": False,
        "meaning": (
            "A group-disjoint source audit is not an error metric against "
            "a frozen predictive model, an independent proof of provenance, "
            "or a demonstration of flight readiness"
        ),
    }


def audit_telemetry_bundle(
    bundles: list[tuple[TelemetryManifest, bytes]],
) -> dict:
    audited = [(m, audit_telemetry_csv(m, raw)) for m, raw in bundles]
    return {
        "schema_version": "1.0",
        "datasets": [result for _, result in audited],
        "partition": audit_partition(audited),
        "near_real_world_simulation_accuracy_established": False,
        "limitations": [
            "Source files are checksum matched to self-declared manifests, not independently authenticated",
            "Hardware identifiers and role assignment are operator-supplied and unverified",
            "Time-dense integrals are descriptive measurements conditioned on reported sensors",
            "Without independent sensor uncertainty, actual true energy bounds cannot be inferred",
            "Actual simulator prediction comparisons, blind tests and repeated independent runs remain missing",
            "No telemetry is written, calibrated into a model or certified by this audit",
        ],
    }


def audit_telemetry_directory(root: Path = DEFAULT_EVIDENCE_ROOT) -> dict:
    """Read immutable local bundles, never follow filenames outside their folder."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("telemetry root must be an existing non-symlink directory")
    bundles = []
    for folder in sorted(root.iterdir(), key=lambda p: p.name):
        if not folder.is_dir():
            continue
        if folder.is_symlink():
            raise ValueError("symlink telemetry bundle rejected")
        manifest_file = folder / "manifest.json"
        if not manifest_file.is_file() or manifest_file.is_symlink():
            raise ValueError(f"{folder.name}: missing or symlinked manifest.json")
        manifest = TelemetryManifest.model_validate_json(
            manifest_file.read_text(encoding="utf-8")
        )
        if manifest.dataset_id != folder.name or not _SAFENAME.fullmatch(manifest.filename):
            raise ValueError("dataset ID or filename conflicts with directory layout")
        input_file = folder / manifest.filename
        if not input_file.is_file() or input_file.is_symlink():
            raise ValueError("missing or symlinked CSV source file")
        if input_file.stat().st_size > MAX_CSV_BYTES:
            raise ValueError("telemetry file exceeds size limit")
        bundles.append((manifest, input_file.read_bytes()))
    return audit_telemetry_bundle(bundles)
