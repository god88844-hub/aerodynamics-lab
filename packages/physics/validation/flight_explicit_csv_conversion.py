"""M26.18: explicit, deterministic vendor CSV -> one AeroForge channel.

A DERIVED CSV is never original data. Conversion is from verified original
local bytes, declared source column and exact source units, using an allowlist.
Unknown formats/units, missing rows and invented calibration are not accepted.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation, localcontext
from hashlib import sha256
import io
import json
from collections.abc import Mapping
from pathlib import Path
import re

from physics.validation.flight_vendor_csv_inspector import read_pinned_vendor_csv

_SPEC = {
    "source_relative_path", "time_column", "time_unit",
    "channel_column", "output_channel", "channel_unit",
    "mapping_source_reference",
}
_ALLOWED = {
    "rotor_rpm": {"rpm", "Hz"},
    "pressure_pa": {"Pa", "kPa", "bar", "psi"},
    "temperature_c": {"degC", "K", "degF"},
    "arm_force_n": {"N", "kN", "lbf"},
    "acceleration_m_s2": {"m/s2", "g0"},
    "strain_microstrain": {"microstrain", "strain"},
}
_TIME_UNITS = {"s": Decimal(1), "ms": Decimal("0.001"),
               "us": Decimal("0.000001"), "ns": Decimal("0.000000001")}
_NUMBER = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,3})?$")


def _number(raw: str, label: str) -> Decimal:
    if len(raw) > 80 or not _NUMBER.fullmatch(raw.strip()):
        raise ValueError(f"{label}: invalid or nonfinite source decimal")
    try:
        result = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ValueError(f"{label}: invalid source decimal") from exc
    if not result.is_finite() or (result != 0 and not -18 <= result.adjusted() <= 18):
        raise ValueError(f"{label}: source decimal outside permitted finite magnitude")
    return result


def _format_decimal(value: Decimal, label: str) -> str:
    if not value.is_finite() or (value != 0 and not -18 <= value.adjusted() <= 15):
        raise ValueError(f"{label}: converted output magnitude or precision unsupported")
    return "0" if value == 0 else format(value.normalize(), "f")


def _convert_channel(x: Decimal, channel: str, source_unit: str) -> Decimal:
    if channel == "rotor_rpm":
        return x * (Decimal(60) if source_unit == "Hz" else Decimal(1))
    if channel == "pressure_pa":
        return x * {"Pa": Decimal(1), "kPa": Decimal(1000),
                    "bar": Decimal(100000), "psi": Decimal("6894.757293168")}[source_unit]
    if channel == "temperature_c":
        return ((x - 32) * 5 / 9 if source_unit == "degF"
                else x - Decimal("273.15") if source_unit == "K" else x)
    if channel == "arm_force_n":
        return x * {"N": Decimal(1), "kN": Decimal(1000),
                    "lbf": Decimal("4.4482216152605")}[source_unit]
    if channel == "acceleration_m_s2":
        return x * (Decimal("9.80665") if source_unit == "g0" else Decimal(1))
    if channel == "strain_microstrain":
        return x * (Decimal(1000000) if source_unit == "strain" else Decimal(1))
    raise ValueError("unsupported converted channel")


def _validate_spec(mapping: Mapping) -> None:
    if not isinstance(mapping, Mapping) or set(mapping) != _SPEC:
        raise ValueError("exact source column/unit transformation specification required")
    for name in _SPEC:
        value = mapping[name]
        if not isinstance(value, str) or not value.strip() or len(value) > 300:
            raise ValueError(f"{name}: nonempty explicit source mapping required")
    if mapping["time_unit"] not in _TIME_UNITS:
        raise ValueError("unsupported time unit; only s, ms, us, ns permitted")
    channel = mapping["output_channel"]
    if channel not in _ALLOWED or mapping["channel_unit"] not in _ALLOWED[channel]:
        raise ValueError("unknown or incompatible source channel/unit; no guessed conversions")
    if mapping["time_column"] == mapping["channel_column"]:
        raise ValueError("time and measured channel must be distinct original columns")


def derive_original_vendor_csv_bytes(root, manifest, *, mapping: Mapping):
    """Replayable bytes/metadata; never changes original files or writes output."""
    _validate_spec(mapping)
    original, header, rows, archive = read_pinned_vendor_csv(
        root, manifest, mapping["source_relative_path"]
    )
    if mapping["time_column"] not in header or mapping["channel_column"] not in header:
        raise ValueError("mapping column names must match exact original CSV headers")
    ti, yi = header.index(mapping["time_column"]), header.index(mapping["channel_column"])
    result = io.StringIO(newline="")
    writer = csv.writer(result, lineterminator="\n")
    writer.writerow(["t_s", mapping["output_channel"]])
    previous = None
    with localcontext() as ctx:
        ctx.prec = 40
        for row in rows:
            t = _number(row[ti], "original time") * _TIME_UNITS[mapping["time_unit"]]
            y = _convert_channel(_number(row[yi], "original measured value"),
                                 mapping["output_channel"], mapping["channel_unit"])
            if previous is not None and t <= previous:
                raise ValueError("converted original timestamps must strictly increase")
            previous = t
            writer.writerow([_format_decimal(t, "original time"),
                             _format_decimal(y, "measured value")])
    encoded = result.getvalue().encode("utf-8")
    spec_sha = sha256(json.dumps(
        dict(mapping), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")).hexdigest()
    provenance = {
        "schema_version": "1.0",
        "status": "DERIVED_NUMERIC_CSV_TRANSFORM_NOT_ORIGINAL_EVIDENCE",
        "original_source_relative_path": mapping["source_relative_path"],
        "original_sha256": original["original_sha256"],
        "original_byte_count": original["original_byte_count"],
        "archive_inventory_sha256": archive["canonical_file_inventory_sha256"],
        "source_flight_id_operator_declared": original["flight_id"],
        "transformation_spec": dict(mapping),
        "transformation_spec_sha256": spec_sha,
        "derived_csv_sha256": sha256(encoded).hexdigest(),
        "derived_csv_byte_count": len(encoded),
        "derived_sample_count": len(rows),
        "output_channel": mapping["output_channel"],
        "unmapped_source_columns_not_interpreted": [c for c in header if c not in
                                                      (mapping["time_column"], mapping["channel_column"])],
        "source_calibration_reference_operator_reported": original["calibration_reference"],
        "source_clock_reference_operator_reported": original["clock_reference"],
        "conversion_constants_are_software_assumptions": True,
        "raw_file_origin_or_license_independently_authenticated": False,
        "source_instrument_units_and_calibration_independently_verified": False,
        "physically_validated_simulation": False,
        "flight_release_authorized": False,
    }
    return encoded, provenance


def write_derived_vendor_csv(
    root, manifest, *, mapping: Mapping,
    derived_csv_path: str | Path,
    provenance_json_path: str | Path,
) -> dict:
    """Write outside originals, exclusively; no overwrite of any existing file."""
    base = Path(root).resolve(strict=True)
    out = Path(derived_csv_path)
    meta = Path(provenance_json_path)
    out_resolved, meta_resolved = out.resolve(strict=False), meta.resolve(strict=False)
    if (out_resolved == meta_resolved or out_resolved.is_relative_to(base)
            or meta_resolved.is_relative_to(base)):
        raise ValueError("derived output and provenance must be separate and outside original root")
    if (out.suffix.lower() != ".csv" or meta.suffix.lower() != ".json"
            or not out.parent.is_dir() or not meta.parent.is_dir()
            or out.is_symlink() or meta.is_symlink()
            or out.exists() or meta.exists()):
        raise ValueError("derived outputs must be new non-symlink CSV/JSON files")
    data, provenance = derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)
    # Never rename/rewrite original bytes; exclusive creation prevents overwrites.
    with out.open("xb") as f:
        f.write(data)
    with meta.open("x", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2, sort_keys=True, allow_nan=False)
        f.write("\n")
    return provenance
