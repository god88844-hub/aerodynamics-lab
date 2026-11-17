"""M26.2: enumerate actual on-disk native originals without making up source IDs.

An inventory draft is only a deterministic, *operator-declared* source
manifest. Every present file must be assigned a flight and sensor family
explicitly; no source license, signal channel, clock or calibration is inferred.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from physics.validation.native_flight_archive import (
    _MAX_FILES, _id, _text, audit_native_flight_archive,
    hash_original_archive_file,
)

_ASSIGNMENT_KEYS = {
    "relative_path", "flight_id", "sensor_family",
    "declared_channels", "calibration_reference", "clock_reference", "source_notes",
}


def draft_native_flight_manifest(
    root: str | Path, *,
    archive_id: str,
    publication_reference: str,
    archive_record_reference: str,
    declared_vehicle_identity: str,
    assignments: Sequence[Mapping],
    source_permission: str | None = None,
) -> dict:
    """Draft an exact-file manifest from bytes, rejecting ANY omitted source.

    Only complete operator-provided filenames, flight IDs and sensor-family
    declarations are accepted; there is no source-specific native decoder.
    """
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("original source root must be a directory")
    _id(archive_id, "archive_id")
    _text(publication_reference, "publication_reference")
    _text(archive_record_reference, "archive_record_reference")
    _text(declared_vehicle_identity, "declared_vehicle_identity")
    _text(source_permission, "source_permission", nullable=True)
    if isinstance(assignments, (str, bytes)) or not isinstance(assignments, Sequence) or not 1 <= len(assignments) <= _MAX_FILES:
        raise ValueError("1..1000 explicit source file/flight assignments required")

    actual = set()
    for path in base.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlinks inside immutable original folder are forbidden")
        if path.is_file():
            actual.add(path.relative_to(base).as_posix())
            if len(actual) > _MAX_FILES:
                raise ValueError("more than 1000 original evidence files")
        elif not path.is_dir():
            raise ValueError("unsupported non-regular object in original source folder")
    expected = set()
    files = []
    for item in assignments:
        if not isinstance(item, Mapping) or set(item) != _ASSIGNMENT_KEYS:
            raise ValueError("assignment must contain exact original path, flight, sensor, channel and provenance fields")
        rel = item["relative_path"]
        if not isinstance(rel, str) or rel in expected:
            raise ValueError("duplicate or invalid source relative_path assignment")
        expected.add(rel)
        _id(item["flight_id"], "flight_id")
        _id(item["sensor_family"], "sensor_family")
        channels = item["declared_channels"]
        if (isinstance(channels, (str, bytes)) or not isinstance(channels, Sequence)
                or len(channels) > 64 or any(not isinstance(ch, str) for ch in channels)):
            raise ValueError("declared_channels must be a sequence of names or empty if unknown")
        _text(item["calibration_reference"], "calibration_reference", nullable=True)
        _text(item["clock_reference"], "clock_reference", nullable=True)
        _text(item["source_notes"], "source_notes", nullable=True)
        if rel not in actual:
            raise ValueError(f"unlisted/missing original source path: {rel}")
        hashed = hash_original_archive_file(base, rel)
        files.append({
            **item,
            "original_sha256": hashed["computed_original_sha256"],
            "original_byte_count": hashed["original_byte_count"],
        })
    if actual != expected:
        raise ValueError(f"original source inventory incomplete; unassigned files: {sorted(actual-expected)}")
    files.sort(key=lambda x: x["relative_path"])
    manifest = {
        "schema_version": "1.0",
        "archive_id": archive_id,
        "publication_reference": publication_reference,
        "archive_record_reference": archive_record_reference,
        "source_permission": source_permission,
        "declared_vehicle_identity": declared_vehicle_identity,
        "files": files,
    }
    # Check the newly computed manifest against *every* source byte and schema
    # before returning it; this never authenticates who acquired those bytes.
    verified = audit_native_flight_archive(base, manifest)
    return {
        "manifest": manifest,
        "source_integrity_audit": verified,
        "all_present_original_files_enumerated": True,
        "source_filenames_and_bytes_unchanged": True,
        "operator_assignments_physically_authenticated": False,
        "published_source_or_license_independently_verified": False,
        "physical_flight_measurements_validated": False,
        "flight_release_authorized": False,
    }
