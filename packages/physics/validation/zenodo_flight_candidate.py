"""M26.25: verify provider-shaped metadata for one concrete Zenodo flight dataset.

This SOURCE CANDIDATE is the DJI Matrice 300 KIOS drone telemetry dataset
(doi:10.5281/zenodo.7643456), NOT the AeroForge 60 kg reference hexacopter.
Provider identity, exact file metadata, license, and data authenticity are
separate from simply checking an operator-supplied JSON object.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import re

RECORD_ID = 7643456
DOI = "10.5281/zenodo.7643456"
EXPECTED_MD5 = "e2f188e8f5cbf498c7009f422d401207"
ORIGINAL_CSV_DELIMITER = ";"
METADATA_API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
MAX_ORIGINAL_SIZE = 25_000_000
_HEX = re.compile(r"^[0-9a-f]{32}$")
_NAME = "Drone onboard multi-modal sensor dataset"
_REQUIRED = {"id", "metadata", "files"}


def _files_from_provider(payload: Mapping) -> list:
    files = payload.get("files")
    if isinstance(files, Mapping):
        entries = files.get("entries")
        if not isinstance(entries, Mapping) or len(entries) > 100:
            raise ValueError("unsupported Zenodo v2 file entries")
        normalized = []
        for name, entry in entries.items():
            if not isinstance(entry, Mapping):
                raise ValueError("malformed provider file metadata")
            normalized.append({**entry, "key": entry.get("key", name)})
        return normalized
    if isinstance(files, list) and len(files) <= 100:
        return files
    raise ValueError("bounded Zenodo v1/v2 files metadata required")


def inspect_zenodo_m300_record(provider_response: Mapping) -> dict:
    """Require DOI, record id, published file identity and provider MD5.

    This is a parser for official-provider *shaped* metadata, not proof the
    JSON was obtained directly from an authentic TLS session.
    """
    if not isinstance(provider_response, Mapping) or not _REQUIRED <= set(provider_response):
        raise ValueError("complete Zenodo API record metadata required")
    if type(provider_response["id"]) is not int or provider_response["id"] != RECORD_ID:
        raise ValueError("Zenodo record identifier differs from known published ID")
    doi = provider_response.get("doi")
    if not isinstance(doi, str) or doi.lower() != DOI:
        raise ValueError("Zenodo record DOI mismatch")
    metadata = provider_response["metadata"]
    if not isinstance(metadata, Mapping):
        raise ValueError("Zenodo article metadata missing")
    title = metadata.get("title")
    if not isinstance(title, str) or _NAME.casefold() not in title.casefold():
        raise ValueError("Zenodo dataset title differs from the known publication")
    entries = _files_from_provider(provider_response)
    seen, inventory = set(), []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("invalid Zenodo file metadata")
        key = entry.get("key")
        size = entry.get("size")
        checksum = entry.get("checksum")
        if not isinstance(key, str) or not 1 <= len(key) <= 512 or key in seen:
            raise ValueError("invalid or duplicate Zenodo file key")
        seen.add(key)
        if type(size) is not int or not 1 <= size <= MAX_ORIGINAL_SIZE:
            raise ValueError("Zenodo original file size outside bounded reader")
        if not isinstance(checksum, str) or not checksum.startswith("md5:"):
            raise ValueError("Zenodo provider MD5 checksum required")
        digest = checksum[4:].lower()
        if not _HEX.fullmatch(digest):
            raise ValueError("invalid provider MD5")
        inventory.append({
            "provider_key_exact": key, "provider_bytes": size,
            "provider_md5": digest,
            "csv_filename_extension_reported": key.casefold().endswith(".csv"),
        })
    if len(inventory) != 1 or inventory[0]["provider_md5"] != EXPECTED_MD5:
        raise ValueError("Zenodo source candidate file list differs from published MD5")
    if not inventory[0]["csv_filename_extension_reported"]:
        raise ValueError("expected source file no longer named CSV")
    license_value = metadata.get("license")
    license_id = (license_value.get("id") if isinstance(license_value, Mapping)
                  else license_value if isinstance(license_value, str) else None)
    return {
        "status": "PUBLISHED_M300_RECORD_METADATA_SCREENED_RAW_BYTES_NOT_RETRIEVED",
        "provider": "Zenodo",
        "record_id": RECORD_ID, "doi": DOI,
        "metadata_api_url": METADATA_API_URL,
        "metadata_title_as_returned": title,
        "file_inventory": inventory,
        "license_identifier_from_provider_metadata_unverified": license_id,
        "reported_aircraft_type_from_dataset_description": "DJI Matrice 300",
        "aeroforge_60kg_hexacopter_hardware_matched": False,
        "original_data_file_locally_verified": False,
        "provider_tls_response_independently_authenticated": False,
        "source_rights_independently_reviewed": False,
        "source_instrument_calibration_verified": False,
        "original_data_for_physical_validation_acquired": False,
        "full_vehicle_physical_accuracy_established": False,
        "flight_release_authorized": False,
    }
