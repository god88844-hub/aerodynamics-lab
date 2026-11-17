"""M26.28: inspect downloaded source CSV *as published*, with no guessed units.

The M300 Zenodo file is about 15.6 MB, larger than the legacy M26.17
8-MB vendor CSV reader. This dedicated inspector supports up to 25 MB,
validates the provider MD5 and local SHA256, and records actual columns.
It never rewrites, interpolates, auto-converts or asserts source authenticity.
"""
from __future__ import annotations

import csv
import io
from hashlib import md5, sha256
from pathlib import Path
from collections.abc import Mapping

from physics.validation.zenodo_flight_candidate import EXPECTED_MD5, MAX_ORIGINAL_SIZE, ORIGINAL_CSV_DELIMITER


def inspect_downloaded_m300_csv(path: Path | str, acquisition: Mapping) -> dict:
    if not isinstance(acquisition, Mapping) or not acquisition.get("provider_md5_matched"):
        raise ValueError("matching provider acquisition receipt required")
    src = Path(path)
    if src.is_symlink() or not src.is_file() or src.suffix.lower() != ".csv":
        raise ValueError("downloaded original must be a regular existing CSV")
    actual_size = src.stat().st_size
    if not 0 < actual_size <= MAX_ORIGINAL_SIZE:
        raise ValueError("downloaded file outside 25MB original size cap")
    raw = src.read_bytes()
    if (len(raw) != acquisition.get("actual_source_bytes")
            or md5(raw).hexdigest() != EXPECTED_MD5
            or sha256(raw).hexdigest() != acquisition.get("computed_original_sha256")):
        raise ValueError("downloaded original has changed or fails provider MD5/SHA-256 audit")
    try:
        decoded = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ValueError("original CSV is not UTF-8; audited source-specific adapter needed") from exc
    if decoded.startswith("\ufeff") or "\x00" in decoded:
        raise ValueError("original CSV contains BOM/NUL; refuse implicit conversion")
    try:
        rows = csv.reader(io.StringIO(decoded, newline=""), delimiter=ORIGINAL_CSV_DELIMITER, strict=True)
        header = next(rows, None)
        if (not isinstance(header, list) or not 2 <= len(header) <= 128
                or any(not field.strip() or len(field) > 256 for field in header)
                or len(set(header)) != len(header)):
            raise ValueError("actual original CSV header missing or ambiguous")
        line_count = incomplete_count = 0
        first_row = last_row = None
        for row in rows:
            if len(row) != len(header):
                raise ValueError("original CSV row has inconsistent column count")
            line_count += 1
            if first_row is None:
                first_row = row
            last_row = row
            incomplete_count += int(any(not cell.strip() for cell in row))
            if line_count > 1_000_000:
                raise ValueError("original source exceeds one million CSV records")
    except csv.Error as exc:
        raise ValueError("original CSV malformed quoting") from exc
    if line_count < 5:
        raise ValueError("source has fewer than five original data rows")
    return {
        "status": "PUBLISHED_ORIGINAL_CSV_COLUMNS_INVENTORIED_NO_INSTRUMENT_AUTHENTICATION",
        "source_doi": acquisition["source_doi"],
        "provider_original_md5": EXPECTED_MD5,
        "computed_original_sha256": sha256(raw).hexdigest(),
        "original_bytes": len(raw),
        "actual_original_column_names": header,
        "original_csv_record_count": line_count,
        "rows_with_one_or_more_blank_cells": incomplete_count,
        "missing_cells_filled_or_dropped": False,
        "source_original_bytes_modified": False,
        "all_column_units_known": False,
        "actual_instrument_clock_calibration_verified": False,
        "independent_aircraft_hardware_match_verified": False,
        "flight_prediction_accuracy_validated": False,
    }
