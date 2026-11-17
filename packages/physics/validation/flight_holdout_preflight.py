"""M26.7 pre-registration and whole-flight split preflight.

This audits only declared source hashes, actual local original bytes and
operator-reported access dates. It does not prove the freeze predated actual
unblinding, that different physical flights occurred, or that true holdouts
were unseen by model developers.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from pathlib import Path

from physics.validation.source_completeness import audit_source_completeness

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_KEYS = {
    "flight_id", "experimental_group_id", "partition", "source_file_sha256",
    "operating_regime_id", "first_revealed_utc",
}


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label}: strict UTC timestamp ending in Z required")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{label}: ISO UTC timestamp required") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{label}: UTC timestamp required")
    return parsed


def prepare_whole_flight_holdout_manifest(
    root: Path | str,
    source_manifest: Mapping,
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    preregistered_utc: str,
    frozen_model_utc: str,
    partitions: Sequence[Mapping],
    minimum_holdout_groups: int = 2,
) -> dict:
    """Require calibration / blind-holdout groups to be separately declared.

    The output is a reproducible checksum of reported split decisions,
    NEVER a certification of their historical truth or model accuracy.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha requires lowercase 40-hex")
    if not isinstance(frozen_protocol_sha256, str) or not _SHA256.fullmatch(frozen_protocol_sha256):
        raise ValueError("frozen_protocol_sha256 requires lowercase 64-hex")
    registration, freeze = _utc(preregistered_utc, "preregistered_utc"), _utc(frozen_model_utc, "frozen_model_utc")
    if registration > freeze:
        raise ValueError("declared protocol preregistration cannot postdate model freeze")
    if type(minimum_holdout_groups) is not int or not 2 <= minimum_holdout_groups <= 50:
        raise ValueError("minimum_holdout_groups must be integer 2..50")
    if isinstance(partitions, (str, bytes)) or not isinstance(partitions, Sequence) or not 3 <= len(partitions) <= 500:
        raise ValueError("3..500 whole flight partition records required")
    inventory = audit_source_completeness(root, source_manifest)
    by_flight: dict[str, set[str]] = {}
    by_digest: dict[str, str] = {}
    for row in source_manifest["files"]:
        by_flight.setdefault(row["flight_id"], set()).add(row["original_sha256"])
        prior = by_digest.setdefault(row["original_sha256"], row["flight_id"])
        if prior != row["flight_id"]:
            raise ValueError("identical original source bytes cannot support distinct flights")

    observed_flights = set()
    calibration_groups, holdout_groups = set(), set()
    normalized = []
    for item in partitions:
        if not isinstance(item, Mapping) or set(item) != _KEYS:
            raise ValueError("exact whole-flight split fields required")
        flight, group, regime = item["flight_id"], item["experimental_group_id"], item["operating_regime_id"]
        if (not isinstance(flight, str) or flight not in by_flight or flight in observed_flights
                or any(not isinstance(s, str) or not _ID.fullmatch(s) for s in (group, regime))):
            raise ValueError("each declared flight must appear exactly once with valid group/regime")
        observed_flights.add(flight)
        part = item["partition"]
        if part not in ("calibration", "holdout"):
            raise ValueError("partition must be calibration or holdout")
        digest = item["source_file_sha256"]
        if not isinstance(digest, str) or digest not in by_flight[flight]:
            raise ValueError("source SHA-256 must correspond to an original declared file for this flight")
        revealed = _utc(item["first_revealed_utc"], "first_revealed_utc")
        if part == "holdout" and revealed <= freeze:
            raise ValueError("reported holdout unblinding must be after the frozen model")
        if part == "holdout" and revealed <= registration:
            raise ValueError("reported holdout unblinding must postdate protocol preregistration")
        (holdout_groups if part == "holdout" else calibration_groups).add(group)
        normalized.append({
            "flight_id": flight, "experimental_group_id": group,
            "partition": part, "source_file_sha256": digest,
            "operating_regime_id": regime, "first_revealed_utc": item["first_revealed_utc"],
        })
    if observed_flights != set(by_flight):
        raise ValueError("all declared original flight IDs need an explicit partition")
    if calibration_groups & holdout_groups:
        raise ValueError("same whole experimental group cannot enter calibration and holdout")
    if not calibration_groups or len(holdout_groups) < minimum_holdout_groups:
        raise ValueError("at least one calibration group and requested independent holdout groups required")
    normalized.sort(key=lambda x: x["flight_id"])
    canonical = {
        "archive_inventory_sha256": inventory["canonical_file_inventory_sha256"],
        "model_git_sha": frozen_model_git_sha,
        "protocol_sha256": frozen_protocol_sha256,
        "preregistered_utc": preregistered_utc,
        "frozen_model_utc": frozen_model_utc,
        "partitions": normalized,
    }
    digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {
        "status": "SELF_REPORTED_WHOLE_FLIGHT_SPLIT_CONSISTENT_NOT_AUTHENTICATED",
        "canonical_split_sha256": digest,
        "original_archive_inventory_sha256": inventory["canonical_file_inventory_sha256"],
        "calibration_group_ids": sorted(calibration_groups),
        "holdout_group_ids": sorted(holdout_groups),
        "declared_flight_count": len(observed_flights),
        "partitions": normalized,
        "frozen_timestamps_independently_authenticated": False,
        "holdout_reveal_times_independently_authenticated": False,
        "whole_experiment_independence_physically_verified": False,
        "actual_independent_prediction_validation_completed": False,
        "physical_release_authorized": False,
    }
