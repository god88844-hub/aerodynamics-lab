"""Offline immutable-original flight archive custody preflight.

Unlike M19, this supports instrument-native TDMS/MAT/HDF5/ZIP/binary files.
It does not decode those formats, infer timestamps, calibrate instruments,
validate model predictions, or authenticate a download or flight occurrence.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from collections.abc import Mapping, Sequence
import re

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_FORMATS = {"tdms", "mat", "h5", "hdf5", "csv", "txt", "bin", "dat", "zip"}
_CHUNK = 1024 * 1024
_MAX_FILE = 20 * 1024**3
_MAX_FILES = 1000
_MANIFEST_KEYS = {
    "schema_version", "archive_id", "publication_reference",
    "archive_record_reference", "source_permission",
    "declared_vehicle_identity", "files",
}
_FILE_KEYS = {
    "relative_path", "flight_id", "sensor_family",
    "declared_channels", "original_sha256", "original_byte_count",
    "calibration_reference", "clock_reference", "source_notes",
}


def _text(value: object, field: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
        raise ValueError(f"{field}: nonempty text source or explicit null required")
    return value.strip()


def _id(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{field}: unsupported identifier")
    return value


def _file(root: Path, relative_path: object) -> Path:
    if not isinstance(relative_path, str) or not 1 <= len(relative_path) <= 240:
        raise ValueError("source relative_path missing or too long")
    rel = Path(relative_path)
    if rel.is_absolute() or len(rel.parts) > 8 or any(p in ("..", ".", "") for p in rel.parts):
        raise ValueError("source relative_path must be a safe, shallow relative path")
    if any(not _ID.fullmatch(p) for p in rel.parts):
        raise ValueError("source relative_path contains unapproved characters")
    if rel.suffix.lower().lstrip(".") not in _ALLOWED_FORMATS:
        raise ValueError("source file format not admitted for native archive inventory")
    base = root.resolve(strict=True)
    if not base.is_dir():
        raise ValueError("source root must be an existing directory")
    current = base
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("source symlinks cannot be used for immutable originals")
    target = base / rel
    if not target.is_file() or not target.resolve(strict=True).is_relative_to(base):
        raise ValueError("source original file is missing or outside evidence root")
    return target


def hash_original_archive_file(root: Path | str, relative_path: str) -> dict:
    """Read and hash a real file in bounded chunks, never altering its bytes."""
    original = _file(Path(root), relative_path)
    size_before = original.stat().st_size
    if size_before <= 0 or size_before > _MAX_FILE:
        raise ValueError("source original file byte count must be 1..20 GiB")
    digest = sha256()
    counted = 0
    with original.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            counted += len(chunk)
            if counted > _MAX_FILE:
                raise ValueError("source file changed or exceeded permitted size")
            digest.update(chunk)
    if counted != size_before or original.stat().st_size != size_before:
        raise ValueError("source original file changed during hashing")
    return {
        "relative_path": relative_path,
        "original_byte_count": counted,
        "computed_original_sha256": digest.hexdigest(),
        "original_file_read_without_mutation": True,
        "publisher_original_download_authenticated": False,
        "physical_flight_measurement_origin_authenticated": False,
    }


def audit_native_flight_archive(root: Path | str, manifest: Mapping) -> dict:
    """Check *all* declared original files, with no missing-file success fallback."""
    if not isinstance(manifest, Mapping) or set(manifest) != _MANIFEST_KEYS:
        raise ValueError("flight archive manifest requires exact root fields")
    if manifest["schema_version"] != "1.0":
        raise ValueError("unsupported original flight manifest schema version")
    archive_id = _id(manifest["archive_id"], "archive_id")
    publication = _text(manifest["publication_reference"], "publication_reference")
    record = _text(manifest["archive_record_reference"], "archive_record_reference")
    permission = _text(manifest["source_permission"], "source_permission", nullable=True)
    identity = _text(manifest["declared_vehicle_identity"], "declared_vehicle_identity")
    files = manifest["files"]
    if isinstance(files, (str, bytes)) or not isinstance(files, Sequence) or not 1 <= len(files) <= _MAX_FILES:
        raise ValueError("1..1000 original files must be explicitly listed")
    paths, flight_ids, results = set(), set(), []
    calibration_gaps, timing_gaps, channel_gaps = [], [], []
    for item in files:
        if not isinstance(item, Mapping) or set(item) != _FILE_KEYS:
            raise ValueError("each original file must have complete explicit metadata fields")
        path = item["relative_path"]
        if not isinstance(path, str) or path in paths:
            raise ValueError("duplicate or invalid relative original file path")
        paths.add(path)
        flight = _id(item["flight_id"], "flight_id")
        sensor = _id(item["sensor_family"], "sensor_family")
        flight_ids.add(flight)
        declared_channels = item["declared_channels"]
        if (isinstance(declared_channels, (str, bytes))
                or not isinstance(declared_channels, Sequence)
                or len(declared_channels) > 64
                or len(set(declared_channels)) != len(declared_channels)
                or any(not isinstance(ch, str) or not _ID.fullmatch(ch) for ch in declared_channels)):
            raise ValueError("declared_channels must be unique ASCII channel IDs, or an empty unknown list")
        expected_sha = item["original_sha256"]
        expected_bytes = item["original_byte_count"]
        if not isinstance(expected_sha, str) or not _HASH.fullmatch(expected_sha):
            raise ValueError("original source SHA-256 must be lowercase 64-hex")
        if type(expected_bytes) is not int or not 1 <= expected_bytes <= _MAX_FILE:
            raise ValueError("original source byte count is missing or outside range")
        calibration = _text(item["calibration_reference"], "calibration_reference", nullable=True)
        clock = _text(item["clock_reference"], "clock_reference", nullable=True)
        _text(item["source_notes"], "source_notes", nullable=True)
        hashed = hash_original_archive_file(root, path)
        if hashed["original_byte_count"] != expected_bytes:
            raise ValueError(f"{path}: original byte count changed from pinned manifest")
        if hashed["computed_original_sha256"] != expected_sha:
            raise ValueError(f"{path}: original SHA-256 differs from pinned manifest")
        if calibration is None:
            calibration_gaps.append(path)
        if clock is None:
            timing_gaps.append(path)
        if not declared_channels:
            channel_gaps.append(path)
        results.append({
            **hashed, "flight_id": flight, "sensor_family": sensor,
            "declared_channels_operator_reported": sorted(declared_channels),
            "calibration_reference_operator_reported": calibration,
            "clock_reference_operator_reported": clock,
        })
    results.sort(key=lambda x: x["relative_path"])
    return {
        "status": "LOCAL_ORIGINAL_BYTES_MATCH_SELF_SUPPLIED_MANIFEST_ONLY",
        "archive_id": archive_id,
        "publication_reference_operator_reported": publication,
        "archive_record_reference_operator_reported": record,
        "vehicle_identity_operator_reported": identity,
        "source_permission_operator_reported": permission,
        "flight_ids_declared": sorted(flight_ids),
        "original_file_count": len(results),
        "original_files_checked": results,
        "missing_calibration_references": sorted(calibration_gaps),
        "missing_clock_references": sorted(timing_gaps),
        "unknown_original_channels": sorted(channel_gaps),
        "source_rights_need_independent_verification": True,
        "original_recorder_or_file_custody_authenticated": False,
        "actual_channel_contents_decoded_or_verified": False,
        "physical_instrument_calibrations_authenticated": False,
        "measurement_clock_alignment_authenticated": False,
        "whole_flight_independence_or_blinding_authenticated": False,
        "full_aircraft_prediction_validated": False,
        "manufacturing_or_flight_release_authorized": False,
    }
