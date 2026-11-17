"""M26.32: explicit timestamp-column integrity and contiguous-segment preflight.

A human must identify the original timestamp header and its actual unit.
Large gaps break segments; duplicate/backward timestamps invalidate the claim.
No clock sync, flight IDs or physical independence are inferred.
"""
from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path

from physics.validation.zenodo_original_quality import audit_original_m300_field_quality
from physics.validation.zenodo_flight_candidate import MAX_ORIGINAL_SIZE

_UNITS = {"s": Decimal("1"), "ms": Decimal(".001"),
          "us": Decimal(".000001"), "ns": Decimal(".000000001")}

def audit_original_m300_time_segments(
    path: Path | str, receipt: Mapping, *,
    original_time_column: str, original_time_unit: str,
    declared_max_sample_gap_s: float, minimum_contiguous_rows: int = 5,
) -> dict:
    evidence = audit_original_m300_field_quality(path, receipt)
    columns = [c["original_label"] for c in evidence["columns"]]
    if not isinstance(original_time_column, str) or original_time_column not in columns:
        raise ValueError("exact observed timestamp header required")
    if original_time_unit not in _UNITS:
        raise ValueError("explicit original timestamp units required")
    if (type(declared_max_sample_gap_s) not in (int, float)
            or not math.isfinite(declared_max_sample_gap_s)
            or not 0 < declared_max_sample_gap_s <= 3600):
        raise ValueError("positive finite declared sampling-gap bound required")
    if type(minimum_contiguous_rows) is not int or not 5 <= minimum_contiguous_rows <= 50000:
        raise ValueError("minimum contiguous original rows must be 5..50000")
    data = Path(path).read_bytes()
    if len(data) > MAX_ORIGINAL_SIZE:
        raise ValueError("source size changed")
    rows = csv.reader(io.StringIO(data.decode("utf-8"), newline=""), strict=True)
    headers = next(rows)
    ti = headers.index(original_time_column)
    previous = None
    blocks = []
    start = last = None
    count = 0
    max_gap = Decimal("0")
    threshold = Decimal(str(declared_max_sample_gap_s))
    for row in rows:
        try:
            v = Decimal(row[ti].strip()) * _UNITS[original_time_unit]
        except (InvalidOperation, IndexError, TypeError) as exc:
            raise ValueError("missing or nonnumeric original timestamp") from exc
        if not v.is_finite() or abs(v) > Decimal("1e18"):
            raise ValueError("original timestamp outside finite supported magnitude")
        if previous is not None:
            gap = v - previous
            if gap <= 0:
                raise ValueError("original timestamps are duplicate or nonmonotone")
            max_gap = max(max_gap, gap)
            if gap > threshold:
                blocks.append({"start_s": str(start), "end_s": str(last), "rows": count})
                start, count = v, 0
        if count == 0:
            start = v
        count += 1
        last = v
        previous = v
    blocks.append({"start_s": str(start), "end_s": str(last), "rows": count})
    usable = sum(int(block["rows"] >= minimum_contiguous_rows) for block in blocks)
    return {
        "status": "CONTIGUOUS_TIMESTAMP_BLOCKS_REPORTED_NOT_DISTINCT_FLIGHTS",
        "source_sha256": evidence["source_sha256"],
        "original_time_column": original_time_column,
        "operator_declared_time_unit": original_time_unit,
        "operator_declared_max_sample_gap_s": declared_max_sample_gap_s,
        "total_original_rows": evidence["records_scanned_without_modification"],
        "contiguous_blocks": blocks,
        "blocks_with_sufficient_rows": usable,
        "maximum_sample_gap_s": str(max_gap),
        "distinct_flights_or_original_clock_authenticated": False,
        "independent_holdout_blinding_authenticated": False,
        "flight_validation_authorized": False,
    }
