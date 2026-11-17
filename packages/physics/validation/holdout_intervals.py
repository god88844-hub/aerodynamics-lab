"""M27.1: conservative holdout interval diagnostics (not physical certification).

A reported measurement y with independently justified absolute instrument error
bound u admits true values in [y-u, y+u]. A prediction interval [lo, hi]
*robustly encloses* the measurement only when the entire error interval fits.
This is intentionally stricter than testing a point observation against a band.

Input hashes and provenance are operator-declared; none proves independent tests.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_MODEL = re.compile(r"^[0-9a-f]{40}$")


def _number(value: object, name: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or (nonnegative and result < 0):
        raise ValueError(f"{name} must be finite" + (" and nonnegative" if nonnegative else ""))
    return result


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 300:
        raise ValueError(f"{name} must be a nonempty identifier/reference")
    return value.strip()


def audit_heldout_intervals(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    channel: str,
    maximum_absolute_error: float,
    minimum_robust_coverage_fraction: float,
    calibration_group_ids: Sequence[str],
    holdout_runs: Sequence[Mapping],
) -> dict:
    """Compare frozen prediction intervals with independently *reported* holdouts.

    Required per run: run_id, group_id, source_sha256, dataset_kind,
    hardware_match, unused_for_calibration, samples. Samples require
    sample_id, prediction, lower, upper, observed, measurement_hard_bound.
    Each complete holdout run must individually satisfy acceptance criteria;
    pooled averages cannot mask one failing operating regime.
    """
    if not isinstance(frozen_model_git_sha, str) or not _MODEL.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be a lowercase 40-hex git SHA")
    if not isinstance(frozen_protocol_sha256, str) or not _DIGEST.fullmatch(frozen_protocol_sha256):
        raise ValueError("frozen_protocol_sha256 must be a lowercase SHA-256")
    channel = _text(channel, "channel")
    tolerance = _number(maximum_absolute_error, "maximum_absolute_error")
    coverage_min = _number(minimum_robust_coverage_fraction, "minimum_robust_coverage_fraction")
    if tolerance <= 0 or not 0 < coverage_min <= 1:
        raise ValueError("predeclared error and coverage thresholds must be positive; coverage <= 1")
    if isinstance(calibration_group_ids, (str, bytes)) or not isinstance(calibration_group_ids, Sequence):
        raise ValueError("calibration_group_ids must be a sequence")
    calibration = [_text(x, "calibration group") for x in calibration_group_ids]
    if not calibration or len(set(calibration)) != len(calibration):
        raise ValueError("unique calibration groups are required")
    if isinstance(holdout_runs, (str, bytes)) or not isinstance(holdout_runs, Sequence):
        raise ValueError("holdout_runs must be a sequence")
    if not 2 <= len(holdout_runs) <= 60:
        raise ValueError("at least two and at most sixty complete holdout runs required")

    seen_runs, seen_groups, seen_digests, seen_samples = set(), set(), set(), set()
    out = []
    blockers = []
    for index, run in enumerate(holdout_runs):
        if not isinstance(run, Mapping):
            raise ValueError("each holdout run must be a mapping")
        run_id = _text(run.get("run_id"), "run_id")
        group = _text(run.get("group_id"), "group_id")
        digest = run.get("source_sha256")
        if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError(f"{run_id}: original source_sha256 required")
        if run_id in seen_runs or group in seen_groups:
            raise ValueError("duplicate holdout run or experimental group")
        if digest in seen_digests:
            raise ValueError("duplicate original source digest across holdout runs")
        seen_digests.add(digest)
        seen_runs.add(run_id)
        seen_groups.add(group)
        if group in calibration:
            raise ValueError(f"{run_id}: calibration/holdout experimental group leakage")
        samples = run.get("samples")
        if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence):
            raise ValueError(f"{run_id}: samples must be a sequence")
        if not 5 <= len(samples) <= 100000:
            raise ValueError(f"{run_id}: 5–100000 observations required")

        flags = {
            "reported_physical_source": run.get("dataset_kind") == "reported_physical_measurements",
            "hardware_match_operator_declared": run.get("hardware_match") is True,
            "calibration_independence_operator_declared": run.get("unused_for_calibration") is True,
        }
        if not all(flags.values()):
            blockers.append(f"{run_id}: synthetic, incompatible, or reused calibration data")

        robust, possible, point_inside, error_inside = 0, 0, 0, 0
        worst_error = 0.0
        for sample in samples:
            if not isinstance(sample, Mapping):
                raise ValueError(f"{run_id}: sample must be a mapping")
            sid = _text(sample.get("sample_id"), "sample_id")
            if sid in seen_samples:
                raise ValueError("sample identifiers must be unique across holdouts")
            seen_samples.add(sid)
            predicted = _number(sample.get("prediction"), "prediction")
            lo = _number(sample.get("lower"), "lower")
            hi = _number(sample.get("upper"), "upper")
            observed = _number(sample.get("observed"), "observed")
            u = _number(sample.get("measurement_hard_bound"), "measurement_hard_bound", nonnegative=True)
            if lo > predicted or predicted > hi:
                raise ValueError(f"{run_id}/{sid}: prediction must be inside the reported interval")
            if not all(math.isfinite(v) for v in (observed - u, observed + u, predicted - observed)):
                raise ValueError(f"{run_id}/{sid}: error/enclosure overflow")
            residual_bound = abs(predicted - observed) + u
            if not math.isfinite(residual_bound):
                raise ValueError(f"{run_id}/{sid}: residual upper bound overflow")
            worst_error = max(worst_error, residual_bound)
            robust += int(lo <= observed - u and observed + u <= hi)
            possible += int(lo <= observed + u and observed - u <= hi)
            point_inside += int(lo <= observed <= hi)
            error_inside += int(residual_bound <= tolerance)

        count = len(samples)
        run_coverage = robust / count
        run_error_pass = error_inside == count
        run_coverage_pass = run_coverage >= coverage_min
        if not run_error_pass:
            blockers.append(f"{run_id}: hard-bound residual exceeds predeclared absolute tolerance")
        if not run_coverage_pass:
            blockers.append(f"{run_id}: robust interval inclusion below predeclared coverage")
        out.append({
            "run_id": run_id,
            "group_id": group,
            "source_sha256_operator_declared": digest,
            "source_flags": flags,
            "sample_count": count,
            "robustly_enclosed": robust,
            "point_estimate_inside": point_inside,
            "possibly_enclosed": possible,
            "hard_bound_residual_within_tolerance": error_inside,
            "robust_coverage_fraction": run_coverage,
            "worst_conservative_absolute_residual": worst_error,
            "error_gate_passed": run_error_pass,
            "interval_gate_passed": run_coverage_pass,
        })
    return {
        "status": ("REPORTED_HOLDOUT_REJECTED" if blockers
                   else "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"),
        "channel": channel,
        "frozen_model_git_sha": frozen_model_git_sha,
        "frozen_protocol_sha256_operator_supplied": frozen_protocol_sha256,
        "predeclared_maximum_absolute_error_operator_supplied": tolerance,
        "predeclared_minimum_robust_coverage_fraction_operator_supplied": coverage_min,
        "runs": out,
        "blockers": blockers,
        "source_cryptographically_authenticated": False,
        "actual_independent_physical_validation_established": False,
        "decision_equivalent_to_physical_testing": False,
        "limitations": [
            "SHA-256 strings have not been checked against authenticated original files",
            "Reported physical origin, hardware match, calibration split and preregistration timing are not independently verified",
            "Robust inclusion is deterministic for supplied hard error bounds, not a statistical coverage or failure-probability claim",
            "Samples within a run are correlated; pooled sample frequency does not prove generalization",
            "No operating-envelope representativeness, unseen failure cases or flight safety is established",
        ],
    }
