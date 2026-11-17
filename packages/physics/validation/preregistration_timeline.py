"""M27.5 deterministic review of DECLARED preregistration/freeze/experiment chronology.

UTC timestamps and receipts are operator declarations. Their correct ordering
does not prove preregistration was made at that time or an experiment occurred.
"""
from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Mapping, Sequence
import re

_SHA1 = re.compile(r"^[a-f0-9]{40}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _utc(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        raise ValueError(f"{name}: exact UTC RFC3339 seconds with Z required")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{name}: invalid UTC date/time") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError(f"{name}: noncanonical UTC timestamp")
    return parsed


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name}: invalid identifier")
    return value


def _entries(values: object, *, role: str) -> list[dict]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{role}: explicit experiment records required")
    if not 1 <= len(values) <= 60:
        raise ValueError(f"{role}: 1–60 whole experiment records required")
    seen_ids, seen_groups = set(), set()
    rows = []
    for item in values:
        if not isinstance(item, Mapping) or set(item) != {"run_id", "group_id", "started_at_utc", "completed_at_utc"}:
            raise ValueError(f"{role}: exact experiment fields required")
        run = _identifier(item["run_id"], "run_id")
        group = _identifier(item["group_id"], "group_id")
        if run in seen_ids or group in seen_groups:
            raise ValueError(f"{role}: duplicate run ID or whole experiment group")
        seen_ids.add(run)
        seen_groups.add(group)
        started = _utc(item["started_at_utc"], f"{run}.started_at_utc")
        completed = _utc(item["completed_at_utc"], f"{run}.completed_at_utc")
        if started >= completed:
            raise ValueError(f"{role}/{run}: experiment start must precede completion")
        rows.append(dict(run_id=run, group_id=group, start=started, end=completed))
    return rows


def audit_declared_preregistration_sequence(
    *,
    provenance_report: Mapping,
    freeze_manifest: Mapping,
    calibration_records: Sequence[Mapping],
    holdout_records: Sequence[Mapping],
) -> dict:
    """Validate internal temporal sequence and exact M27.4 group/run linkages.

    Does not connect to immutable archives, independently verified signers,
    CI providers, hardware clocks or third-party acquisition equipment.
    """
    if not isinstance(provenance_report, Mapping) or not isinstance(freeze_manifest, Mapping):
        raise ValueError("provenance report and freeze manifest must be objects")
    freeze_keys = {
        "frozen_model_git_sha", "frozen_protocol_sha256",
        "protocol_archived_at_utc", "model_frozen_at_utc",
        "predictions_frozen_at_utc", "claimed_archive_reference",
    }
    if set(freeze_manifest) != freeze_keys:
        raise ValueError("freeze manifest must have exact declared receipt fields")
    model = freeze_manifest["frozen_model_git_sha"]
    protocol = freeze_manifest["frozen_protocol_sha256"]
    if not isinstance(model, str) or not _SHA1.fullmatch(model):
        raise ValueError("invalid frozen model commit")
    if not isinstance(protocol, str) or not _SHA256.fullmatch(protocol):
        raise ValueError("invalid frozen protocol digest")
    ref = freeze_manifest["claimed_archive_reference"]
    if not isinstance(ref, str) or not 1 <= len(ref.strip()) <= 500:
        raise ValueError("claimed_archive_reference required")
    plan = _utc(freeze_manifest["protocol_archived_at_utc"], "protocol_archived_at_utc")
    model_time = _utc(freeze_manifest["model_frozen_at_utc"], "model_frozen_at_utc")
    preds = _utc(freeze_manifest["predictions_frozen_at_utc"], "predictions_frozen_at_utc")
    calibration = _entries(calibration_records, role="calibration")
    holdouts = _entries(holdout_records, role="holdout")
    if len(holdouts) < 2:
        raise ValueError("at least two distinct whole-experiment holdouts are required")
    if {x["group_id"] for x in calibration} & {x["group_id"] for x in holdouts}:
        raise ValueError("calibration and holdout experimental groups overlap")
    if {x["run_id"] for x in calibration} & {x["run_id"] for x in holdouts}:
        raise ValueError("calibration and holdout run IDs overlap")

    holdout_report = provenance_report.get("holdout_audit")
    links = provenance_report.get("source_bindings")
    if not isinstance(holdout_report, Mapping) or not isinstance(links, list):
        raise ValueError("complete M27.4 provenance bindings required")
    if holdout_report.get("frozen_model_git_sha") != model or holdout_report.get("frozen_protocol_sha256_operator_supplied") != protocol:
        raise ValueError("freeze manifest identifiers differ from original source audit")
    if len(links) != len(holdouts):
        raise ValueError("declared holdouts not fully cross-linked to original-source runs")
    linked_runs = {x.get("run_id") for x in links if isinstance(x, Mapping)}
    if linked_runs != {r["run_id"] for r in holdouts}:
        raise ValueError("declared whole holdout runs differ from frozen source bindings")
    blockers = []
    if not plan <= model_time <= preds:
        blockers.append("Protocol archive, model freeze and prediction freeze reported in invalid order")
    if any(c["end"] > model_time for c in calibration):
        blockers.append("Calibration was reportedly completed after model freeze")
    if any(h["start"] <= preds for h in holdouts):
        blockers.append("A holdout reportedly started before predictions were frozen")
    if provenance_report.get("status") != "ORIGINAL_BYTES_CROSS_LINKED_EXTERNAL_AUTHENTICATION_REQUIRED":
        blockers.append("Linked source audit does not pass reported holdout consistency")
    return {
        "status": ("DECLARED_SEQUENCE_REJECTED" if blockers
                   else "DECLARED_SEQUENCE_CONSISTENT_UNAUTHENTICATED"),
        "frozen_model_git_sha": model,
        "frozen_protocol_sha256": protocol,
        "calibration_group_count": len(calibration),
        "holdout_group_count": len(holdouts),
        "reported_temporal_order_consistent": not blockers,
        "blockers": blockers + [
            "No independently authenticated archive timestamp or sealed prediction source",
            "No trusted sensor clock, physical experiment origin or external preregistration review",
        ],
        "archive_timestamp_authenticated": False,
        "blind_holdout_independence_authenticated": False,
        "actual_physical_validation_established": False,
        "release_authorized": False,
    }
