"""M26.4 full archive/flight-level availability without phantom physical evidence.

Rehashes the entire declared original archive, checks only genuinely
supported original CSV channels and counts distinct *declared* flight IDs.
Two CSV windows with one flight ID never count as independent flights.
All provenance, calibration, clock, rights and independence claims remain
self-reported; a green coverage matrix is NOT model validation.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from physics.validation.native_flight_archive import audit_native_flight_archive
from physics.validation.flight_channel_csv import (
    _CHANNEL_UNITS, audit_original_flight_channel_csv,
)

_KEYS = {"relative_path", "channels_with_units", "maximum_declared_sample_gap_s"}


def audit_original_flight_channel_coverage(
    root: Path | str, manifest: Mapping, *,
    required_channels: Sequence[str],
    original_csv_sources: Sequence[Mapping],
    minimum_distinct_flights_per_channel: int = 2,
) -> dict:
    """Report exact available *raw CSV* channels by flight, never infer absence.

    A reported availability pass requires the source bytes, time grid,
    calibration/clock references, and operator-declared rights; it still
    does NOT authenticate the measurement origin or physical independence.
    """
    if (isinstance(required_channels, (str, bytes))
            or not isinstance(required_channels, Sequence)
            or not 1 <= len(required_channels) <= 6
            or any(not isinstance(ch, str) or ch not in _CHANNEL_UNITS for ch in required_channels)
            or len(set(required_channels)) != len(required_channels)):
        raise ValueError("one to six distinct supported required_channels must be declared")
    if type(minimum_distinct_flights_per_channel) is not int or not 2 <= minimum_distinct_flights_per_channel <= 100:
        raise ValueError("minimum_distinct_flights_per_channel must be integer 2..100")
    if isinstance(original_csv_sources, (str, bytes)) or not isinstance(original_csv_sources, Sequence) or not 1 <= len(original_csv_sources) <= 1000:
        raise ValueError("1..1000 explicitly selected original CSV recording sources required")
    archive = audit_native_flight_archive(root, manifest)
    all_records = {x["relative_path"]: x for x in manifest["files"]}
    source_hash_flight = {}
    seen_paths = set()
    reports = []
    for item in original_csv_sources:
        if not isinstance(item, Mapping) or set(item) != _KEYS:
            raise ValueError("each source requires exact original CSV path/channel/step fields")
        path = item["relative_path"]
        if not isinstance(path, str) or path in seen_paths or path not in all_records:
            raise ValueError("original source path must be present and appear exactly once")
        seen_paths.add(path)
        raw = all_records[path]
        digest, flight = raw["original_sha256"], raw["flight_id"]
        if digest in source_hash_flight and source_hash_flight[digest] != flight:
            raise ValueError("identical original bytes across distinct flight IDs cannot prove independent recordings")
        source_hash_flight[digest] = flight
        row = audit_original_flight_channel_csv(
            root, manifest, relative_path=path,
            channels_with_units=item["channels_with_units"],
            maximum_declared_sample_gap_s=item["maximum_declared_sample_gap_s"],
        )
        reports.append(row)
    covered = {}
    blockers = []
    for channel in required_channels:
        available = sorted({
            r["flight_id"] for r in reports
            if channel in r["channels_with_declared_units"]
            and r["within_operator_declared_time_gap"]
            and r["calibration_reference_operator_supplied"] is not None
            and r["clock_reference_operator_supplied"] is not None
        })
        enough = len(available) >= minimum_distinct_flights_per_channel
        if not enough:
            blockers.append(
                f"{channel}: fewer than {minimum_distinct_flights_per_channel} separate claimed flights "
                "with original readable data, adequate sampling and clock/calibration references"
            )
        covered[channel] = {
            "unit": _CHANNEL_UNITS[channel],
            "declared_flight_ids_with_usable_recordings": available,
            "reported_whole_flight_count": len(available),
            "reported_coverage_gate_passed": enough,
            "actual_flight_independence_authenticated": False,
        }
    rights_present = manifest["source_permission"] is not None
    if not rights_present:
        blockers.append("Original source permission/license metadata missing; obtain and verify rights")
    unprocessed = sorted(set(all_records)-seen_paths)
    if unprocessed:
        blockers.append(
            "Other original archive sources have not been decoded under a supported exact CSV schema"
        )
    all_covered = rights_present and all(v["reported_coverage_gate_passed"] for v in covered.values())
    return {
        "status": (
            "OPERATOR_DECLARED_CHANNEL_COVERAGE_COMPLETE_EXTERNAL_EVIDENCE_REVIEW_REQUIRED"
            if all_covered else "ORIGINAL_FLIGHT_CHANNEL_COVERAGE_GAPS"
        ),
        "archive_id": archive["archive_id"],
        "declared_flight_ids_in_archive": archive["flight_ids_declared"],
        "required_channel_coverage": covered,
        "audited_exact_original_csv_sources": reports,
        "original_files_unparsed_or_not_selected": unprocessed,
        "blockers": blockers,
        "operator_reported_coverage_consistent": all_covered,
        "true_source_license_verified": False,
        "independent_original_file_custody_authenticated": False,
        "instrument_calibration_and_clocks_independently_verified": False,
        "flight_or_mission_independence_authenticated": False,
        "full_vehicle_physical_prediction_validated": False,
        "manufacturing_or_flight_release_authorized": False,
    }
