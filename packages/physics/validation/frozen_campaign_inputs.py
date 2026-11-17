"""M26.14: exact original input-byte locking for a flight comparison campaign.

Uses explicit operator-supplied SHA-256 pins for both JSON documents; validates
a strict typed top-level schema and does not silently accept NaN/duplicate keys.
Self-supplied digest consistency never proves real original-source custody,
physical experiment existence, historical freeze, or independent holdout status.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path
import re

_SHA = re.compile(r"^[a-f0-9]{64}$")
_MAX_JSON = 2_000_000
_CAMPAIGN_KEYS = {
    "holdout_case", "required_metrics", "comparison_cases",
    "required_limits", "stress_cases", "review_documents",
}


def _no_constant(value: str):
    raise ValueError(f"nonfinite JSON constant forbidden: {value}")


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key forbidden: {key}")
        obj[key] = value
    return obj


def _read_pinned_json(path: Path | str, pinned_sha256: str, label: str) -> tuple[dict, dict]:
    if not isinstance(pinned_sha256, str) or not _SHA.fullmatch(pinned_sha256):
        raise ValueError(f"{label}: original JSON SHA-256 must be lowercase 64-hex")
    src = Path(path)
    if src.is_symlink() or not src.is_file():
        raise ValueError(f"{label}: regular nonsymlink JSON input required")
    if not 0 < src.stat().st_size <= _MAX_JSON:
        raise ValueError(f"{label}: JSON input must be 1..2000000 bytes")
    original = src.read_bytes()
    actual_sha = sha256(original).hexdigest()
    if actual_sha != pinned_sha256:
        raise ValueError(f"{label}: source JSON SHA-256 mismatch")
    try:
        obj = json.loads(original.decode("utf-8"), parse_constant=_no_constant,
                         object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: malformed original JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"{label}: JSON root must be an object")
    return obj, {
        "source_label": label, "original_sha256": actual_sha,
        "original_byte_count": len(original),
        "source_bytes_match_operator_pinned_sha256": True,
        "independent_source_provenance_authenticated": False,
    }


def audit_frozen_campaign_inputs(
    *, source_manifest_json: Path | str, source_manifest_sha256: str,
    campaign_json: Path | str, campaign_sha256: str,
) -> dict:
    """Load and fingerprint exact frozen file bytes without modifying originals."""
    src = Path(source_manifest_json).resolve(strict=True)
    campaign = Path(campaign_json).resolve(strict=True)
    if src == campaign:
        raise ValueError("source manifest and frozen campaign must be different JSON files")
    manifest, source_pin = _read_pinned_json(source_manifest_json, source_manifest_sha256, "source_manifest")
    config, campaign_pin = _read_pinned_json(campaign_json, campaign_sha256, "campaign")
    if set(config) != _CAMPAIGN_KEYS:
        raise ValueError("campaign requires exact freeze/metric/comparison/limits/stress/review keys")
    if not isinstance(config["holdout_case"], Mapping):
        raise ValueError("holdout_case must be an object")
    for name in ("required_metrics", "comparison_cases", "required_limits", "stress_cases", "review_documents"):
        if not isinstance(config[name], list):
            raise ValueError(f"{name} must be an explicit JSON array")
    if not isinstance(manifest.get("files"), list) or not manifest.get("files"):
        raise ValueError("source manifest must contain original file inventory")
    snapshot = {
        "source_manifest_sha256": source_pin["original_sha256"],
        "campaign_sha256": campaign_pin["original_sha256"],
    }
    fingerprint = sha256(json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return {
        "source_manifest": manifest, "campaign": config,
        "input_pin_report": {
            "status": "ORIGINAL_JSON_BYTES_MATCH_OPERATOR_PINS_NO_EXTERNAL_AUTHENTICATION",
            "source_manifest": source_pin, "campaign": campaign_pin,
            "pair_fingerprint_sha256": fingerprint,
            "source_publisher_authenticated": False,
            "protocol_predeclared_before_experiment_authenticated": False,
            "physical_test_data_validated": False,
            "flight_release_authorized": False,
        },
    }
