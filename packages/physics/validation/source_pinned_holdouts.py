"""M27.2: hash-pinned paired prediction/observation holdout CSV gate.

Validates supplied original bytes against supplied hashes and aligns samples
without interpolation. Source labels/permissions do NOT authenticate a real
experiment or independent calibration, nor prove preregistration timing.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import math
import re
from collections.abc import Mapping, Sequence

from physics.validation.holdout_intervals import audit_heldout_intervals

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_OBS_HEADER = ("sample_id", "t_s", "observed", "measurement_hard_bound")
_PRED_HEADER = ("sample_id", "t_s", "prediction", "lower", "upper")
MAX_ORIGINAL_BYTES = 1_000_000
MAX_ROWS = 5000


def _field_number(value: str, label: str, *, minimum_zero: bool = False) -> float:
    if not value or not value.strip():
        raise ValueError(f"{label}: empty numeric field")
    try:
        v = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{label}: invalid number") from exc
    if not math.isfinite(v) or (minimum_zero and v < 0):
        raise ValueError(f"{label}: nonfinite or negative number")
    return v


def _read_original_csv(raw: object, digest: object, header: tuple[str, ...], label: str) -> list[dict]:
    if not isinstance(raw, str):
        raise ValueError(f"{label}: original UTF-8 CSV text required")
    original = raw.encode("utf-8")
    if not 1 <= len(original) <= MAX_ORIGINAL_BYTES:
        raise ValueError(f"{label}: original source byte limit exceeded")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ValueError(f"{label}: expected lower-case SHA-256 digest required")
    if sha256(original).hexdigest() != digest:
        raise ValueError(f"{label}: original byte digest mismatch")
    try:
        rows = csv.reader(io.StringIO(raw, newline=""), strict=True)
        if tuple(next(rows, [])) != header:
            raise ValueError(f"{label}: exact original CSV header required")
        out: list[dict] = []
        seen = set()
        last_t = None
        for k, fields in enumerate(rows):
            if len(fields) != len(header):
                raise ValueError(f"{label}: row {k + 2}: wrong column count")
            sid = fields[0]
            if not _ID.fullmatch(sid) or sid in seen:
                raise ValueError(f"{label}: invalid or duplicate sample_id")
            seen.add(sid)
            values = {
                name: _field_number(raw_value, f"{label}/{sid}/{name}",
                                    minimum_zero=(name in ("t_s", "measurement_hard_bound")))
                for name, raw_value in zip(header[1:], fields[1:])
            }
            t = values["t_s"]
            if (last_t is None and t != 0) or (last_t is not None and t <= last_t):
                raise ValueError(f"{label}: timestamp sequence must start at zero and strictly increase")
            last_t = t
            out.append({"sample_id": sid, **values})
            if len(out) > MAX_ROWS:
                raise ValueError(f"{label}: too many original rows")
    except csv.Error as exc:
        raise ValueError(f"{label}: malformed CSV") from exc
    if len(out) < 5:
        raise ValueError(f"{label}: at least five measurements required")
    return out


def audit_source_pinned_holdouts(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    channel: str,
    maximum_absolute_error: float,
    minimum_robust_coverage_fraction: float,
    calibration_group_ids: Sequence[str],
    runs: Sequence[Mapping],
) -> dict:
    """Read-only exact-byte checks before running the M27.1 error audit.

    Each run supplies metadata and:
      observed_csv, observed_sha256, prediction_csv, prediction_sha256
    Both CSVs use exact SI time seconds and one row per aligned sample.
    Prediction and observation files must differ and must be disjoint
    across holdout runs; no interpolation, filling or clock alignment occurs.
    """
    if isinstance(runs, (str, bytes)) or not isinstance(runs, Sequence):
        raise ValueError("runs must be a sequence")
    if not 2 <= len(runs) <= 60:
        raise ValueError("2–60 independent holdout runs required")
    all_obs_hashes, all_pred_hashes = set(), set()
    records = []
    sources = []
    for run in runs:
        if not isinstance(run, Mapping):
            raise ValueError("run must be an object with original source files")
        run_id = run.get("run_id")
        if not isinstance(run_id, str) or not _ID.fullmatch(run_id):
            raise ValueError("invalid run_id")
        obs_digest = run.get("observed_sha256")
        pred_digest = run.get("prediction_sha256")
        observed = _read_original_csv(run.get("observed_csv"), obs_digest, _OBS_HEADER,
                                      f"{run_id}/observations")
        predictions = _read_original_csv(run.get("prediction_csv"), pred_digest, _PRED_HEADER,
                                         f"{run_id}/predictions")
        if obs_digest == pred_digest or obs_digest in all_obs_hashes or pred_digest in all_pred_hashes:
            raise ValueError("reused or identical original prediction/observation source bytes")
        # Reject observations reused as predictions anywhere in the campaign,
        # not just where the two files belong to the same experiment.
        all_obs_hashes.add(obs_digest)
        all_pred_hashes.add(pred_digest)
        if len(observed) != len(predictions):
            raise ValueError(f"{run_id}: prediction/observation row count mismatch")
        samples = []
        for o, p in zip(observed, predictions):
            if o["sample_id"] != p["sample_id"] or o["t_s"] != p["t_s"]:
                raise ValueError(f"{run_id}: sample IDs/time grids differ; no implicit clock shifting")
            samples.append({
                "sample_id": f"{run_id}.{o['sample_id']}",
                "prediction": p["prediction"], "lower": p["lower"], "upper": p["upper"],
                "observed": o["observed"],
                "measurement_hard_bound": o["measurement_hard_bound"],
            })
        records.append({
            "run_id": run_id,
            "group_id": run.get("group_id"),
            "source_sha256": obs_digest,
            "dataset_kind": run.get("dataset_kind"),
            "hardware_match": run.get("hardware_match"),
            "unused_for_calibration": run.get("unused_for_calibration"),
            "samples": samples,
        })
        sources.append({
            "run_id": run_id,
            "original_observations_digest_checked": obs_digest,
            "original_predictions_digest_checked": pred_digest,
            "row_count": len(samples),
            "actual_physical_provenance_authenticated": False,
        })
    if all_obs_hashes.intersection(all_pred_hashes):
        raise ValueError("observation data reused as frozen predictions in another run")
    report = audit_heldout_intervals(
        frozen_model_git_sha=frozen_model_git_sha,
        frozen_protocol_sha256=frozen_protocol_sha256,
        channel=channel, maximum_absolute_error=maximum_absolute_error,
        minimum_robust_coverage_fraction=minimum_robust_coverage_fraction,
        calibration_group_ids=calibration_group_ids,
        holdout_runs=records,
    )
    return {
        **report,
        "original_source_digest_checks": sources,
        "source_bytes_integrity_verified_against_operator_supplied_digests": True,
        "source_identity_or_preregistration_externally_authenticated": False,
        "actual_independent_physical_validation_established": False,
        "decision_equivalent_to_physical_testing": False,
    }
