"""M26.11: verify declared operating envelopes and hard component limits.

These are source-byte-linked numerical checks over *operator-provided* limits.
No physical instrument, model validity range or component rating is certified.
Known hard-limit exceedance is FAIL. Missing coverage or out-of-envelope data
is INCONCLUSIVE, not a silently accepted measurement.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path

from physics.validation.flight_channel_csv import (
    _CHANNEL_UNITS, audit_original_flight_channel_csv,
)
from physics.validation.flight_clock_alignment import _finite
from physics.validation.flight_holdout_preflight import prepare_whole_flight_holdout_manifest
from physics.validation.frozen_flight_comparison import _csv_rows
from physics.validation.native_flight_archive import _file

_LIMIT_FIELDS = {
    "operating_regime_id", "channel", "envelope_min", "envelope_max",
    "hard_limit_min", "hard_limit_max", "maximum_original_time_gap_s",
    "limit_source",
}


def screen_flight_hard_limits(
    root: str | Path, manifest: Mapping, *,
    holdout_case: Mapping,
    required_limits: Sequence[Mapping],
    observed_source_paths: Sequence[str],
) -> dict:
    """Screen every *provided* heldout CSV; never auto-infer absent channels."""
    if isinstance(required_limits, (str, bytes)) or not isinstance(required_limits, Sequence) or not 1 <= len(required_limits) <= 100:
        raise ValueError("1..100 exact regime-specific limit declarations required")
    if isinstance(observed_source_paths, (str, bytes)) or not isinstance(observed_source_paths, Sequence) or not 1 <= len(observed_source_paths) <= 500:
        raise ValueError("1..500 exact original observation source paths required")
    limits = {}
    for item in required_limits:
        if not isinstance(item, Mapping) or set(item) != _LIMIT_FIELDS:
            raise ValueError("each hard-limit declaration requires exact fields")
        regime, channel = item["operating_regime_id"], item["channel"]
        if not isinstance(regime, str) or not regime or len(regime) > 100 or channel not in _CHANNEL_UNITS:
            raise ValueError("unsupported regime or measurement channel")
        key = (regime, channel)
        if key in limits:
            raise ValueError("duplicate hard-limit regime/channel declaration")
        nums = {name: _finite(item[name], name) for name in (
            "envelope_min", "envelope_max", "hard_limit_min", "hard_limit_max",
        )}
        if not nums["hard_limit_min"] <= nums["envelope_min"] <= nums["envelope_max"] <= nums["hard_limit_max"]:
            raise ValueError("supported envelope must be inside declared physical hard limits")
        gap = _finite(item["maximum_original_time_gap_s"], "maximum_original_time_gap_s", nonnegative=True)
        if not 0 < gap <= 3600:
            raise ValueError("maximum original time gap must be >0 and <=3600 seconds")
        source = item["limit_source"]
        if not isinstance(source, str) or not source.strip() or len(source) > 500:
            raise ValueError("nonempty operator limit_source required")
        limits[key] = (nums, gap, source.strip())
    split = prepare_whole_flight_holdout_manifest(root, manifest, **holdout_case)
    partitions = {p["flight_id"]: p for p in split["partitions"]}
    native = {f["relative_path"]: f for f in manifest["files"]}
    records, used = [], set()
    for path in observed_source_paths:
        if not isinstance(path, str) or path in used or path not in native:
            raise ValueError("each original path must exist and be unique")
        used.add(path)
        f = native[path]
        part = partitions[f["flight_id"]]
        if part["partition"] != "holdout":
            raise ValueError("hard-limit evidence cannot use calibration flights")
        channels = f["declared_channels"]
        if not isinstance(channels, list) or len(channels) != 1:
            raise ValueError("exact single channel original CSV required")
        channel = channels[0]
        key = (part["operating_regime_id"], channel)
        if key not in limits:
            raise ValueError("original observation has no declared physical limit")
        nums, gap, source = limits[key]
        screened = audit_original_flight_channel_csv(
            root, manifest, relative_path=path,
            channels_with_units={channel: _CHANNEL_UNITS[channel]},
            maximum_declared_sample_gap_s=gap,
        )
        original_bytes = _file(Path(root), path).read_bytes()
        if len(original_bytes) != f["original_byte_count"] or sha256(original_bytes).hexdigest() != f["original_sha256"]:
            raise ValueError("original flight CSV changed since byte integrity audit")
        rows = _csv_rows(original_bytes, ["t_s", channel], "hard-limit measured original")
        low = min(row[1] for row in rows)
        high = max(row[1] for row in rows)
        hard_exceeded = low < nums["hard_limit_min"] or high > nums["hard_limit_max"]
        outside = (low < nums["envelope_min"] or high > nums["envelope_max"]
                   or not screened["within_operator_declared_time_gap"])
        records.append({
            "flight_id": f["flight_id"],
            "experimental_group_id": part["experimental_group_id"],
            "operating_regime_id": key[0], "channel": channel,
            "unit": _CHANNEL_UNITS[channel], "original_source_sha256": f["original_sha256"],
            "observed_minimum": low, "observed_maximum": high,
            "sample_count": len(rows),
            "hard_limit_exceeded": hard_exceeded,
            "out_of_validated_envelope_or_sampling": outside,
            "declared_limits": nums,
            "limit_source_operator_claimed": source,
        })
    missing = sorted(
        f"{regime}/{channel}"
        for regime, channel in limits
        if not any(r["operating_regime_id"] == regime and r["channel"] == channel for r in records)
    )
    any_failed = any(r["hard_limit_exceeded"] for r in records)
    any_outside = any(r["out_of_validated_envelope_or_sampling"] for r in records)
    status = ("FAIL_DECLARED_PHYSICAL_HARD_LIMIT_EXCEEDED" if any_failed
              else "INCONCLUSIVE_OUT_OF_DECLARED_OPERATING_ENVELOPE_OR_MISSING" if any_outside or missing
              else "WITHIN_OPERATOR_DECLARED_LIMITS_UNAUTHENTICATED")
    stable = {"split": split["canonical_split_sha256"],
              "required_limits": [dict(limits[key][0], operating_regime_id=key[0],
                                       channel=key[1], maximum_original_time_gap_s=limits[key][1],
                                       limit_source=limits[key][2]) for key in sorted(limits)],
              "observations": sorted(records, key=lambda x: (x["flight_id"], x["channel"]))}
    digest = hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {
        "status": status, "canonical_hard_limit_report_sha256": digest,
        "canonical_split_sha256": split["canonical_split_sha256"],
        "screened_observations": stable["observations"],
        "missing_declared_regime_channels": missing,
        "any_declared_hard_limit_exceeded": any_failed,
        "all_screened_cases_within_declared_envelope": not any_outside and not missing,
        "hard_limits_and_installed_component_identity_independently_verified": False,
        "original_physical_measurements_authenticated": False,
        "airworthiness_or_flight_release_authorized": False,
    }
