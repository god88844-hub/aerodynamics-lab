"""M27.6: bound residuals under declared absolute clock and measurement errors.

This is NOT an instrument clock calibration nor an empirical source audit.
The local slew-rate hard bound must truly cover the target signal throughout
the allowed timing offset; otherwise a time-shift error cannot be bounded.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

_SHA1 = re.compile(r"^[a-f0-9]{40}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _finite(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: finite numeric value required")
    try:
        x = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name}: finite numeric value required") from exc
    if not math.isfinite(x) or x < 0 or (positive and x == 0):
        raise ValueError(f"{name}: finite nonnegative value required")
    return x


def audit_clock_bounded_residuals(
    *,
    model_git_sha: str,
    protocol_sha256: str,
    channel: str,
    absolute_error_tolerance: float,
    minimum_coverage_fraction: float,
    samples: Sequence[Mapping],
    measurement_source: str,
    clock_bound_source: str,
    slew_bound_source: str,
) -> dict:
    """Compute conservative |prediction - observed| + u_y + L*u_t.

    For a signal y(t) known to be L-Lipschitz over the sample's possible
    absolute timing error u_t, |y(t)-observed| <= measurement_u + L*u_t.
    A user-declared "L" without physically justified coverage is not proof
    of correctness. No interpolation or clock alignment is performed.
    """
    if not isinstance(model_git_sha, str) or not _SHA1.fullmatch(model_git_sha):
        raise ValueError("model_git_sha must be lowercase 40-hex")
    if not isinstance(protocol_sha256, str) or not _SHA256.fullmatch(protocol_sha256):
        raise ValueError("protocol_sha256 must be lowercase 64-hex")
    if not isinstance(channel, str) or not _NAME.fullmatch(channel):
        raise ValueError("channel name required")
    for source, label in (
        (measurement_source, "measurement_source"),
        (clock_bound_source, "clock_bound_source"),
        (slew_bound_source, "slew_bound_source"),
    ):
        if not isinstance(source, str) or not 1 <= len(source.strip()) <= 500:
            raise ValueError(f"{label}: explicit source required")
    tolerance = _finite(absolute_error_tolerance, "absolute_error_tolerance", positive=True)
    if isinstance(minimum_coverage_fraction, bool) or not isinstance(minimum_coverage_fraction, (int, float)):
        raise ValueError("minimum_coverage_fraction must be between 0 and 1")
    coverage = float(minimum_coverage_fraction)
    if not math.isfinite(coverage) or not 0 < coverage <= 1:
        raise ValueError("minimum_coverage_fraction must be between 0 and 1")
    if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence) or not 5 <= len(samples) <= 50000:
        raise ValueError("5–50000 aligned samples required")
    allowed = {
        "sample_id", "time_s", "prediction", "observed", "measurement_hard_bound",
        "clock_time_hard_bound_s", "signal_slew_hard_bound_per_s",
    }
    output = []
    seen = set()
    previous = -1.0
    worst = 0.0
    inside = 0
    for item in samples:
        if not isinstance(item, Mapping) or set(item) != allowed:
            raise ValueError("every sample requires exact clock and instrument hard-bound fields")
        sid = item["sample_id"]
        if not isinstance(sid, str) or not _NAME.fullmatch(sid) or sid in seen:
            raise ValueError("sample ID must be unique and valid")
        seen.add(sid)
        t = _finite(item["time_s"], "time_s")
        if t <= previous:
            raise ValueError("sample times must strictly increase")
        previous = t
        predicted, observed = item["prediction"], item["observed"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (predicted, observed)):
            raise ValueError("prediction and observed must be finite numbers")
        try:
            p, o = float(predicted), float(observed)
        except (ValueError, OverflowError) as exc:
            raise ValueError("prediction and observed must be finite numbers") from exc
        if not math.isfinite(p) or not math.isfinite(o):
            raise ValueError("prediction and observed must be finite numbers")
        u_y = _finite(item["measurement_hard_bound"], "measurement_hard_bound")
        u_t = _finite(item["clock_time_hard_bound_s"], "clock_time_hard_bound_s")
        L = _finite(item["signal_slew_hard_bound_per_s"], "signal_slew_hard_bound_per_s")
        displacement = L * u_t
        abs_residual = abs(p - o)
        upper = abs_residual + u_y + displacement
        if not all(math.isfinite(v) for v in (abs_residual, displacement, upper)):
            raise ValueError("conservative timing-error accumulation overflow")
        meets = upper <= tolerance
        worst = max(worst, upper)
        inside += int(meets)
        output.append({
            "sample_id": sid, "time_s": t,
            "point_absolute_residual": abs_residual,
            "conservative_clock_value_uncertainty": displacement,
            "conservative_total_absolute_residual_upper": upper,
            "within_declared_tolerance": meets,
        })
    fraction = inside / len(output)
    passes = fraction >= coverage
    return {
        "status": ("REPORTED_CLOCK_BOUNDED_RESIDUAL_WITHIN_DECLARED_COVERAGE"
                   if passes else "REPORTED_CLOCK_BOUNDED_RESIDUAL_GATE_FAILED"),
        "model_git_sha": model_git_sha,
        "protocol_sha256_operator_declared": protocol_sha256,
        "channel": channel,
        "sample_count": len(output),
        "samples_within_declared_tolerance": inside,
        "conservative_coverage_fraction": fraction,
        "worst_conservative_absolute_residual_upper": worst,
        "metric_analytical_gate_passed": passes,
        "sample_results": output,
        "clock_hard_bounds_independently_verified": False,
        "signal_slew_bounds_independently_verified": False,
        "physical_measurement_origin_authenticated": False,
        "independent_real_world_prediction_validated": False,
        "flight_release_authorized": False,
        "limitations": [
            "Clock bounds and Lipschitz signal slew bound are declared, not instrument calibrated",
            "Assumes each slew bound covers the entire possible timing offset around the sample",
            "Reported coverage is an empirical sample fraction, not a future safety probability",
            "No original file custody, sensor synchronisation or independent hardware verification",
        ],
    }
