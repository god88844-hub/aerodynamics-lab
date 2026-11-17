"""M26.38: source-linked explicit numeric channel probe; no invented units.

Only examines an observed original column under an operator-declared unit.
Does not change source files, discard blank samples or certify a sensor.
"""
from __future__ import annotations
import csv
import io
import math
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

from physics.validation.zenodo_flight_candidate import ORIGINAL_CSV_DELIMITER
from physics.validation.zenodo_original_quality import audit_original_m300_field_quality

_CHANNEL_UNITS = {
    "battery_voltage": {"V", "mV"},
    "battery_current": {"A", "mA"},
    "position": {"m"},
    "velocity": {"m/s"},
    "acceleration": {"m/s2"},
    "wind_speed": {"m/s"},
    "heading": {"deg", "rad"},
}
_MULTIPLIER = {"V": Decimal(1), "mV": Decimal(".001"),
               "A": Decimal(1), "mA": Decimal(".001"),
               "m": Decimal(1), "m/s": Decimal(1), "m/s2": Decimal(1),
               "deg": Decimal(1), "rad": Decimal(1)}

def inspect_declared_original_m300_channel(
    path: Path | str, receipt: Mapping, *,
    original_column: str, claimed_channel: str, claimed_original_unit: str,
    instrument_unit_document_reference: str,
) -> dict:
    audit = audit_original_m300_field_quality(path, receipt)
    columns = [x["original_label"] for x in audit["columns"]]
    if not isinstance(original_column, str) or original_column not in columns:
        raise ValueError("channel name must match an observed original CSV column")
    if claimed_channel not in _CHANNEL_UNITS or claimed_original_unit not in _CHANNEL_UNITS[claimed_channel]:
        raise ValueError("explicit supported channel and source unit are required")
    if (not isinstance(instrument_unit_document_reference, str) or
            not 8 <= len(instrument_unit_document_reference.strip()) <= 400):
        raise ValueError("traceable original instrument unit document reference required")
    index = columns.index(original_column)
    reader = csv.reader(
        io.StringIO(Path(path).read_bytes().decode("utf-8"), newline=""),
        delimiter=ORIGINAL_CSV_DELIMITER,
        strict=True,
    )
    next(reader)
    n = 0
    lo = hi = None
    with __import__("decimal").localcontext() as context:
        context.prec = 40
        for row in reader:
            raw = row[index].strip()
            if not raw:
                raise ValueError("missing values in selected original channel cannot be silently dropped")
            try:
                value = Decimal(raw) * _MULTIPLIER[claimed_original_unit]
            except InvalidOperation as exc:
                raise ValueError("nonnumeric original source channel value") from exc
            if not value.is_finite() or abs(value) > Decimal("1e18"):
                raise ValueError("source channel has nonfinite or unsupported magnitude")
            n += 1
            lo = value if lo is None else min(lo, value)
            hi = value if hi is None else max(hi, value)
    return {
        "status": "EXPLICIT_ORIGINAL_CHANNEL_NUMERICALLY_SCREENED_UNIT_UNAUTHENTICATED",
        "source_sha256": audit["source_sha256"],
        "original_column": original_column,
        "claimed_engineering_channel": claimed_channel,
        "claimed_original_unit": claimed_original_unit,
        "instrument_unit_document_reference_operator_claimed": instrument_unit_document_reference.strip(),
        "samples_checked": n,
        "minimum_in_declared_base_unit": str(lo),
        "maximum_in_declared_base_unit": str(hi),
        "missing_or_nonfinite_original_samples_accepted": False,
        "source_units_or_sensor_calibration_independently_authenticated": False,
        "battery_pack_and_aircraft_hardware_match_authenticated": False,
        "physical_validation_authorized": False,
    }
