"""M26.3: a constrained *actual CSV file* channel reader; never transcribe native data.

This does not claim any TU Braunschweig original source uses this exact CSV
header. TDMS/MAT/HDF5/ZIP and unknown headers require a separate audited
source-specific adapter; never convert unknown binary into fictitious values.
"""
from __future__ import annotations

import csv
import io
import math
from hashlib import sha256
from collections.abc import Mapping
from pathlib import Path

from physics.validation.native_flight_archive import (
    _file, _id, audit_native_flight_archive,
)

# These are explicitly supported output channel schemas, NOT inferred units.
_CHANNEL_UNITS = {
    "rotor_rpm": "rpm", "pressure_pa": "Pa",
    "temperature_c": "degC", "arm_force_n": "N",
    "acceleration_m_s2": "m/s2",
    "strain_microstrain": "microstrain",
}
_MAX_CSV_BYTES = 8_000_000
_MAX_SAMPLES = 50000


def audit_original_flight_channel_csv(
    root: str | Path, manifest: Mapping, *,
    relative_path: str,
    channels_with_units: Mapping[str, str],
    maximum_declared_sample_gap_s: float,
) -> dict:
    """Consume only an original hashed CSV in an EXACT declared SI schema.

    The original source remains unmodified. Unknown original formats/units,
    absent channels or clock/calibration references never get interpolated.
    """
    if not isinstance(channels_with_units, Mapping) or not 1 <= len(channels_with_units) <= 6:
        raise ValueError("one to six explicitly named supported measured channels required")
    for ch, unit in channels_with_units.items():
        if ch not in _CHANNEL_UNITS or unit != _CHANNEL_UNITS[ch]:
            raise ValueError(f"unsupported or mismatched channel/unit declaration: {ch}")
    if type(maximum_declared_sample_gap_s) not in (int, float):
        raise ValueError("finite positive maximum_declared_sample_gap_s required")
    max_gap = float(maximum_declared_sample_gap_s)
    if not math.isfinite(max_gap) or max_gap <= 0 or max_gap > 3600:
        raise ValueError("finite positive maximum_declared_sample_gap_s in (0,3600] required")
    audit = audit_native_flight_archive(root, manifest)
    source = [r for r in manifest["files"] if r["relative_path"] == relative_path]
    if len(source) != 1 or not isinstance(relative_path, str) or not relative_path.lower().endswith(".csv"):
        raise ValueError("one specifically declared original CSV file path required")
    original = source[0]
    if list(original["declared_channels"]) != list(channels_with_units):
        raise ValueError("actual original channels differ from explicitly declared supported CSV columns")
    path = _file(Path(root), relative_path)
    if path.stat().st_size > _MAX_CSV_BYTES:
        raise ValueError("original CSV exceeds 8MB reader size cap")
    raw = path.read_bytes()
    # The file could have changed after the complete-archive preflight.
    # Never parse or summarize data from a second read without verifying
    # *those same* bytes against the frozen original source manifest.
    if len(raw) > _MAX_CSV_BYTES or len(raw) != original["original_byte_count"]:
        raise ValueError("original CSV bytes changed or exceeded reader cap")
    if sha256(raw).hexdigest() != original["original_sha256"]:
        raise ValueError("original CSV SHA-256 changed after archive verification")
    try:
        content = raw.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ValueError("original CSV is not valid unmodified UTF-8") from exc
    if content.startswith("\ufeff"):
        raise ValueError("original CSV BOM not supported; do not silently rewrite source")
    header = ["t_s", *channels_with_units]
    try:
        rows = csv.reader(io.StringIO(content, newline=""), strict=True)
        if next(rows, None) != header:
            raise ValueError("original CSV requires exact t_s and declared channel/unit column order")
        count, previous, start, gap_max = 0, None, None, 0.
        minmax = {ch: [math.inf, -math.inf] for ch in channels_with_units}
        for row in rows:
            if len(row) != len(header) or any(not cell.strip() for cell in row):
                raise ValueError("missing/extra original CSV field; no imputation")
            try:
                nums = [float(x) for x in row]
            except (ValueError, OverflowError) as exc:
                raise ValueError("original CSV contains nonnumeric sample") from exc
            if not all(math.isfinite(x) for x in nums):
                raise ValueError("original CSV contains nonfinite measured value")
            t = nums[0]
            if previous is not None:
                gap = t - previous
                if gap <= 0:
                    raise ValueError("original CSV times not strictly increasing")
                gap_max = max(gap_max, gap)
            else:
                start = t
            previous = t
            count += 1
            if count > _MAX_SAMPLES:
                raise ValueError("original CSV exceeds 50000 samples")
            for ch, value in zip(channels_with_units, nums[1:]):
                extrema = minmax[ch]
                extrema[0] = min(extrema[0], value)
                extrema[1] = max(extrema[1], value)
    except csv.Error as exc:
        raise ValueError("malformed original CSV quoting") from exc
    if count < 5:
        raise ValueError("at least five intact original samples required")
    acceptable_sampling = gap_max <= max_gap
    return {
        "status": ("OPERATOR_REPORTED_CSV_CHANNELS_PARSED_CLOCK_NOT_AUTHENTICATED"
                   if acceptable_sampling else "CSV_SOURCE_GAPS_EXCEED_DECLARED_SAMPLE_LIMIT"),
        "archive_id": audit["archive_id"],
        "flight_id": _id(original["flight_id"], "flight_id"),
        "relative_path": relative_path,
        "original_file_sha256_checked_against_operator_manifest": original["original_sha256"],
        "original_file_byte_count": len(raw),
        "original_csv_sample_count": count,
        "first_original_time_s": start,
        "last_original_time_s": previous,
        "maximum_observed_time_step_s": gap_max,
        "within_operator_declared_time_gap": acceptable_sampling,
        "channels_with_declared_units": dict(channels_with_units),
        "original_value_ranges": {k: v for k, v in minmax.items()},
        "calibration_reference_operator_supplied": original["calibration_reference"],
        "clock_reference_operator_supplied": original["clock_reference"],
        "source_rights_independently_verified": False,
        "source_clock_calibration_independently_verified": False,
        "physical_sensor_measurements_authenticated": False,
        "independent_physical_model_validation_established": False,
        "flight_release_authorized": False,
    }
