"""Read-only Dataverse source discovery and local original-byte preflight.

No publication, self-supplied checksum or matching model name authenticates
independent physical evidence, original instrument origin, or flight safety.
"""
from __future__ import annotations

from hashlib import md5, sha256
from pathlib import Path
from typing import Mapping
import re

EXPECTED_PID = "doi:10.7910/DVN/J5L2P4"
METADATA_URL = (
    "https://dataverse.harvard.edu/api/datasets/:persistentId/"
    "?persistentId=doi%3A10.7910%2FDVN%2FJ5L2P4"
)
MAX_METADATA_FILES = 500
MAX_ORIGINAL_BYTES = 100_000_000
_HEX = re.compile(r"^[0-9a-fA-F]+$")


def _persistent_id(payload: Mapping) -> str:
    direct = payload.get("persistentId")
    if isinstance(direct, str):
        return direct
    protocol, authority, identifier = (
        payload.get("protocol"), payload.get("authority"), payload.get("identifier")
    )
    if all(isinstance(x, str) and x for x in (protocol, authority, identifier)):
        return f"{protocol}:{authority}/{identifier}"
    return ""


def inspect_dataverse_candidate(response: Mapping) -> dict:
    """Inventory provider metadata ONLY; original observations not retrieved."""
    if not isinstance(response, Mapping) or response.get("status") != "OK":
        raise ValueError("Dataverse metadata API response is missing or not OK")
    data = response.get("data")
    if not isinstance(data, Mapping) or _persistent_id(data) != EXPECTED_PID:
        raise ValueError("Dataverse persistent ID does not match the published source DOI")
    version = data.get("latestVersion")
    if not isinstance(version, Mapping):
        raise ValueError("Dataverse latestVersion metadata is missing")
    raw_files = version.get("files")
    if not isinstance(raw_files, list) or len(raw_files) > MAX_METADATA_FILES:
        raise ValueError("Dataverse file list absent or unbounded")
    files = []
    seen = set()
    for row in raw_files:
        if not isinstance(row, Mapping) or not isinstance(row.get("dataFile"), Mapping):
            raise ValueError("Invalid Dataverse file metadata entry")
        dat = row["dataFile"]
        file_id, filename, size = dat.get("id"), dat.get("filename"), dat.get("filesize")
        if type(file_id) is not int or file_id <= 0 or file_id in seen:
            raise ValueError("Missing, invalid or duplicate Dataverse file ID")
        seen.add(file_id)
        if not isinstance(filename, str) or not 1 <= len(filename) <= 512:
            raise ValueError("Missing or invalid Dataverse filename")
        if type(size) is not int or size < 0:
            raise ValueError("Missing or invalid file byte count")
        checksum = dat.get("checksum")
        algo = digest = None
        if checksum is not None:
            if not isinstance(checksum, Mapping):
                raise ValueError("Malformed provider checksum")
            algo, digest = checksum.get("type"), checksum.get("value")
            required_size = {"MD5": 32, "SHA-256": 64, "SHA256": 64}.get(algo)
            if required_size is None or not isinstance(digest, str) or len(digest) != required_size or not _HEX.fullmatch(digest):
                raise ValueError("Unsupported or malformed provider checksum")
        files.append({
            "file_id": file_id,
            "filename_as_published": filename,
            "bytes_reported": size,
            "restricted_by_provider": bool(dat.get("restricted", False)),
            "original_provider_checksum_type": algo,
            "original_provider_checksum": digest,
            "download_endpoint": f"https://dataverse.harvard.edu/api/access/datafile/{file_id}",
            "original_bytes_retrieved": False,
            "original_sha256_computed": None,
        })
    released = version.get("versionState") == "RELEASED"
    return {
        "source_doi": EXPECTED_PID,
        "source_article_doi": "10.3390/aerospace10060528",
        "data_repository": "Harvard Dataverse",
        "metadata_version_reported": {
            "number": version.get("versionNumber"),
            "minor": version.get("versionMinorNumber"),
            "state": version.get("versionState"),
        },
        "metadata_file_count": len(files),
        "file_inventory": files,
        "metadata_discovery_status": (
            "PUBLISHED_FILE_METADATA_FOUND_RAW_BYTES_AND_RIGHTS_PENDING"
            if released and files else "DATASET_VERSION_OR_FILE_LIST_NOT_READY"
        ),
        "source_license_or_permission_verified": False,
        "specific_setup_3_files_identified": False,
        "original_file_custody_authenticated": False,
        "hardware_revision_match_authenticated": False,
        "selected_ESC_and_mount_match_authenticated": False,
        "independent_holdout_split_authenticated": False,
        "physical_propulsion_model_validated": False,
        "full_aircraft_validated": False,
        "flight_release_authorized": False,
    }


def inspect_original_local_file(metadata_report: Mapping, *, file_id: int, local_path: str | Path) -> dict:
    """Hash already-acquired original bytes without modification.

    Provider MD5 is checked when present, but MD5 is not strong provenance.
    """
    if not isinstance(metadata_report, Mapping) or metadata_report.get("source_doi") != EXPECTED_PID:
        raise ValueError("Verified source metadata discovery report required")
    if type(file_id) is not int:
        raise ValueError("An explicit integer provider file ID is required")
    candidates = [f for f in metadata_report.get("file_inventory", [])
                  if isinstance(f, Mapping) and f.get("file_id") == file_id]
    if len(candidates) != 1:
        raise ValueError("File ID does not appear exactly once in source metadata")
    item = candidates[0]
    if item.get("restricted_by_provider"):
        raise ValueError("Restricted source file cannot be asserted freely reusable")
    src = Path(local_path)
    if not src.is_file() or src.is_symlink():
        raise ValueError("Original file must be a regular, non-symlinked existing local file")
    size = src.stat().st_size
    if size > MAX_ORIGINAL_BYTES:
        raise ValueError("Original file exceeds bounded local evidence audit size")
    original = src.read_bytes()
    if len(original) != item["bytes_reported"]:
        raise ValueError("Original local byte count differs from provider metadata")
    provider_algo, checksum = item["original_provider_checksum_type"], item["original_provider_checksum"]
    if provider_algo is not None:
        locally_hashed = md5(original).hexdigest() if provider_algo == "MD5" else sha256(original).hexdigest()
        if locally_hashed.lower() != checksum.lower():
            raise ValueError("Locally obtained original bytes mismatch provider checksum")
    return {
        "source_doi": EXPECTED_PID,
        "file_id": file_id,
        "provider_filename": item["filename_as_published"],
        "original_byte_count": len(original),
        "computed_original_sha256": sha256(original).hexdigest(),
        "provider_checksum_matched_if_provided": provider_algo is not None,
        "original_local_file_read_without_mutation": True,
        "original_file_was_observed_on_publication_host": False,
        "provider_download_chain_or_author_authenticated": False,
        "selected_motor_ESC_propeller_revision_authenticated": False,
        "source_use_permission_independently_verified": False,
        "physical_validation_conclusion": "ORIGINAL_BYTES_LOCALLY_HASHED_NOT_PHYSICALLY_VALIDATED",
        "flight_release_authorized": False,
    }


def assess_setup_three_hardware_match(*, published: Mapping, reference: Mapping) -> dict:
    """Matching operator-provided names does not prove serial/revision identity."""
    keys = {"motor_name", "motor_revision", "esc_name", "propeller_name", "mount_revision"}
    if not isinstance(published, Mapping) or not isinstance(reference, Mapping):
        raise ValueError("Published and reference hardware identity records required")
    if set(published) != keys or set(reference) != keys:
        raise ValueError("Each hardware record must specify exact identity fields")
    matches = {}
    unknown = []
    for key in keys:
        a, b = published[key], reference[key]
        if a is not None and (not isinstance(a, str) or not a.strip()):
            raise ValueError("Hardware identity fields must be names or null")
        if b is not None and (not isinstance(b, str) or not b.strip()):
            raise ValueError("Hardware identity fields must be names or null")
        matches[key] = None if a is None or b is None else a == b
        if matches[key] is None:
            unknown.append(key)
    complete = all(v is True for v in matches.values())
    return {
        "status": ("NOMINAL_METADATA_MATCH_EXTERNAL_HARDWARE_AUTHENTICATION_REQUIRED"
                   if complete else "EXACT_INSTALLED_HARDWARE_MATCH_NOT_ESTABLISHED"),
        "per_attribute_reported_string_match": matches,
        "unknown_hardware_fields": unknown,
        "all_declared_strings_equal": complete,
        "independent_serial_revision_and_mount_match_authenticated": False,
        "physical_validation_eligible": False,
        "flight_release_authorized": False,
    }
