"""M26.9: compare independently stored frozen predictions with original flight CSV.

Numerical checks are real computations over actual supplied source bytes,
but cannot authenticate physical acquisition, model freeze or true blinding.
No interpolation, missing-value repair or unit conversion is performed.
"""
from __future__ import annotations

import csv
import io
import math
import re
from hashlib import sha256
from pathlib import Path
from collections.abc import Mapping

from physics.validation.flight_channel_csv import (
    audit_original_flight_channel_csv, _CHANNEL_UNITS, _MAX_CSV_BYTES,
)
from physics.validation.flight_holdout_preflight import prepare_whole_flight_holdout_manifest
from physics.validation.flight_clock_alignment import _finite
from physics.validation.native_flight_archive import _file

_SHA = re.compile(r"^[a-f0-9]{64}$")


def _csv_rows(data: bytes, header: list[str], label: str) -> list[list[float]]:
    try:
        s = data.decode("utf-8", "strict")
        if s.startswith("\ufeff"):
            raise ValueError(f"{label}: unexpected BOM")
        rows = csv.reader(io.StringIO(s, newline=""), strict=True)
        if next(rows, None) != header:
            raise ValueError(f"{label}: exact CSV header required")
        result = []
        previous = None
        for row in rows:
            if len(row) != len(header) or any(not cell.strip() for cell in row):
                raise ValueError(f"{label}: original sample has blank/extra columns")
            try:
                numbers = [float(cell) for cell in row]
            except (ValueError, OverflowError) as exc:
                raise ValueError(f"{label}: nonnumeric sample") from exc
            if not all(math.isfinite(x) for x in numbers):
                raise ValueError(f"{label}: nonfinite sample")
            if previous is not None and numbers[0] <= previous:
                raise ValueError(f"{label}: original sample times must strictly increase")
            previous = numbers[0]
            result.append(numbers)
            if len(result) > 50000:
                raise ValueError(f"{label}: maximum 50000 samples")
        if len(result) < 5:
            raise ValueError(f"{label}: minimum five samples required")
        return result
    except (UnicodeError, csv.Error) as exc:
        raise ValueError(f"{label}: malformed source CSV") from exc


def compare_frozen_flight_channel(
    root: Path | str,
    source_manifest: Mapping,
    *,
    holdout_case: Mapping,
    observed_relative_path: str,
    channel: str,
    frozen_prediction_csv_path: Path | str,
    frozen_prediction_sha256: str,
    maximum_original_time_gap_s: float,
    measurement_hard_error: float,
    numerical_hard_error: float,
    additional_model_discrepancy_hard_error: float,
    predeclared_max_conservative_error: float,
    predeclared_min_robust_interval_coverage: float,
) -> dict:
    """Compute exact holdout residuals, hard-error budget and robust coverage.

    A source is eligible only when a whole-flight preflight assigns it to a
    reported held-out flight. All tolerances are operator-supplied assumptions.
    """
    if not isinstance(channel, str) or channel not in _CHANNEL_UNITS:
        raise ValueError("unsupported measured engineering channel")
    if not isinstance(frozen_prediction_sha256, str) or not _SHA.fullmatch(frozen_prediction_sha256):
        raise ValueError("frozen_prediction_sha256 must be lowercase 64-hex")
    measurement = _finite(measurement_hard_error, "measurement_hard_error", nonnegative=True)
    numerical = _finite(numerical_hard_error, "numerical_hard_error", nonnegative=True)
    discrepancy = _finite(additional_model_discrepancy_hard_error, "additional_model_discrepancy_hard_error", nonnegative=True)
    allowable = _finite(predeclared_max_conservative_error, "predeclared_max_conservative_error", nonnegative=True)
    coverage_limit = _finite(predeclared_min_robust_interval_coverage, "predeclared_min_robust_interval_coverage", nonnegative=True)
    if coverage_limit > 1:
        raise ValueError("predeclared_min_robust_interval_coverage must be <=1")
    total_extra = measurement + numerical + discrepancy
    if not math.isfinite(total_extra):
        raise ValueError("numerical uncertainty accumulation overflow")

    split = prepare_whole_flight_holdout_manifest(root, source_manifest, **holdout_case)
    paths = [r for r in source_manifest["files"] if r["relative_path"] == observed_relative_path]
    if len(paths) != 1 or list(paths[0]["declared_channels"]) != [channel]:
        raise ValueError("one exact declared original single-channel CSV required")
    observed_file = paths[0]
    part = [r for r in split["partitions"] if r["flight_id"] == observed_file["flight_id"]]
    if len(part) != 1 or part[0]["partition"] != "holdout":
        raise ValueError("original measurement must belong to declared frozen whole-flight holdout")
    if observed_file["calibration_reference"] is None or observed_file["clock_reference"] is None:
        raise ValueError("original sensor calibration and clock reference required")
    observed_audit = audit_original_flight_channel_csv(
        root, source_manifest, relative_path=observed_relative_path,
        channels_with_units={channel: _CHANNEL_UNITS[channel]},
        maximum_declared_sample_gap_s=maximum_original_time_gap_s,
    )
    if not observed_audit["within_operator_declared_time_gap"]:
        raise ValueError("measured original time gaps exceed declared maximum")

    src = _file(Path(root), observed_relative_path)
    original_bytes = src.read_bytes()
    if (len(original_bytes) != observed_file["original_byte_count"]
            or sha256(original_bytes).hexdigest() != observed_file["original_sha256"]):
        raise ValueError("original measurement changed after source audit")
    observed = _csv_rows(original_bytes, ["t_s", channel], "measured original")

    prediction_path = Path(frozen_prediction_csv_path)
    if prediction_path.is_symlink() or not prediction_path.is_file():
        raise ValueError("frozen prediction file must be an existing non-symlinked CSV")
    pred_resolved = prediction_path.resolve(strict=True)
    if pred_resolved.is_relative_to(Path(root).resolve(strict=True)):
        raise ValueError("frozen predictions must be stored outside immutable original measurement root")
    if pred_resolved.suffix.lower() != ".csv" or pred_resolved.stat().st_size > _MAX_CSV_BYTES:
        raise ValueError("frozen prediction file requires bounded original CSV bytes")
    pred_bytes = pred_resolved.read_bytes()
    if len(pred_bytes) > _MAX_CSV_BYTES or sha256(pred_bytes).hexdigest() != frozen_prediction_sha256:
        raise ValueError("frozen prediction bytes do not match supplied SHA-256")
    predicted = _csv_rows(pred_bytes, ["t_s", "prediction", "lower", "upper"], "frozen prediction")
    if len(observed) != len(predicted):
        raise ValueError("original observation/prediction sample count mismatch; no interpolation")

    max_cons = 0.
    sq = 0.
    nominal_covered = 0
    robust_covered = 0
    for (t_obs, y), (t_pred, model, lower, upper) in zip(observed, predicted):
        if t_obs != t_pred:
            raise ValueError("original observation/prediction time grids differ; no interpolation")
        if lower > upper or not lower <= model <= upper:
            raise ValueError("frozen prediction bounds reversed or exclude predicted estimate")
        residual = abs(model - y)
        conservative = residual + total_extra
        if not math.isfinite(conservative):
            raise ValueError("conservative residual overflow")
        max_cons = max(max_cons, conservative)
        sq += residual * residual
        nominal_covered += int(lower <= y <= upper)
        robust_covered += int(lower <= y - measurement and y + measurement <= upper)
    n = len(observed)
    robust_fraction = robust_covered / n
    rmse = math.sqrt(sq / n)
    if not math.isfinite(rmse):
        raise ValueError("residual square accumulation overflow")
    passes = max_cons <= allowable and robust_fraction >= coverage_limit
    return {
        "status": ("RECOMPUTED_FROZEN_HOLDOUT_NUMERIC_GATES_PASS_UNAUTHENTICATED"
                   if passes else "FROZEN_HOLDOUT_NUMERIC_GATE_FAILED"),
        "flight_id": observed_file["flight_id"],
        "operating_regime_id": part[0]["operating_regime_id"],
        "experimental_group_id": part[0]["experimental_group_id"],
        "channel": channel, "unit": _CHANNEL_UNITS[channel],
        "measured_original_sha256": observed_file["original_sha256"],
        "frozen_prediction_sha256": frozen_prediction_sha256,
        "canonical_split_sha256": split["canonical_split_sha256"],
        "samples_compared_without_interpolation": n,
        "nominal_interval_coverage_fraction": nominal_covered / n,
        "robust_measurement_interval_coverage_fraction": robust_fraction,
        "nominal_rmse": rmse,
        "maximum_conservative_absolute_residual": max_cons,
        "measurement_hard_error_operator_claimed": measurement,
        "numerical_hard_error_operator_claimed": numerical,
        "model_discrepancy_hard_error_operator_claimed": discrepancy,
        "predeclared_max_conservative_error_operator_claimed": allowable,
        "predeclared_min_robust_coverage_operator_claimed": coverage_limit,
        "analytical_gates_passed": passes,
        "source_file_custody_and_holdout_blinding_authenticated": False,
        "model_freeze_timestamp_authenticated": False,
        "physical_flight_validation_established": False,
        "flight_release_authorized": False,
    }
