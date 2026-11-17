"""M26.35: constrained alternate official Zenodo transport for one pinned M300 CSV.

The file must be verified by original provider MD5 and byte count. The
alternate landing download route is not evidence that retrieval succeeded.
Redirects to non-Zenodo hosts are refused rather than trusted automatically.
"""
from __future__ import annotations

from urllib.parse import urlparse, quote
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError
from collections.abc import Mapping

from physics.validation.zenodo_flight_candidate import RECORD_ID, DOI, EXPECTED_MD5, MAX_ORIGINAL_SIZE
from physics.validation.zenodo_original_download import audit_zenodo_original_stream


class _OnlyOfficialZenodoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = urlparse(newurl)
        if (new.scheme != "https" or new.hostname != "zenodo.org"
                or new.port not in (None, 443) or new.username or new.password
                or not (new.path.startswith("/api/") or
                        new.path.startswith(f"/records/{RECORD_ID}/files/"))):
            raise ValueError("redirect outside pinned official Zenodo endpoints refused")
        current = int(req.headers.get("X-Source-Redirect-Hop", "0"))
        if current >= 3:
            raise ValueError("too many original-data redirects")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            raise ValueError("provider download redirect cannot be followed safely")
        redirected.add_header("X-Source-Redirect-Hop", str(current + 1))
        return redirected


def _official_source_urls(plan: Mapping) -> list[str]:
    if (not isinstance(plan, Mapping)
            or plan.get("source_doi") != DOI or plan.get("record_id") != RECORD_ID
            or plan.get("expected_provider_md5") != EXPECTED_MD5
            or type(plan.get("expected_bytes")) is not int
            or not 0 < plan["expected_bytes"] <= MAX_ORIGINAL_SIZE
            or not isinstance(plan.get("source_use_review_reference_operator_reported"), str)
            or len(plan["source_use_review_reference_operator_reported"].strip()) < 8):
        raise ValueError("official source identity, byte bounds and rights-review declaration required")
    key = plan.get("provider_key_exact")
    if (not isinstance(key, str) or not 1 <= len(key) <= 512 or
            key in (".", "..") or "/" in key or "\\" in key or
            not key.casefold().endswith(".csv")):
        raise ValueError("source original file key invalid")
    encoded = quote(key, safe="")
    api = f"https://zenodo.org/api/records/{RECORD_ID}/files/{encoded}/content"
    if plan.get("official_constructed_content_url") != api:
        raise ValueError("official provider download URL must be canonical")
    landing = f"https://zenodo.org/records/{RECORD_ID}/files/{encoded}?download=1"
    return [api, landing]


def alternate_zenodo_original_download(plan: Mapping, *, output_file,
                                       timeout_seconds: int = 30) -> dict:
    """Try fixed API path then fixed landing-file path, and checksum every byte.

    No third-party mirror, broad redirect, fabricated data or existing file
    overwrite. A corrupt/oversized response is terminal, never a fallback.
    """
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 120:
        raise ValueError("download timeout must be 1..120 seconds")
    urls = _official_source_urls(plan)
    unavailable = []
    for endpoint in urls:
        request = Request(endpoint, headers={
            "Accept": "application/octet-stream",
            "Accept-Encoding": "identity",
            "User-Agent": "AeroForge-SourceIntake/1.0",
        })
        try:
            with build_opener(_OnlyOfficialZenodoRedirects()).open(
                request, timeout=timeout_seconds
            ) as response:
                if response.status != 200:
                    raise ValueError("official original-data HTTP status not 200")
                if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                    raise ValueError("compressed transfer of original file forbidden")
                length = response.headers.get("Content-Length")
                if length is not None and int(length) != plan["expected_bytes"]:
                    raise ValueError("transfer byte count differs from official metadata")
                report = audit_zenodo_original_stream(
                    plan, output_file=output_file, stream=response,
                )
                return {
                    **report,
                    "download_route": "provider_api_content" if endpoint == urls[0]
                    else "provider_public_landing_file",
                    "official_provider_only_redirect_policy": True,
                }
        except (HTTPError, URLError, TimeoutError) as exc:
            unavailable.append(f"{urlparse(endpoint).path}: {type(exc).__name__}")
    raise ValueError("both official file endpoints unavailable; original file not acquired: "
                     + "; ".join(unavailable))
