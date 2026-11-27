"""P0D-002: Immutable versioned component, material, and experimental source custody ingestion."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any


def ingest_custody_record(
    store: dict[str, dict[str, Any]],
    *,
    record_id: str,
    dated_version: str,
    units: str,
    rights_scope: str,
    raw_bytes: bytes,
    experiment_role: str,
    instrument_uncertainty_rel: float | None = None,
    has_measured_source: bool = True,
) -> dict[str, Any]:
    """Validate and append an immutable dated custody record into `store` without overwriting history."""
    clean_id = record_id.strip()
    clean_ver = dated_version.strip()
    if not clean_id or not clean_ver:
        raise ValueError("record_id and dated_version must be non-empty")
    if units != "SI":
        raise ValueError(f"Unsupported unit system {units!r}; SI required for custody ingestion")
    if not rights_scope.strip():
        raise ValueError("Ingestion refused: source license/rights_scope is required")
    if experiment_role not in ("calibration", "holdout", "benchmark_reference", "component_datasheet"):
        raise ValueError(f"Unsupported experiment_role {experiment_role!r}")
    if instrument_uncertainty_rel is not None and (not math.isfinite(instrument_uncertainty_rel) or instrument_uncertainty_rel <= 0.0):
        raise ValueError("instrument_uncertainty_rel must be positive when supplied")

    snapshot_key = f"{clean_id}@{clean_ver}"
    if snapshot_key in store:
        raise ValueError(f"Immutable custody violation: historical snapshot {snapshot_key!r} cannot be overwritten")

    digest = sha256(raw_bytes).hexdigest()
    provenance_tag = "SOURCED_MEASUREMENT" if has_measured_source else "UNVERIFIED_ESTIMATE"
    entry = {
        "schema_version": "1.0",
        "snapshot_key": snapshot_key,
        "record_id": clean_id,
        "dated_version": clean_ver,
        "units": units,
        "rights_scope": rights_scope.strip(),
        "raw_sha256": digest,
        "experiment_role": experiment_role,
        "instrument_uncertainty_rel": instrument_uncertainty_rel,
        "provenance_status": provenance_tag,
    }
    store[snapshot_key] = entry
    return dict(entry)
