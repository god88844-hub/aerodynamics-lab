"""M27.10: exact-original-byte source gate before affine ADC holdout comparison.

Checks supplied bytes against supplied SHA-256 and freezes original sample order.
The claimed digest and observation origin are still operator-controlled: no
certificate, independent timestamp or physical acquisition is authenticated.
"""
from __future__ import annotations

import csv
from hashlib import sha256
import io
import math
import re
from collections.abc import Mapping, Sequence

from physics.validation.affine_adc_holdout import audit_affine_sensor_holdouts

_OBS = ("sample_id", "t_s", "raw_code", "saturated")
_PRED = ("sample_id", "t_s", "prediction", "lower", "upper")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_INT = re.compile(r"^[0-9]{1,12}$")
_MAX_BYTES = 1_000_000
_MAX_SAMPLES = 5000


def _original_rows(raw: object, digest: object, header: tuple[str, ...], label: str) -> list[dict]:
    if not isinstance(raw, str) or not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ValueError(f"{label}: original CSV and lowercase claimed SHA-256 required")
    try:
        data = raw.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError(f"{label}: valid original UTF-8 CSV text required") from exc
    if not 1 <= len(data) <= _MAX_BYTES:
        raise ValueError(f"{label}: source byte count outside 1–1000000")
    if sha256(data).hexdigest() != digest:
        raise ValueError(f"{label}: original source SHA-256 digest mismatch")
    try:
        stream = csv.reader(io.StringIO(raw, newline=""), strict=True)
        if tuple(next(stream, ())) != header:
            raise ValueError(f"{label}: exact CSV header and column order required")
        rows = []
        seen = set()
        previous = -1.0
        for values in stream:
            if len(values) != len(header):
                raise ValueError(f"{label}: wrong original field count")
            sid = values[0]
            if not _ID.fullmatch(sid) or sid in seen:
                raise ValueError(f"{label}: invalid or duplicated sample ID")
            seen.add(sid)
            try:
                t = float(values[1])
            except (ValueError, OverflowError) as exc:
                raise ValueError(f"{label}: invalid original sample time") from exc
            if not math.isfinite(t) or t <= previous or (not rows and t != 0):
                raise ValueError(f"{label}: time must start at zero and strictly increase")
            previous = t
            row = {"sample_id": sid, "time_s": t}
            if header == _OBS:
                if not _INT.fullmatch(values[2]):
                    raise ValueError(f"{label}: raw ADC count must be an unsigned integer string")
                raw_code = int(values[2])
                if raw_code > 2**32-1:
                    raise ValueError(f"{label}: raw ADC count outside uint32")
                if values[3] not in ("0", "1"):
                    raise ValueError(f"{label}: saturated field must be 0 or 1")
                row.update(raw_code=raw_code, saturated=(values[3] == "1"))
            else:
                numbers = []
                for value in values[2:]:
                    try:
                        number = float(value)
                    except (ValueError, OverflowError) as exc:
                        raise ValueError(f"{label}: invalid frozen prediction number") from exc
                    if not math.isfinite(number):
                        raise ValueError(f"{label}: nonfinite frozen prediction number")
                    numbers.append(number)
                if numbers[1] > numbers[2]:
                    raise ValueError(f"{label}: reversed frozen prediction bounds")
                row.update(prediction=numbers[0], lower=numbers[1], upper=numbers[2])
            rows.append(row)
            if len(rows) > _MAX_SAMPLES:
                raise ValueError(f"{label}: too many original samples")
        if len(rows) < 5:
            raise ValueError(f"{label}: minimum five original samples required")
        return rows
    except csv.Error as exc:
        raise ValueError(f"{label}: malformed original CSV") from exc


def load_original_adc_sensor_case(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    channel: str,
    calibration: Mapping,
    calibration_source: str,
    maximum_conservative_absolute_residual: float,
    minimum_interval_coverage_fraction: float,
    source_runs: Sequence[Mapping],
) -> tuple[dict, list[dict]]:
    """Prepare M27.9 inputs *only* from precisely hashed original source rows."""
    if isinstance(source_runs, (str, bytes)) or not isinstance(source_runs, Sequence) or not 2 <= len(source_runs) <= 60:
        raise ValueError("2–60 original held-out whole-run source bundles required")
    required = {
        "run_id", "group_id", "original_adc_csv", "original_adc_sha256",
        "frozen_prediction_csv", "frozen_prediction_sha256",
    }
    paired = []
    digests = []
    all_hashes = set()
    for run in source_runs:
        if not isinstance(run, Mapping) or set(run) != required:
            raise ValueError("each original source bundle requires exact IDs, bytes and SHA-256")
        run_id, group_id = run["run_id"], run["group_id"]
        if not isinstance(run_id, str) or not _ID.fullmatch(run_id):
            raise ValueError("invalid original run identifier")
        if not isinstance(group_id, str) or not _ID.fullmatch(group_id):
            raise ValueError("invalid original group identifier")
        obs_sha, pred_sha = run["original_adc_sha256"], run["frozen_prediction_sha256"]
        observed = _original_rows(run["original_adc_csv"], obs_sha, _OBS, f"{run_id}/ADC")
        predicted = _original_rows(run["frozen_prediction_csv"], pred_sha, _PRED, f"{run_id}/frozen")
        if obs_sha in all_hashes or pred_sha in all_hashes or obs_sha == pred_sha:
            raise ValueError("duplicate or reused original source digest across independent runs")
        all_hashes.update((obs_sha, pred_sha))
        if len(observed) != len(predicted):
            raise ValueError(f"{run_id}: unmatched ADC and frozen prediction row counts")
        samples = []
        for a, b in zip(observed, predicted):
            if a["sample_id"] != b["sample_id"] or a["time_s"] != b["time_s"]:
                raise ValueError(f"{run_id}: original sample ID/time grids differ; no interpolation")
            samples.append({**a, "prediction": b["prediction"], "lower": b["lower"], "upper": b["upper"]})
        paired.append({"run_id": run_id, "group_id": group_id, "samples": samples})
        digests.append({
            "run_id": run_id, "group_id": group_id,
            "original_adc_sha256": obs_sha, "frozen_prediction_sha256": pred_sha,
            "sample_count": len(samples),
        })
    prepared = {
        "frozen_model_git_sha": frozen_model_git_sha,
        "frozen_protocol_sha256": frozen_protocol_sha256,
        "channel": channel, "calibration": calibration,
        "calibration_source": calibration_source,
        "maximum_conservative_absolute_residual": maximum_conservative_absolute_residual,
        "minimum_interval_coverage_fraction": minimum_interval_coverage_fraction,
        "holdout_runs": paired,
    }
    return prepared, sorted(digests, key=lambda x: x["run_id"])


def audit_original_adc_holdout_sources(**kwargs) -> dict:
    prepared, source_digests = load_original_adc_sensor_case(**kwargs)
    report = audit_affine_sensor_holdouts(**prepared)
    return {
        "status": (
            "ORIGINAL_ADC_SOURCES_MATCH_OPERATOR_HASHES_NUMERICALLY_CONSISTENT_UNAUTHENTICATED"
            if report["all_declared_holdout_analytical_gates_passed"]
            else "ORIGINAL_ADC_SOURCE_NUMERIC_GATE_FAILED"
        ),
        "source_digests_checked": source_digests,
        "original_bytes_hashed_against_supplied_sha256": True,
        "calibrated_holdout_report": report,
        "independent_source_custody_authenticated": False,
        "physical_instrument_calibration_authenticated": False,
        "independent_real_world_prediction_validated": False,
        "manufacturing_or_flight_release_authorized": False,
    }
