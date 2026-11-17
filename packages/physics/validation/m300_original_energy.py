"""M26.30–M26.33: source-verified M300 session telemetry and energy accounting.

30: Repeat original provider-MD5/local-SHA256 verification.
31: Require explicit time, current-sign, unit and exact column declarations.
32: Audit monotonic per-UID clocks and recording gaps without interpolation.
33: Integrate battery terminal Wh/Ah across ONLY measured adjacent samples.

Never reuse these DJI M300 observations as exact 60 kg hexacopter evidence.
Original files are never edited, and source origin/instrument accuracy are
not authenticated by hash matching or operator metadata.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import re
from collections.abc import Mapping

from physics.validation.zenodo_original_csv_schema import inspect_downloaded_m300_csv
from physics.validation.zenodo_flight_candidate import DOI, MAX_ORIGINAL_SIZE, ORIGINAL_CSV_DELIMITER

_MAPPING_KEYS = {
    "uid_column", "timestamp_column", "timestamp_unit", "voltage_column",
    "voltage_unit", "current_column", "current_unit", "discharge_current_sign",
    "state_column", "maximum_accepted_sample_gap_s", "upper_voltage_v",
    "upper_discharge_current_a", "unit_source_document_reference",
}
_TIME_SCALE = {
    "elapsed_s": Decimal("1"), "elapsed_ms": Decimal("0.001"),
    "unix_s": Decimal("1"), "unix_ms": Decimal("0.001"),
}
_NUMBER = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,3})?$")
_UID = re.compile(r"^[^\x00\r\n\t]{1,128}$")
_MAX_UIDS = 2000


def _decimal(value: object, label: str) -> Decimal:
    if not isinstance(value, (str, int, float, Decimal)) or isinstance(value, bool):
        raise ValueError(f"{label}: explicit finite decimal required")
    raw = str(value).strip()
    if len(raw) > 80 or not _NUMBER.fullmatch(raw):
        raise ValueError(f"{label}: nonnumeric, nonfinite or excessive exponent")
    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{label}: invalid numeric value") from exc
    if not parsed.is_finite() or (parsed != 0 and not -18 <= parsed.adjusted() <= 18):
        raise ValueError(f"{label}: unsupported numerical magnitude")
    return parsed


def _bounded(value: object, label: str, *, maximum: str, positive: bool = False) -> Decimal:
    v = _decimal(value, label)
    if v < 0 or (positive and v == 0) or v > Decimal(maximum):
        raise ValueError(f"{label}: out of permitted positive engineering range")
    return v


def validate_explicit_m300_mapping(mapping: Mapping, actual_header: list[str]) -> dict:
    """M26.31: no guessed or implicit sensor unit or clock semantics."""
    if not isinstance(mapping, Mapping) or set(mapping) != _MAPPING_KEYS:
        raise ValueError("exact explicit instrument mapping fields required")
    if not isinstance(actual_header, list) or len(actual_header) != len(set(actual_header)):
        raise ValueError("exact original source header must be unambiguous")
    mandatory = (
        mapping["uid_column"], mapping["timestamp_column"],
        mapping["voltage_column"], mapping["current_column"],
    )
    if any(not isinstance(v, str) or v not in actual_header for v in mandatory):
        raise ValueError("mapped source column absent from actual original CSV header")
    if len(set(mandatory)) != 4:
        raise ValueError("UID, time, voltage and current must use four distinct source columns")
    state = mapping["state_column"]
    if state is not None and (
        not isinstance(state, str) or state not in actual_header or state in mandatory
    ):
        raise ValueError("state column must be null or a distinct actual original column")
    if mapping["timestamp_unit"] not in _TIME_SCALE:
        raise ValueError("timestamp unit is undocumented or unsupported")
    if mapping["voltage_unit"] != "V" or mapping["current_unit"] != "A":
        raise ValueError("only explicitly documented V/A battery columns are supported")
    if mapping["discharge_current_sign"] not in ("positive", "negative"):
        raise ValueError("discharge-current sign must be explicitly declared")
    document = mapping["unit_source_document_reference"]
    if not isinstance(document, str) or not 8 <= len(document.strip()) <= 500:
        raise ValueError("explicit instrument unit/time/current-sign reference required")
    gap = _bounded(mapping["maximum_accepted_sample_gap_s"], "sample time gap", maximum="3600", positive=True)
    voltage = _bounded(mapping["upper_voltage_v"], "maximum permitted voltage", maximum="1000", positive=True)
    current = _bounded(mapping["upper_discharge_current_a"], "maximum discharge current", maximum="5000", positive=True)
    return {
        "time_scale_s": _TIME_SCALE[mapping["timestamp_unit"]],
        "max_gap_s": gap, "voltage_cap_v": voltage, "current_cap_a": current,
        "current_multiplier": Decimal(-1) if mapping["discharge_current_sign"] == "negative" else Decimal(1),
        "unit_source_document_reference": document.strip(),
        "mapping_sha256": sha256(json.dumps(
            dict(mapping), sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest(),
    }


def analyse_m300_original_energy(path: str | Path, acquisition_receipt: Mapping, *,
                                 mapping: Mapping) -> dict:
    """M26.30/32/33: compute auditable battery-terminal energy per source UID.

    A maximum-gap violation is never bridged by interpolation; only measured,
    time-adjacent intervals within the operator-declared limit are integrated.
    Units, current sign and historical physical provenance are NOT verified.
    """
    inspection = inspect_downloaded_m300_csv(path, acquisition_receipt)
    src = Path(path)
    if src.stat().st_size > MAX_ORIGINAL_SIZE:
        raise ValueError("original source exceeds bounded size")
    original_bytes = src.read_bytes()
    if sha256(original_bytes).hexdigest() != inspection["computed_original_sha256"]:
        raise ValueError("original source changed following provider checksum scan")
    text = original_bytes.decode("utf-8", "strict")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=ORIGINAL_CSV_DELIMITER, strict=True)
    header = next(reader)
    config = validate_explicit_m300_mapping(mapping, header)
    col = {name: header.index(mapping[name]) for name in (
        "uid_column", "timestamp_column", "voltage_column", "current_column",
    )}
    state_col = header.index(mapping["state_column"]) if mapping["state_column"] is not None else None
    sessions: dict[str, dict] = {}
    line_count = 0
    with localcontext() as context:
        context.prec = 40
        for row in reader:
            line_count += 1
            if len(row) != len(header):
                raise ValueError("inconsistent original CSV row width")
            uid = row[col["uid_column"]].strip()
            if not _UID.fullmatch(uid) or not uid.strip():
                raise ValueError("missing or unsafe original flight UID")
            if uid not in sessions:
                if len(sessions) >= _MAX_UIDS:
                    raise ValueError("too many distinct original flight UIDs")
                sessions[uid] = {
                    "samples": 0, "first_time": None, "last_time": None,
                    "last_voltage": None, "last_current": None,
                    "intervals": 0, "gap_count": 0, "max_gap": Decimal(0),
                    "integrated_seconds": Decimal(0), "energy_wh": Decimal(0),
                    "charge_ah": Decimal(0), "state_counts": {},
                }
            session = sessions[uid]
            raw_t = _decimal(row[col["timestamp_column"]], "original timestamp")
            t = raw_t * config["time_scale_s"]
            v = _bounded(row[col["voltage_column"]], "battery voltage", maximum=str(config["voltage_cap_v"]), positive=True)
            i = _decimal(row[col["current_column"]], "battery current") * config["current_multiplier"]
            if i < 0 or i > config["current_cap_a"]:
                raise ValueError("battery current inconsistent with declared discharge sign or bound")
            if state_col is not None:
                state = row[state_col].strip()
                if not state or len(state) > 128:
                    raise ValueError("missing or oversized original source flight-state annotation")
                session["state_counts"][state] = session["state_counts"].get(state, 0) + 1
            if session["last_time"] is not None:
                dt = t - session["last_time"]
                if dt <= 0:
                    raise ValueError("original timestamps must strictly increase within each flight UID")
                session["max_gap"] = max(session["max_gap"], dt)
                if dt > config["max_gap_s"]:
                    session["gap_count"] += 1
                else:
                    session["intervals"] += 1
                    session["integrated_seconds"] += dt
                    session["energy_wh"] += (
                        (session["last_voltage"] * session["last_current"] + v * i)
                        * dt / Decimal(7200)
                    )
                    session["charge_ah"] += (session["last_current"] + i) * dt / Decimal(7200)
            else:
                session["first_time"] = t
            session["last_time"] = t
            session["last_voltage"] = v
            session["last_current"] = i
            session["samples"] += 1
    if line_count != inspection["original_csv_record_count"]:
        raise ValueError("original file changed or record count disagrees with source scan")
    recordings = []
    for uid in sorted(sessions):
        row = sessions[uid]
        elapsed = row["last_time"] - row["first_time"]
        covered = row["intervals"] >= 4 and row["gap_count"] == 0
        charge = float(row["charge_ah"])
        wh = float(row["energy_wh"])
        if not math.isfinite(charge) or not math.isfinite(wh):
            raise ValueError("integrated source values exceeded supported output magnitude")
        recordings.append({
            "uid": uid,
            "sample_count": row["samples"],
            "observed_elapsed_s": float(elapsed),
            "integrated_measured_interval_s": float(row["integrated_seconds"]),
            "usable_adjacent_intervals": row["intervals"],
            "unbridged_gaps": row["gap_count"],
            "maximum_original_gap_s": float(row["max_gap"]),
            "battery_terminal_discharge_wh_over_observed_coverage": wh,
            "battery_terminal_discharge_ah_over_observed_coverage": charge,
            "original_state_label_counts_not_interpreted": dict(sorted(row["state_counts"].items())),
            "complete_covered_recording_for_numeric_holdout": covered,
        })
    return {
        "status": "PROVIDER_HASH_VERIFIED_M300_ENERGY_ACCOUNTING_NOT_FULL_VEHICLE_VALIDATION",
        "source_doi": DOI,
        "original_source_sha256": inspection["computed_original_sha256"],
        "original_csv_record_count": line_count,
        "original_header_inspected": header,
        "source_mapping_sha256": config["mapping_sha256"],
        "source_mapping_operator_declared": dict(mapping),
        "flight_uid_count": len(recordings),
        "recordings": recordings,
        "original_bytes_modified": False,
        "missing_intervals_interpolated": False,
        "battery_measurement_units_or_discharge_sign_independently_verified": False,
        "source_instrument_accuracy_and_clock_verified": False,
        "exact_aeroforge_60kg_hexacopter_hardware_matched": False,
        "flight_release_authorized": False,
    }
