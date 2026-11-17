"""M26.26-27: narrow Zenodo source download plan and exact-byte audit.

Not a general URL downloader. Explicit research/data-use review is required
before any network request. No redirects or arbitrary provider links are used.
Downloaded bytes matching a public MD5 still do not certify an experiment.
"""
from __future__ import annotations

from hashlib import md5, sha256
from pathlib import Path
from urllib.parse import quote
from urllib.request import build_opener, HTTPRedirectHandler, Request
from collections.abc import Mapping
import re

from physics.validation.zenodo_flight_candidate import (
    DOI, EXPECTED_MD5, MAX_ORIGINAL_SIZE, RECORD_ID,
)

_MD5 = re.compile(r"^[a-f0-9]{32}$")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def plan_original_zenodo_download(metadata_report: Mapping, *,
                                  source_use_review_reference: str) -> dict:
    """Generate a fixed-provider endpoint from the verified record/file key."""
    if not isinstance(metadata_report, Mapping) or metadata_report.get("doi") != DOI:
        raise ValueError("validated Zenodo record metadata report required")
    if (not isinstance(source_use_review_reference, str)
            or not 8 <= len(source_use_review_reference.strip()) <= 500):
        raise ValueError("explicit externally reviewed data rights reference required")
    inventory = metadata_report.get("file_inventory")
    if not isinstance(inventory, list) or len(inventory) != 1:
        raise ValueError("one published original provider file required")
    item = inventory[0]
    key, size, expected = (
        item.get("provider_key_exact"), item.get("provider_bytes"),
        item.get("provider_md5"),
    )
    if (not isinstance(key, str) or len(key) > 512
            or "/" in key or "\\" in key or key in (".", "..")
            or type(size) is not int or not 0 < size <= MAX_ORIGINAL_SIZE
            or expected != EXPECTED_MD5 or not _MD5.fullmatch(expected)):
        raise ValueError("provider original file identity or digest changed")
    # A constructed endpoint avoids accepting an untrusted user/metadata URL.
    endpoint = (
        f"https://zenodo.org/api/records/{RECORD_ID}/files/"
        + quote(key, safe="") + "/content"
    )
    return {
        "status": "CONSTRAINED_OFFICIAL_ZENODO_DOWNLOAD_PLAN_NOT_EXECUTED",
        "source_doi": DOI, "record_id": RECORD_ID,
        "provider_key_exact": key,
        "expected_bytes": size,
        "expected_provider_md5": expected,
        "official_constructed_content_url": endpoint,
        "source_use_review_reference_operator_reported": source_use_review_reference.strip(),
        "provider_file_downloaded": False,
        "source_redistribution_rights_authenticated": False,
        "physical_experiment_authenticated": False,
    }


def audit_zenodo_original_stream(plan: Mapping, *,
                                 output_file: str | Path, stream) -> dict:
    """M26.27: stream exact original bytes into a NEW file, never rewrite data.

    This function accepts a supplied readable stream for deterministic tests.
    Production fetch must use download_zenodo_original() below.
    """
    if (not isinstance(plan, Mapping) or plan.get("source_doi") != DOI
            or plan.get("record_id") != RECORD_ID
            or plan.get("expected_provider_md5") != EXPECTED_MD5):
        raise ValueError("known M300 Zenodo source plan required")
    expected = plan.get("expected_bytes")
    if type(expected) is not int or not 0 < expected <= MAX_ORIGINAL_SIZE:
        raise ValueError("invalid expected source size")
    output = Path(output_file)
    if (output.is_symlink() or output.exists()
            or not output.parent.is_dir() or output.suffix.lower() != ".csv"):
        raise ValueError("original output must be a new .csv file in an existing directory")
    m, s, size = md5(), sha256(), 0
    created = False
    try:
        with output.open("xb") as handle:
            created = True
            while True:
                chunk = stream.read(min(256 * 1024, expected - size + 1))
                if not chunk:
                    break
                if not isinstance(chunk, bytes):
                    raise ValueError("original stream must yield bytes")
                size += len(chunk)
                if size > expected:
                    raise ValueError("original source larger than provider-declared byte length")
                m.update(chunk)
                s.update(chunk)
                handle.write(chunk)
            if size != expected:
                raise ValueError("original source byte length does not match provider record")
            if m.hexdigest() != EXPECTED_MD5:
                raise ValueError("original source bytes failed official provider MD5 check")
    except BaseException:
        # Never leave a partially downloaded or bad-hash source posing as original.
        if created and output.exists():
            output.unlink()
        raise
    return {
        "status": "ZENODO_PROVIDER_CHECKSUM_MATCHED_SOURCE_BYTES_LOCALLY_SAVED",
        "source_doi": DOI, "record_id": RECORD_ID,
        "source_filename_as_downloaded": output.name,
        "actual_source_bytes": size, "provider_md5_matched": True,
        "computed_original_sha256": s.hexdigest(),
        "operator_rights_review_reference": plan["source_use_review_reference_operator_reported"],
        "provider_tls_and_experiment_origin_independently_authenticated": False,
        "physical_aircraft_hardware_matched": False,
        "flight_validation_authorized": False,
    }


def download_zenodo_original(plan: Mapping, *,
                             output_file: str | Path, timeout_seconds: int = 30) -> dict:
    """Perform explicit network request only to canonical fixed-host content URL.

    No redirects, no arbitrary URL fetching and no overwrite. Network failures
    never fall back to generated observations or vendor-agnostic datasets.
    """
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise ValueError("bounded integer source download timeout required")
    endpoint = plan.get("official_constructed_content_url") if isinstance(plan, Mapping) else None
    key = plan.get("provider_key_exact") if isinstance(plan, Mapping) else None
    canonical = (
        f"https://zenodo.org/api/records/{RECORD_ID}/files/"
        + quote(key, safe="") + "/content"
        if isinstance(key, str) and 0 < len(key) <= 512 else None
    )
    if endpoint != canonical or not isinstance(endpoint, str):
        raise ValueError("download URL is not the fixed canonical Zenodo record content URL")
    req = Request(endpoint, headers={
        "Accept": "application/octet-stream",
        "Accept-Encoding": "identity",
        "User-Agent": "AeroForge-SourceIntake/1.0",
    })
    with build_opener(_NoRedirect()).open(req, timeout=timeout_seconds) as response:
        if response.status != 200:
            raise ValueError("official source file response not successful")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("unexpected compressed source transfer encoding")
        header_length = response.headers.get("Content-Length")
        if header_length and int(header_length) != plan["expected_bytes"]:
            raise ValueError("downloaded Content-Length differs from provider file metadata")
        return audit_zenodo_original_stream(plan, output_file=output_file, stream=response)
