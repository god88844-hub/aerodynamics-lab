"""M16: immutable third-party physical telemetry audit — no physics promotion.

A published PX4 quadplane battery CSV is copied with CC BY 4.0 attribution.
Its electrical readings are real-world *reported* observations; the file
lacks timestamps and hardware-specific pack specifications. We therefore
audit source integrity and observational envelopes ONLY, not predict flight.
"""
from __future__ import annotations

import csv
from hashlib import sha1
import io
import json
import math
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data" / "benchmarks" / "public" / "quadplane_2022"
SOURCE_REGISTER = REPO_ROOT / "data" / "benchmarks" / "public_sources.json"

EXPECTED_COLUMNS = (
    "BATT_VFilt", "BATT_CFilt", "BATT_Discharged", "BATT_Remaining",
    "BATT_RemainingV", "BATT_Warning",
)


def _finite_number(value: str, *, row: int, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row}: {field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"row {row}: {field} must be finite")
    return number


def audit_quadplane_battery(*, data_dir: Path | None = None) -> dict:
    """Audit a third-party physical log without imputing absent timestamps.

    The source's immutable Git blob SHA-1 is a **provenance equality check**,
    not a cryptographic signature by the aircraft/instrument operator.
    """
    directory = data_dir if data_dir is not None else DATA_DIR
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("id") != "quadplane_px4_batt_2022":
        raise ValueError("unexpected physical evidence manifest identifier")
    if manifest.get("license") != "CC BY 4.0":
        raise ValueError("physical dataset license and required attribution not confirmed")
    if manifest.get("timestamp_column_available") is not False:
        raise ValueError("timestamp availability misrepresented in source manifest")
    if manifest.get("battery_model_match_verified") is not False:
        raise ValueError("unverified vehicle hardware must not be marked matched")
    raw = (directory / "BATT.csv").read_bytes()
    # Git hashes a blob as SHA1("blob <length>\\0" || file_bytes).
    git_blob = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
    if git_blob != manifest.get("upstream_git_blob_sha1"):
        raise ValueError("physical evidence byte integrity mismatch against pinned upstream Git blob")
    try:
        content = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("unsupported non-UTF8 flight evidence") from exc
    reader = csv.DictReader(io.StringIO(content))
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise ValueError("physical evidence channel names or schema differ from provenance")
    rows = []
    for index, record in enumerate(reader, start=2):
        if None in record or any(record[name] is None for name in EXPECTED_COLUMNS):
            raise ValueError(f"row {index}: unexpected field count")
        numbers = {
            key: _finite_number(record[key], row=index, field=key)
            for key in EXPECTED_COLUMNS
        }
        if (numbers["BATT_VFilt"] <= 0 or numbers["BATT_CFilt"] < 0
                or numbers["BATT_Discharged"] < 0
                or not 0 <= numbers["BATT_Remaining"] <= 1
                or not 0 <= numbers["BATT_RemainingV"] <= 1
                or numbers["BATT_Warning"] not in (0, 1, 2, 3)):
            raise ValueError(f"row {index}: physically invalid source channel value")
        rows.append(numbers)
    if len(rows) != manifest.get("sample_count") or len(rows) < 10:
        raise ValueError("source row count differs from pinned manifest")
    count_discharge_decreases = sum(
        b["BATT_Discharged"] < a["BATT_Discharged"]
        for a, b in zip(rows, rows[1:])
    )
    count_remaining_increases = sum(
        b["BATT_Remaining"] > a["BATT_Remaining"]
        for a, b in zip(rows, rows[1:])
    )
    if count_discharge_decreases or count_remaining_increases:
        raise ValueError("cumulative discharge/remaining capacity are not monotonic")
    first, last = rows[0], rows[-1]
    volts = [p["BATT_VFilt"] for p in rows]
    currents = [p["BATT_CFilt"] for p in rows]
    powers = [v * i for v, i in zip(volts, currents)]
    delta_mah = last["BATT_Discharged"] - first["BATT_Discharged"]
    fraction_drop = first["BATT_Remaining"] - last["BATT_Remaining"]
    if delta_mah < 0 or fraction_drop < 0:
        raise ValueError("nonphysical cumulative battery readings")
    # This is NOT a measured actual pack capacity: PX4 derives both channels
    # from its same coulomb counter + configured nominal capacity.
    implied_configured_capacity_mah = (
        delta_mah / fraction_drop if fraction_drop > 0 else None
    )
    return {
        "dataset_id": manifest["id"],
        "source": {
            "reported_physical_log": True,
            "source_url": manifest["original_source"],
            "authors": manifest["authors"],
            "upstream_commit": manifest["upstream_commit"],
            "git_blob_sha1": git_blob,
            "bytes": len(raw),
            "license": manifest["license"],
            "license_url": manifest["license_url"],
            "instrument_and_identity_authenticated_by_aeroforge": False,
        },
        "quality": {
            "rows_verified": len(rows),
            "numeric_and_finite": True,
            "counter_monotonic": True,
            "remaining_fraction_nonincreasing": True,
            "per_row_timestamps_present": False,
            "synchronized_with_aeroforge_simulation": False,
            "hardware_model_match_verified": False,
        },
        "observed": {
            "voltage_range_v": [min(volts), max(volts)],
            "current_range_a": [min(currents), max(currents)],
            "peak_sampled_pack_electrical_power_w": max(powers),
            "discharge_counter_at_start_mah": first["BATT_Discharged"],
            "discharge_counter_at_end_mah": last["BATT_Discharged"],
            "difference_in_reported_discharge_counter_mah": delta_mah,
            "remaining_capacity_fraction_first": first["BATT_Remaining"],
            "remaining_capacity_fraction_last": last["BATT_Remaining"],
            "controller_implied_nominal_capacity_mah_not_independent_measurement":
                implied_configured_capacity_mah,
            "power_time_integral_wh": None,
            "independently_measured_capacity_ah": None,
            "per_row_time_s": None,
        },
        "benchmark_status": "PUBLIC_PHYSICAL_OBSERVATIONS_AUDITED_NOT_MODEL_VALIDATION",
        "validated_flight_prediction_error": None,
        "near_real_world_equivalence_established": False,
        "limitations": [
            "A copied source CSV and matching Git blob hash do not authenticate aircraft instrumentation",
            "Per-row timestamps are absent: never infer uniform sampling or integrate power against guessed time",
            "PX4 consumed-charge and remaining-capacity channels share controller processing, not independent capacity measurements",
            "Log includes an approximately 24-minute session but only approximately six minutes actual flight",
            "Actual pack serial, resistance, full calibration certificates and exact vehicle geometry are unavailable",
            "The logged aircraft is a VTOL quadplane, not an AeroForge reference multirotor configuration",
            "No model prediction has been compared to this trace; observational audits cannot be promoted to validation",
        ],
    }


def get_public_source_inventory(*, path: Path | None = None) -> dict:
    register = json.loads((path or SOURCE_REGISTER).read_text(encoding="utf-8"))
    datasets = register.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("physical evidence source registry is empty or malformed")
    ids = [d.get("id") for d in datasets]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("physical source identifiers must be unique")
    if any(not d.get("url") or not d.get("source_status") or not d.get("ingestion_status")
           for d in datasets):
        raise ValueError("source registry must preserve provenance and availability")
    return register
