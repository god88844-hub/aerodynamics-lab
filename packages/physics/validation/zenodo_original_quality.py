"""M26.31: byte-pinned original M300 column completeness and type profile.

This examines *actual* original CSV bytes only after provider-MD5/SHA256
verification; does not invent channel names, units or missing values.
"""
from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from hashlib import md5, sha256
from pathlib import Path
from physics.validation.zenodo_flight_candidate import EXPECTED_MD5, MAX_ORIGINAL_SIZE, DOI

def audit_original_m300_field_quality(path: Path | str, receipt: Mapping) -> dict:
    src = Path(path)
    if (not isinstance(receipt, Mapping) or receipt.get("source_doi") != DOI
            or not receipt.get("provider_md5_matched") or src.is_symlink()
            or not src.is_file() or src.suffix.lower() != ".csv"
            or not 0 < src.stat().st_size <= MAX_ORIGINAL_SIZE):
        raise ValueError("actual bounded provider-matched M300 original CSV required")
    raw = src.read_bytes()
    if (len(raw) != receipt.get("actual_source_bytes")
            or md5(raw).hexdigest() != EXPECTED_MD5
            or sha256(raw).hexdigest() != receipt.get("computed_original_sha256")):
        raise ValueError("actual original CSV bytes fail pinned provider checksum")
    try:
        text = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ValueError("unknown source encoding; no hidden conversion") from exc
    if text.startswith("\ufeff") or "\x00" in text:
        raise ValueError("BOM/NUL requires separately audited source adapter")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        columns = next(reader, None)
        if (not isinstance(columns, list) or not 2 <= len(columns) <= 128
                or len(set(columns)) != len(columns)
                or any(not c.strip() or len(c) > 256 for c in columns)):
            raise ValueError("invalid or ambiguous original header")
        missing = [0] * len(columns)
        count = 0
        for row in reader:
            if len(row) != len(columns):
                raise ValueError("original source CSV has variable column count")
            count += 1
            if count > 1_000_000:
                raise ValueError("source CSV exceeds one million rows")
            for index, value in enumerate(row):
                missing[index] += int(not value.strip())
    except csv.Error as exc:
        raise ValueError("malformed source CSV") from exc
    if count < 5:
        raise ValueError("at least five complete-structure source records required")
    return {
        "status": "ORIGINAL_BYTE_PINNED_COLUMN_MISSINGNESS_SCREEN_NOT_CALIBRATION",
        "source_doi": DOI,
        "source_sha256": sha256(raw).hexdigest(),
        "original_bytes": len(raw),
        "records_scanned_without_modification": count,
        "columns": [
            {"original_label": key, "blank_count": blank,
             "nonblank_count": count - blank,
             "blank_fraction": blank / count}
            for key, blank in zip(columns, missing)
        ],
        "has_missing_cells": any(missing),
        "all_units_or_timebases_known": False,
        "source_instruments_calibrated_and_authenticated": False,
        "flight_validation_authorized": False,
    }
