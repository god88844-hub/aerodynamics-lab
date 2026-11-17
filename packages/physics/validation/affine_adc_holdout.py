"""M27.9: bounded affine ADC-sensor calibration and frozen prediction comparison.

Calibrated measurement is (scale * reported_code + offset). Conservative
absolute uncertainty includes scale, offset, quantization and residual bounds.
Operator-supplied calibration coefficients are not independently verified.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence

_ID = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _finite(v: object, name: str, *, nonnegative=False, positive=False) -> float:
    if isinstance(v, bool) or not isinstance(v, (float, int)):
        raise ValueError(f"{name}: finite number required")
    try:
        x = float(v)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name}: finite number required") from exc
    if not math.isfinite(x) or (nonnegative and x < 0) or (positive and x <= 0):
        raise ValueError(f"{name}: finite nonnegative/positive number required")
    return x


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name}: ASCII identifier required")
    return value


def audit_affine_sensor_holdouts(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    channel: str,
    calibration: Mapping,
    calibration_source: str,
    maximum_conservative_absolute_residual: float,
    minimum_interval_coverage_fraction: float,
    holdout_runs: Sequence[Mapping],
) -> dict:
    """Compare ADC-derived observed SI values to frozen predictions per run.

    Each calibration provides:
      scale_per_count, offset, scale_hard_error_per_count, offset_hard_error,
      calibration_residual_hard_error, quantization_code_half_width,
      minimum_valid_code, maximum_valid_code
    Each run provides run_id, group_id, samples; each sample has sample_id,
      time_s, raw_code, prediction, lower, upper, saturated.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be lowercase 40-hex")
    if not isinstance(frozen_protocol_sha256, str) or not _SHA256.fullmatch(frozen_protocol_sha256):
        raise ValueError("frozen_protocol_sha256 must be lowercase SHA-256")
    _identifier(channel, "channel")
    if not isinstance(calibration_source, str) or not 1 <= len(calibration_source.strip()) <= 500:
        raise ValueError("calibration_source required")
    keys = {
        "scale_per_count", "offset", "scale_hard_error_per_count",
        "offset_hard_error", "calibration_residual_hard_error",
        "quantization_code_half_width", "minimum_valid_code", "maximum_valid_code", "output_unit",
    }
    if not isinstance(calibration, Mapping) or set(calibration) != keys:
        raise ValueError("exact declared affine calibration fields required")
    output_unit = _identifier(calibration["output_unit"], "output_unit")
    scale = _finite(calibration["scale_per_count"], "scale_per_count")
    offset = _finite(calibration["offset"], "offset")
    scale_u = _finite(calibration["scale_hard_error_per_count"], "scale_hard_error_per_count", nonnegative=True)
    offset_u = _finite(calibration["offset_hard_error"], "offset_hard_error", nonnegative=True)
    residual_u = _finite(calibration["calibration_residual_hard_error"], "calibration_residual_hard_error", nonnegative=True)
    quant_half = _finite(calibration["quantization_code_half_width"], "quantization_code_half_width", nonnegative=True)
    lower_code, upper_code = calibration["minimum_valid_code"], calibration["maximum_valid_code"]
    if type(lower_code) is not int or type(upper_code) is not int or not 0 <= lower_code < upper_code <= 2**32-1:
        raise ValueError("integer ADC validity limits required")
    tolerance = _finite(maximum_conservative_absolute_residual, "maximum_conservative_absolute_residual", positive=True)
    cov = _finite(minimum_interval_coverage_fraction, "minimum_interval_coverage_fraction", positive=True)
    if cov > 1:
        raise ValueError("minimum_interval_coverage_fraction must not exceed 1")
    if isinstance(holdout_runs, (str, bytes)) or not isinstance(holdout_runs, Sequence) or not 2 <= len(holdout_runs) <= 60:
        raise ValueError("two to sixty whole holdout runs required")
    run_keys = {"run_id", "group_id", "samples"}
    sample_keys = {"sample_id", "time_s", "raw_code", "prediction", "lower", "upper", "saturated"}
    seen_runs, seen_groups = set(), set()
    results = []
    canonical = []
    total_good = 0
    for run in holdout_runs:
        if not isinstance(run, Mapping) or set(run) != run_keys:
            raise ValueError("exact whole-run fields required")
        run_id = _identifier(run["run_id"], "run_id")
        group_id = _identifier(run["group_id"], "group_id")
        if run_id in seen_runs or group_id in seen_groups:
            raise ValueError("duplicate run or group; holdouts must remain independent by declared group")
        seen_runs.add(run_id)
        seen_groups.add(group_id)
        samples = run["samples"]
        if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence) or not 5 <= len(samples) <= 5000:
            raise ValueError("five to five thousand samples per holdout run required")
        seen_samples = set()
        previous = -1.0
        good = 0
        max_error = 0.0
        row_summaries = []
        for sample in samples:
            if not isinstance(sample, Mapping) or set(sample) != sample_keys:
                raise ValueError("exact raw instrument and frozen prediction sample fields required")
            sid = _identifier(sample["sample_id"], "sample_id")
            if sid in seen_samples:
                raise ValueError("duplicate original sample ID")
            seen_samples.add(sid)
            t = _finite(sample["time_s"], "time_s", nonnegative=True)
            if t <= previous or (previous < 0 and t != 0):
                raise ValueError("sample times must start at zero and strictly increase")
            previous = t
            code = sample["raw_code"]
            if type(code) is not int or not lower_code <= code <= upper_code:
                raise ValueError("raw ADC count must be integer within declared non-clipped limits")
            if type(sample["saturated"]) is not bool:
                raise ValueError("saturated must be boolean")
            pred = _finite(sample["prediction"], "prediction")
            lo = _finite(sample["lower"], "lower")
            hi = _finite(sample["upper"], "upper")
            if lo > hi:
                raise ValueError("frozen prediction interval endpoints reversed")
            observed = scale*code + offset
            hard_error = (abs(code)*scale_u + offset_u + residual_u
                          + (abs(scale)+scale_u)*quant_half)
            discrepancy = abs(pred-observed) + hard_error
            if not all(math.isfinite(v) for v in (observed, hard_error, discrepancy, observed-hard_error, observed+hard_error)):
                raise ValueError("calibration arithmetic overflow")
            within_band = lo <= observed-hard_error and observed+hard_error <= hi
            valid = not sample["saturated"] and within_band and discrepancy <= tolerance
            good += int(valid)
            max_error = max(max_error, discrepancy)
            row_summaries.append({
                "sample_id": sid, "time_s": t, "derived_observed_value": observed,
                "declared_conservative_measurement_hard_error": hard_error,
                "declared_conservative_prediction_abs_residual_upper": discrepancy,
                "reported_hard_gate_passed": valid,
                "saturation_or_clipping_reported": sample["saturated"],
            })
        coverage = good/len(samples)
        passed = coverage >= cov and not any(x["saturation_or_clipping_reported"] for x in row_summaries)
        results.append({
            "run_id": run_id, "group_id": group_id, "sample_count": len(samples),
            "declared_coverage_fraction": coverage, "maximum_conservative_abs_residual": max_error,
            "run_analytical_gate_passed": passed, "sample_results": row_summaries,
        })
        canonical.append({"run_id": run_id, "group_id": group_id, "sample_results": row_summaries})
        total_good += int(passed)
    passed_all = total_good == len(results)
    digest = hashlib.sha256(json.dumps(sorted(canonical,key=lambda x:x["run_id"]),sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
    return {
        "status": ("REPORTED_ADC_CALIBRATED_HOLDOUTS_CONSISTENT_UNAUTHENTICATED"
                   if passed_all else "REPORTED_ADC_CALIBRATED_HOLDOUTS_REJECTED"),
        "frozen_model_git_sha": frozen_model_git_sha,
        "frozen_protocol_sha256": frozen_protocol_sha256,
        "channel": channel,
        "calibration_output_unit_operator_declared": output_unit,
        "calibration_source_operator_declared": calibration_source.strip(),
        "operator_report_digest_sha256": digest,
        "runs": results,
        "all_declared_holdout_analytical_gates_passed": passed_all,
        "actual_calibration_certificates_authenticated": False,
        "raw_ADC_bytes_or_physical_recording_authenticated": False,
        "independent_real_world_accuracy_validated": False,
        "physical_release_authorized": False,
        "limitations": [
            "Affine conversion and maximum errors are operator-declared, not independently certified",
            "Raw ADC integer values are supplied in memory, not authenticated acquisition bytes",
            "Quantization bound assumes half-code rounding and no unmodeled hysteresis/nonlinearity",
            "Predictions and holdout independence are operator-reported and not externally verified",
        ],
    }
