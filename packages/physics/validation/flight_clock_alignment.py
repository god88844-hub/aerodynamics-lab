"""M26.6: bounded two-channel, same-flight original-sample time alignment.

Uses exact on-disk CSV bytes and declared clock shifts/hard timing errors.
Never interpolates, uses one sample twice, assumes different flight clocks
compatible, or claims an externally calibrated synchronization system.
"""
from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping
from pathlib import Path
from hashlib import sha256

from physics.validation.flight_channel_csv import (
    _CHANNEL_UNITS, _MAX_CSV_BYTES, audit_original_flight_channel_csv,
)
from physics.validation.native_flight_archive import _file
from physics.validation.source_completeness import audit_source_completeness


def _finite(value: object, name: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: finite real value required")
    try:
        v = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name}: finite real value required") from exc
    if not math.isfinite(v) or (nonnegative and v < 0):
        raise ValueError(f"{name}: finite real value required")
    return v


def _read_times(root: str | Path, record: Mapping, channel: str) -> list[float]:
    path = _file(Path(root), record["relative_path"])
    if path.stat().st_size > _MAX_CSV_BYTES:
        raise ValueError("original source exceeds bounded synchronization reader size")
    data = path.read_bytes()
    if len(data) != record["original_byte_count"] or sha256(data).hexdigest() != record["original_sha256"]:
        raise ValueError("original file changed since source manifest; SHA-256 mismatch")
    try:
        text = data.decode("utf-8", "strict")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        if next(reader, None) != ["t_s", channel]:
            raise ValueError("original CSV exact single-channel schema required")
        times = []
        for row in reader:
            if len(row) != 2:
                raise ValueError("original sample has missing/extra columns")
            t, y = map(float, row)
            if not math.isfinite(t) or not math.isfinite(y):
                raise ValueError("nonfinite original sample")
            if times and t <= times[-1]:
                raise ValueError("original times must strictly increase")
            times.append(t)
        if not 5 <= len(times) <= 50000:
            raise ValueError("source must have 5..50000 original samples")
        return times
    except (UnicodeError, csv.Error, OverflowError) as exc:
        raise ValueError("original source CSV cannot be read without changing bytes") from exc


def audit_same_flight_clock_alignment(
    root: str | Path,
    manifest: Mapping,
    *,
    source_a: Mapping,
    source_b: Mapping,
    maximum_joint_time_difference_s: float,
    minimum_unique_pairs: int = 5,
) -> dict:
    """Match original samples if worst possible time separation is within limit.

    Entries: relative_path, channel, offset_to_shared_clock_s,
    offset_hard_error_s, maximum_sample_gap_s. Offsets and errors are
    user-declared rather than externally calibrated. Matching is a one-to-one
    monotonic greedy pairing and is NOT a general time-series resampler.
    """
    required = {
        "relative_path", "channel", "offset_to_shared_clock_s",
        "offset_hard_error_s", "maximum_sample_gap_s",
    }
    for entry in (source_a, source_b):
        if not isinstance(entry, Mapping) or set(entry) != required:
            raise ValueError("each source requires exact clock, channel and original path declarations")
        if entry["channel"] not in _CHANNEL_UNITS:
            raise ValueError("unsupported original signal channel")
    if source_a["relative_path"] == source_b["relative_path"]:
        raise ValueError("independent sensor files required; cannot pair file to itself")
    max_difference = _finite(maximum_joint_time_difference_s, "maximum_joint_time_difference_s", nonnegative=True)
    if not 0 < max_difference <= 60:
        raise ValueError("positive maximum joint time difference <= 60 seconds required")
    if type(minimum_unique_pairs) is not int or not 5 <= minimum_unique_pairs <= 50000:
        raise ValueError("minimum_unique_pairs must be integer 5..50000")
    archive = audit_source_completeness(root, manifest)
    by_path = {row["relative_path"]: row for row in manifest["files"]}
    prepared = []
    for entry in (source_a, source_b):
        path = entry["relative_path"]
        if not isinstance(path, str) or path not in by_path:
            raise ValueError("source path must be present exactly once in original archive")
        source = by_path[path]
        if (source["clock_reference"] is None or source["calibration_reference"] is None
                or list(source["declared_channels"]) != [entry["channel"]]):
            raise ValueError("explicit clock, calibration and exact single-channel metadata required")
        offset = _finite(entry["offset_to_shared_clock_s"], "offset_to_shared_clock_s")
        uncertainty = _finite(entry["offset_hard_error_s"], "offset_hard_error_s", nonnegative=True)
        check = audit_original_flight_channel_csv(
            root, manifest, relative_path=path,
            channels_with_units={entry["channel"]: _CHANNEL_UNITS[entry["channel"]]},
            maximum_declared_sample_gap_s=entry["maximum_sample_gap_s"],
        )
        if not check["within_operator_declared_time_gap"]:
            raise ValueError("original timestamp gaps exceed declared maximum")
        ts = _read_times(root, source, entry["channel"])
        shifted = [t + offset for t in ts]
        if not all(math.isfinite(t) for t in shifted):
            raise ValueError("clock-shifted time arithmetic overflow")
        prepared.append((source, check, shifted, offset, uncertainty))
    a, b = prepared
    if a[0]["flight_id"] != b[0]["flight_id"]:
        raise ValueError("cross-flight sensor pairing cannot establish same-flight synchronization")
    i = j = 0
    pairs = []
    omitted_a = omitted_b = 0
    combined_hard = a[4] + b[4]
    if not math.isfinite(combined_hard):
        raise ValueError("combined hard clock uncertainty overflow")
    if combined_hard > max_difference:
        # The worst case uncertainty alone is larger than tolerance.
        return {
            "status": "SENSOR_CLOCK_ALIGNMENT_NOT_ESTABLISHED",
            "flight_id": a[0]["flight_id"],
            "matched_original_pairs": 0,
            "maximum_worst_case_time_difference_s": None,
            "minimum_pairs_met": False,
            "clock_hard_uncertainty_sum_s": combined_hard,
            "source_sha256_pair": sorted([a[0]["original_sha256"], b[0]["original_sha256"]]),
            "source_clock_hard_bounds_externally_authenticated": False,
            "physical_measurements_authenticated": False,
            "flight_release_authorized": False,
        }
    while i < len(a[2]) and j < len(b[2]):
        ta, tb = a[2][i], b[2][j]
        worst = abs(ta - tb) + combined_hard
        if math.isfinite(worst) and worst <= max_difference:
            pairs.append((i, j, worst))
            i += 1
            j += 1
        elif ta < tb:
            i += 1
            omitted_a += 1
        else:
            j += 1
            omitted_b += 1
    passed = len(pairs) >= minimum_unique_pairs
    return {
        "status": ("DECLARED_CLOCK_BOUND_AND_UNIQUE_PAIR_SCREEN_PASSED_UNAUTHENTICATED"
                   if passed else "SENSOR_CLOCK_ALIGNMENT_NOT_ESTABLISHED"),
        "flight_id": a[0]["flight_id"],
        "source_a_path": a[0]["relative_path"],
        "source_b_path": b[0]["relative_path"],
        "source_sha256_pair": sorted([a[0]["original_sha256"], b[0]["original_sha256"]]),
        "channel_a": source_a["channel"],
        "channel_b": source_b["channel"],
        "matched_original_pairs": len(pairs),
        "minimum_pairs_met": passed,
        "discarded_unpaired_a_at_search": omitted_a,
        "discarded_unpaired_b_at_search": omitted_b,
        "sample_indices_are_unique_and_monotonic": True,
        "maximum_worst_case_time_difference_s": max((p[2] for p in pairs), default=None),
        "clock_hard_uncertainty_sum_s": combined_hard,
        "source_clock_hard_bounds_externally_authenticated": False,
        "actual_sensor_sync_measured_independently": False,
        "physical_measurements_authenticated": False,
        "flight_release_authorized": False,
    }
