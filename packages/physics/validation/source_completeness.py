"""M26.5: fail-closed completeness and duplicate-source audit for real local files.

A hash against an operator-controlled manifest is byte-consistency evidence,
NOT independent hardware/file custody authentication or flight validation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from collections.abc import Mapping

from physics.validation.native_flight_archive import audit_native_flight_archive


def audit_source_completeness(root: str | Path, manifest: Mapping) -> dict:
    """Reject any undeclared native file, symlink or reused byte stream across flights.

    A regular-file inventory is taken *both before and after* the full native
    archive audit to detect ordinary concurrent changes. This is not an atomic
    filesystem snapshot and cannot defeat a malicious actor controlling files.
    """
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("original evidence root must be a directory")

    def actual_files() -> set[str]:
        found: set[str] = set()
        for directory, dirs, files in os.walk(base, followlinks=False):
            for name in dirs + files:
                p = Path(directory) / name
                if p.is_symlink():
                    raise ValueError("symlinked native evidence entries are forbidden")
                if not p.is_dir() and not p.is_file():
                    raise ValueError("unsupported special source file")
            for name in files:
                p = Path(directory) / name
                relative = p.relative_to(base).as_posix()
                if relative in found:
                    raise ValueError("duplicate native file in filesystem inventory")
                found.add(relative)
                if len(found) > 1000:
                    raise ValueError("original file count exceeds 1000")
        return found

    before = actual_files()
    checked = audit_native_flight_archive(base, manifest)
    declared = {r["relative_path"] for r in checked["original_files_checked"]}
    if before != declared:
        raise ValueError(
            "original source completeness mismatch: "
            f"undeclared={sorted(before - declared)!r}; absent={sorted(declared - before)!r}"
        )
    after = actual_files()
    if after != before:
        raise ValueError("original source inventory changed during file integrity audit")

    # Byte-identical different alleged flights must not count as independent.
    sha_flight: dict[str, str] = {}
    duplicate_within: list[str] = []
    for entry in checked["original_files_checked"]:
        digest = entry["computed_original_sha256"]
        flight = entry["flight_id"]
        if digest in sha_flight and sha_flight[digest] != flight:
            raise ValueError("identical original source bytes reused across declared flights")
        if digest in sha_flight:
            duplicate_within.append(entry["relative_path"])
        sha_flight[digest] = flight

    canonical = json.dumps(
        [
            {"path": r["relative_path"], "flight": r["flight_id"],
             "bytes": r["original_byte_count"], "sha256": r["computed_original_sha256"]}
            for r in checked["original_files_checked"]
        ],
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return {
        "status": "COMPLETE_SELF_REPORTED_ORIGINAL_FILE_SET_UNAUTHENTICATED",
        "archive_id": checked["archive_id"],
        "whole_archive_files_checked": len(declared),
        "declared_flight_ids": checked["flight_ids_declared"],
        "canonical_file_inventory_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "byte_identical_files_within_same_flight": sorted(duplicate_within),
        "missing_calibration_references": checked["missing_calibration_references"],
        "missing_clock_references": checked["missing_clock_references"],
        "unknown_original_channels": checked["unknown_original_channels"],
        "all_present_files_accounted_for": True,
        "independent_original_recorder_custody_authenticated": False,
        "all_declared_flights_independently_verified": False,
        "physical_measurements_validated": False,
        "flight_release_authorized": False,
    }
