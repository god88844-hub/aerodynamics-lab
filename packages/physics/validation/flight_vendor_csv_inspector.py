"""M26.17: inspect a genuine *as obtained* vendor CSV without guessing channels.

All actual source bytes are pinned by the M26 original-source manifest. This
inspection doesn't invent units, calibration, clock offsets, or measurements.
"""
from __future__ import annotations

import csv
import io
from hashlib import sha256
from pathlib import Path

from physics.validation.native_flight_archive import _file
from physics.validation.source_completeness import audit_source_completeness

_MAX_BYTES = 8_000_000
_MAX_ROWS = 50_000


def read_pinned_vendor_csv(root, manifest, relative_path: str):
    """Return original decoded header and string rows only after archive audit."""
    whole = audit_source_completeness(root, manifest)
    rows = [f for f in manifest["files"] if f["relative_path"] == relative_path]
    if len(rows) != 1 or not isinstance(relative_path, str) or not relative_path.lower().endswith(".csv"):
        raise ValueError("exact one original manifest-listed CSV relative path required")
    original = rows[0]
    p = _file(Path(root), relative_path)
    if p.stat().st_size > _MAX_BYTES:
        raise ValueError("original vendor CSV exceeds reader size limit")
    raw = p.read_bytes()
    if len(raw) != original["original_byte_count"] or sha256(raw).hexdigest() != original["original_sha256"]:
        raise ValueError("original vendor CSV SHA-256 or size mismatch on second read")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ValueError("original vendor CSV must be UTF-8; no silent encoding conversion") from exc
    if text.startswith("\ufeff") or "\x00" in text:
        raise ValueError("original CSV BOM or NUL not supported without explicit source adapter")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        if not header or not 2 <= len(header) <= 32 or any(
            not col.strip() or len(col) > 128 or "\n" in col or "\r" in col for col in header
        ) or len(set(header)) != len(header):
            raise ValueError("vendor header must have 2..32 unique, nonblank exact labels")
        data = []
        for row in reader:
            if len(row) != len(header) or any(not x.strip() for x in row):
                raise ValueError("vendor original row contains missing/extra cells; no imputation")
            data.append(row)
            if len(data) > _MAX_ROWS:
                raise ValueError("original vendor source has more than 50000 rows")
    except csv.Error as exc:
        raise ValueError("malformed vendor CSV quoting") from exc
    if len(data) < 5:
        raise ValueError("at least five intact original vendor rows required")
    return original, header, data, whole


def inspect_original_vendor_csv(root, manifest, *, relative_path: str) -> dict:
    original, header, rows, audit = read_pinned_vendor_csv(root, manifest, relative_path)
    return {
        "status": "SOURCE_CSV_HEADER_INVENTORIED_NO_UNIT_OR_CLOCK_AUTHENTICATION",
        "original_relative_path": relative_path,
        "original_file_sha256": original["original_sha256"],
        "original_file_byte_count": original["original_byte_count"],
        "original_record_count": len(rows),
        "exact_original_column_labels": header,
        "declared_flight_id": original["flight_id"],
        "archive_inventory_sha256": audit["canonical_file_inventory_sha256"],
        "original_channel_units_verified": False,
        "instrument_clock_and_calibration_verified": False,
        "original_recorder_custody_authenticated": False,
        "physical_prediction_accuracy_established": False,
        "flight_release_authorized": False,
    }
