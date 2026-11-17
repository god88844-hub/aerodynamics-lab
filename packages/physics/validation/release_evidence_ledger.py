"""M29.2 deterministic, audit-friendly release evidence index.

This ledger captures the operator's own evidence inventory without asserting
that the supplied metadata, file digests, tests or sources were independently
authenticated. Release readiness remains explicitly unproven.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_ALLOWED_ROLES = {"calibration", "holdout"}
_ALLOWED_KINDS = {"synthetic_fixture", "software_verification", "reported_physical_measurements"}


def _id(value: object, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name}: 1–100 ASCII identifier characters required")
    return value


def _sha(value: object, name: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValueError(f"{name}: invalid lowercase digest")
    return value


def index_release_evidence(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    frozen_design_sha256: str,
    sources: Sequence[Mapping],
) -> dict:
    """Freeze a deterministic source inventory and enumerate remaining blockers.

    Source required keys:
      evidence_id, experiment_id, group_id, channel, role, source_kind,
      source_sha256, source_reference, frozen_model_git_sha,
      frozen_protocol_sha256, frozen_design_sha256.

    This does not read the underlying original measurement bytes. The source
    strings, all raw-file hashes and calibration roles are operator claims.
    """
    model = _sha(frozen_model_git_sha, "frozen_model_git_sha", _SHA1)
    protocol = _sha(frozen_protocol_sha256, "frozen_protocol_sha256", _SHA256)
    design = _sha(frozen_design_sha256, "frozen_design_sha256", _SHA256)
    if isinstance(sources, (str, bytes)) or not isinstance(sources, Sequence):
        raise ValueError("sources must be an explicit sequence")
    if not 1 <= len(sources) <= 200:
        raise ValueError("source inventory must contain 1–200 entries")
    normalized = []
    seen_ids = set()
    seen_hashes = set()
    partitions: dict[str, set[str]] = {"calibration": set(), "holdout": set()}
    blockers = []
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("source item must be a mapping")
        permitted = {
            "evidence_id", "experiment_id", "group_id", "channel", "role",
            "source_kind", "source_sha256", "source_reference",
            "frozen_model_git_sha", "frozen_protocol_sha256",
            "frozen_design_sha256",
        }
        if set(source) != permitted:
            raise ValueError("source item must contain exact required fields, no extraneous claims")
        eid = _id(source["evidence_id"], "evidence_id")
        experiment = _id(source["experiment_id"], "experiment_id")
        group = _id(source["group_id"], "group_id")
        channel = _id(source["channel"], "channel")
        role = source["role"]
        kind = source["source_kind"]
        if role not in _ALLOWED_ROLES or kind not in _ALLOWED_KINDS:
            raise ValueError("unsupported role or source kind")
        original = _sha(source["source_sha256"], "original source_sha256", _SHA256)
        reference = source["source_reference"]
        if not isinstance(reference, str) or not 1 <= len(reference.strip()) <= 500:
            raise ValueError("original source reference required")
        if (source["frozen_model_git_sha"] != model
                or source["frozen_protocol_sha256"] != protocol
                or source["frozen_design_sha256"] != design):
            raise ValueError("source uses a different frozen model, protocol or design identity")
        if eid in seen_ids or original in seen_hashes:
            raise ValueError("duplicate evidence ID or reused original source digest")
        seen_ids.add(eid)
        seen_hashes.add(original)
        partitions[role].add(group)
        normalized.append({
            "evidence_id": eid, "experiment_id": experiment, "group_id": group,
            "channel": channel, "role": role, "source_kind": kind,
            "source_sha256_operator_supplied": original,
            "source_reference_operator_supplied": reference.strip(),
        })
        if kind != "reported_physical_measurements":
            blockers.append(f"{eid}: synthetic or software check, not physical test evidence")
    if partitions["calibration"].intersection(partitions["holdout"]):
        blockers.append("calibration and holdout physical group IDs overlap")
    if not partitions["calibration"]:
        blockers.append("no registered calibration group")
    if len(partitions["holdout"]) < 2:
        blockers.append("fewer than two whole-experiment blind holdout groups")
    if not any(item["source_kind"] == "reported_physical_measurements" for item in normalized):
        blockers.append("no operator-reported physical recordings")
    normalized.sort(key=lambda item: item["evidence_id"])
    canonical = {
        "schema_version": "1.0",
        "model": model, "protocol": protocol, "design": design,
        "sources": normalized,
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    inventory_sha256 = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    blockers += [
        "Original source hashes/bytes have not been checked by this index",
        "Physical origin, calibration certificates and custody were not authenticated",
        "Precommit timing, exact hardware identity and independent reviewer approval remain unverified",
        "No verified independent full-aircraft prediction-error decision equivalence",
    ]
    return {
        "status": ("OPERATOR_EVIDENCE_INVENTORY_HAS_GAPS"
                   if any("no registered" in b or "fewer than" in b or "overlap" in b
                          or "no operator" in b or "synthetic" in b for b in blockers)
                   else "OPERATOR_EVIDENCE_INDEX_COMPLETE_NOT_VALIDATED"),
        "canonical_inventory_sha256": inventory_sha256,
        "canonical_inventory": canonical,
        "calibration_group_count": len(partitions["calibration"]),
        "holdout_group_count": len(partitions["holdout"]),
        "blockers": blockers,
        "source_bytes_cryptographically_checked": False,
        "external_measurement_origin_authenticated": False,
        "release_physical_decision_equivalence_established": False,
        "flightworthiness_established": False,
        "release_authorized": False,
        "note": "A self-consistent source ledger is reproducible metadata, not independent physical evidence.",
    }
