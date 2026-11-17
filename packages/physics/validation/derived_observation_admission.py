"""M26.20: admit traceable DERIVED observations, never pass them off as originals.

Replays the source-specific conversion against original source bytes on disk.
No source, clock, instrument or physical validation authority is inferred.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from collections.abc import Mapping

from physics.validation.flight_clock_alignment import _finite
from physics.validation.flight_derived_csv_replay import replay_derived_flight_csv
from physics.validation.frozen_flight_comparison import _csv_rows
from physics.validation.flight_channel_csv import _CHANNEL_UNITS


def admit_derived_observation(
    original_root: Path | str, source_manifest: Mapping, *,
    derived_csv_path: Path | str,
    provenance_json_path: Path | str,
    output_channel: str,
    maximum_declared_sample_gap_s: float,
) -> dict:
    """Rehash and replay a derived file; report sample grid and missing science."""
    if not isinstance(output_channel, str) or output_channel not in _CHANNEL_UNITS:
        raise ValueError("derived observation requires a supported engineering channel")
    gap_limit = _finite(
        maximum_declared_sample_gap_s, "maximum_declared_sample_gap_s",
        nonnegative=True,
    )
    if not 0 < gap_limit <= 3600:
        raise ValueError("maximum sample time gap must be >0 and <=3600 seconds")
    replay = replay_derived_flight_csv(
        original_root, source_manifest,
        derived_csv_path=derived_csv_path,
        provenance_json_path=provenance_json_path,
    )
    from json import loads
    # This is safe to read after the replay: the strict sidecar was independently
    # reconstructed; its bytes are not treated as original instrument data.
    sidecar = loads(Path(provenance_json_path).read_text(encoding="utf-8"))
    if sidecar["output_channel"] != output_channel:
        raise ValueError("derived output channel differs from requested channel")
    source = [
        f for f in source_manifest["files"]
        if f["relative_path"] == sidecar["original_source_relative_path"]
    ]
    if len(source) != 1 or source[0]["original_sha256"] != replay["original_source_sha256"]:
        raise ValueError("derived original source hash or manifest identity mismatch")
    if source[0]["calibration_reference"] is None or source[0]["clock_reference"] is None:
        raise ValueError("declared original instrument calibration and clock references required")
    derived = Path(derived_csv_path).read_bytes()
    if sha256(derived).hexdigest() != replay["derived_csv_sha256"]:
        raise ValueError("derived CSV bytes changed following original-source replay")
    rows = _csv_rows(derived, ["t_s", output_channel], "derived observed (not original)")
    widest = max(b[0] - a[0] for a, b in zip(rows, rows[1:]))
    passed_gap = widest <= gap_limit
    return {
        "status": (
            "REPLAYED_DERIVED_CHANNEL_GRID_SCREENED_NOT_AUTHENTICATED"
            if passed_gap else "INCONCLUSIVE_DERIVED_SOURCE_TIME_GAPS"
        ),
        "original_source_relative_path": source[0]["relative_path"],
        "original_source_sha256": source[0]["original_sha256"],
        "flight_id_operator_declared": source[0]["flight_id"],
        "derived_csv_sha256": replay["derived_csv_sha256"],
        "conversion_spec_sha256": replay["conversion_spec_sha256"],
        "channel": output_channel, "unit": _CHANNEL_UNITS[output_channel],
        "sample_count": len(rows), "first_time_s": rows[0][0],
        "last_time_s": rows[-1][0], "maximum_observed_gap_s": widest,
        "operator_sampling_gap_requirement_met": passed_gap,
        "original_source_is_derived": True,
        "real_sensor_clock_or_calibration_authenticated": False,
        "publisher_original_custody_authenticated": False,
        "physical_measurement_accuracy_established": False,
        "flight_release_authorized": False,
    }
