"""M26.34: original-byte-recomputed M300 per-flight frozen energy holdout.

This is an empirical *source-specific* numerical evaluation only once the
actual provider-MD5-matching CSV is obtained. It is NOT a validation of the
AeroForge hexacopter or of independently calibrated M300 measurements.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math
import re

from physics.validation.m300_original_energy import (
    analyse_m300_original_energy, _bounded, _decimal,
)

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_GIT = re.compile(r"^[a-f0-9]{40}$")
_PROTOCOL_KEYS = {
    "frozen_model_git_sha", "frozen_protocol_sha256", "preregistered_utc",
    "frozen_model_utc", "partitions", "maximum_abs_energy_error_wh",
    "measurement_hard_error_wh", "minimum_robust_interval_coverage_fraction",
    "minimum_distinct_holdout_groups",
}
_PARTITION_KEYS = {"uid", "group_id", "partition", "first_revealed_utc"}
_PREDICTION_KEYS = {"uid", "predicted_wh", "lower_wh", "upper_wh"}


def _utc(value, label):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{label}: UTC ISO8601 ending in Z required")
    try:
        date = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{label}: invalid ISO UTC") from exc
    if date.tzinfo != timezone.utc:
        raise ValueError(f"{label}: UTC timezone required")
    return date


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate frozen prediction JSON key: {key}")
        obj[key] = value
    return obj


def _no_constant(value):
    raise ValueError("frozen prediction JSON rejects NaN/Infinity")


def score_frozen_m300_energy(
    original_csv_path, acquisition_receipt: Mapping, *,
    mapping: Mapping, protocol: Mapping,
    frozen_prediction_json_path, frozen_prediction_sha256: str,
) -> dict:
    """Read original bytes and frozen model output; never trust claimed pass flags."""
    if not isinstance(protocol, Mapping) or set(protocol) != _PROTOCOL_KEYS:
        raise ValueError("exact predeclared holdout energy protocol required")
    git, phash = protocol["frozen_model_git_sha"], protocol["frozen_protocol_sha256"]
    if not isinstance(git, str) or not _GIT.fullmatch(git):
        raise ValueError("frozen model Git SHA must be lowercase 40-hex")
    if not isinstance(phash, str) or not _SHA256.fullmatch(phash):
        raise ValueError("frozen protocol SHA256 must be lowercase 64-hex")
    registered = _utc(protocol["preregistered_utc"], "preregistered_utc")
    freeze = _utc(protocol["frozen_model_utc"], "frozen_model_utc")
    if registered > freeze:
        raise ValueError("reported preregistration cannot postdate reported model freeze")
    if (type(protocol["minimum_distinct_holdout_groups"]) is not int
            or not 2 <= protocol["minimum_distinct_holdout_groups"] <= 50):
        raise ValueError("minimum distinct holdout groups must be integer 2..50")
    allowed = _bounded(protocol["maximum_abs_energy_error_wh"], "absolute energy tolerance", maximum="1000000", positive=True)
    m_error = _bounded(protocol["measurement_hard_error_wh"], "energy measurement hard error", maximum="1000000")
    cmin = _bounded(protocol["minimum_robust_interval_coverage_fraction"], "required robust coverage", maximum="1")
    # Recompute and rehash all physical source bytes rather than accepting a
    # caller-supplied green scan report.
    evidence = analyse_m300_original_energy(
        original_csv_path, acquisition_receipt, mapping=mapping,
    )
    source = {row["uid"]: row for row in evidence["recordings"]}
    partitions = protocol["partitions"]
    if isinstance(partitions, (str, bytes)) or not isinstance(partitions, Sequence) or not 3 <= len(partitions) <= 2000:
        raise ValueError("three or more exact whole-flight split records required")
    by_uid, cal_groups, heldout_groups = {}, set(), set()
    for row in partitions:
        if not isinstance(row, Mapping) or set(row) != _PARTITION_KEYS:
            raise ValueError("exact per-flight partition fields required")
        uid, group, assignment = row["uid"], row["group_id"], row["partition"]
        if (not isinstance(uid, str) or uid not in source or uid in by_uid
                or not isinstance(group, str) or not 1 <= len(group) <= 100
                or assignment not in ("calibration", "holdout")):
            raise ValueError("each observed UID requires one valid partition/group")
        reveal = _utc(row["first_revealed_utc"], "first_revealed_utc")
        if assignment == "holdout" and reveal <= freeze:
            raise ValueError("reported holdout reveal must postdate model freeze")
        (heldout_groups if assignment == "holdout" else cal_groups).add(group)
        by_uid[uid] = {"group": group, "partition": assignment}
    if set(by_uid) != set(source):
        raise ValueError("every observed source UID must have a declared partition")
    if cal_groups & heldout_groups or not cal_groups:
        raise ValueError("calibration and holdout groups must be disjoint, calibration nonempty")

    path = Path(frozen_prediction_json_path)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise ValueError("frozen prediction must be an existing nonsymlink JSON file")
    if path.resolve(strict=True) == Path(original_csv_path).resolve(strict=True):
        raise ValueError("frozen predictions must not replace original telemetry")
    if not isinstance(frozen_prediction_sha256, str) or not _SHA256.fullmatch(frozen_prediction_sha256):
        raise ValueError("frozen prediction artifact SHA256 must be lowercase 64-hex")
    if not 0 < path.stat().st_size <= 2_000_000:
        raise ValueError("frozen predictions JSON size outside bounded reader")
    data = path.read_bytes()
    if sha256(data).hexdigest() != frozen_prediction_sha256:
        raise ValueError("frozen prediction artifact SHA256 mismatch")
    try:
        obj = json.loads(
            data.decode("utf-8", "strict"), object_pairs_hook=_unique_pairs,
            parse_constant=_no_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("frozen predictions JSON malformed") from exc
    if not isinstance(obj, dict) or set(obj) != {"predictions"} or not isinstance(obj["predictions"], list):
        raise ValueError("frozen predictions must have one exact predictions array")
    predicted = {}
    for row in obj["predictions"]:
        if not isinstance(row, Mapping) or set(row) != _PREDICTION_KEYS:
            raise ValueError("exact per-UID frozen energy prediction required")
        uid = row["uid"]
        if (not isinstance(uid, str) or uid not in source or uid in predicted
                or by_uid[uid]["partition"] != "holdout"):
            raise ValueError("predictions must uniquely target declared heldout source UIDs")
        value = _bounded(row["predicted_wh"], "predicted_wh", maximum="1000000")
        lower = _bounded(row["lower_wh"], "lower_wh", maximum="1000000")
        upper = _bounded(row["upper_wh"], "upper_wh", maximum="1000000")
        if not lower <= value <= upper:
            raise ValueError("frozen prediction interval must enclose predicted energy")
        predicted[uid] = (value, lower, upper)
    reports, missing, failures = [], [], []
    for uid in sorted(u for u in by_uid if by_uid[u]["partition"] == "holdout"):
        observed = source[uid]
        if not observed["complete_covered_recording_for_numeric_holdout"]:
            missing.append(f"{uid}: incomplete original per-flight time coverage")
            continue
        if uid not in predicted:
            missing.append(f"{uid}: frozen prediction absent")
            continue
        actual = _decimal(observed["battery_terminal_discharge_wh_over_observed_coverage"], "observed original integrated Wh")
        value, low, high = predicted[uid]
        upper_error = abs(actual - value) + m_error
        within_interval = low <= actual - m_error and actual + m_error <= high
        passed = upper_error <= allowed and within_interval
        if not passed:
            failures.append(uid)
        reports.append({
            "uid": uid,
            "reported_experimental_group_id": by_uid[uid]["group"],
            "observed_battery_terminal_discharge_wh": float(actual),
            "frozen_prediction_wh": float(value),
            "conservative_abs_error_wh": float(upper_error),
            "robust_interval_contains_observed_measurement_bound": bool(within_interval),
            "declared_numeric_gates_passed": bool(passed),
        })
    tested_groups = {r["reported_experimental_group_id"] for r in reports}
    passing_groups = {r["reported_experimental_group_id"] for r in reports if r["declared_numeric_gates_passed"]}
    if failures:
        status = "FAIL_FROZEN_M300_SOURCE_SPECIFIC_ENERGY_GATE"
    elif (missing or len(tested_groups) < protocol["minimum_distinct_holdout_groups"]
          or len(passing_groups) < protocol["minimum_distinct_holdout_groups"]):
        status = "INCONCLUSIVE_M300_FROZEN_ENERGY_HOLDOUT_COVERAGE"
    else:
        status = "CONDITIONAL_M300_DATASET_ENERGY_AGREEMENT_UNAUTHENTICATED"
    canonical = {
        "source_sha256": evidence["original_source_sha256"],
        "mapping_sha256": evidence["source_mapping_sha256"],
        "frozen_prediction_sha256": frozen_prediction_sha256,
        "frozen_protocol_claimed": dict(protocol),
        "measurements": evidence["recordings"],
        "results": reports,
        "missing": missing,
        "status": status,
    }
    return {
        "status": status,
        "canonical_analytical_fingerprint_sha256": sha256(json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest(),
        "source_doi": evidence["source_doi"],
        "source_sha256": evidence["original_source_sha256"],
        "source_mapping_sha256": evidence["source_mapping_sha256"],
        "frozen_prediction_sha256": frozen_prediction_sha256,
        "reported_holdout_groups_count": len(heldout_groups),
        "measured_holdout_groups_evaluated": len(tested_groups),
        "missing_or_gapped_holdout_uids": missing,
        "failed_holdout_uids": failures,
        "per_flight_evaluations": reports,
        "source_specific_numeric_gates_passed": status.startswith("CONDITIONAL_"),
        "actual_historical_blind_freeze_authenticated": False,
        "battery_sensor_current_sign_and_accuracy_independently_verified": False,
        "independent_experiment_source_custody_authenticated": False,
        "hardware_compatible_with_60kg_hexacopter": False,
        "aeroforge_full_vehicle_accuracy_validated": False,
        "manufacturing_or_flight_release_authorized": False,
    }
