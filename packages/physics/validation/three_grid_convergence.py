"""M29.5 three-grid numerical convergence diagnostics for a frozen observable.

Richardson estimates are conditional on reaching an asymptotic error regime.
This read-only checker cannot establish solver order, source veracity, physical
accuracy or any safety/airworthiness permission. Zero fine-grid difference is
inconclusive without a separately verified exact reference solution.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

_SHA1 = re.compile(r"^[a-f0-9]{40}$")
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _finite(value: object, name: str, positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: finite numeric value required")
    try:
        num = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name}: finite numeric value required") from exc
    if not math.isfinite(num) or (positive and num <= 0):
        raise ValueError(f"{name}: finite positive numeric value required")
    return num


def audit_three_resolution_convergence(
    *,
    frozen_model_git_sha: str,
    channel: str,
    expected_solver_order: int,
    coarse_step_s: float,
    fixed_time_step_ratio: float,
    maximum_estimated_fine_grid_error: float,
    maximum_relative_order_ratio_error: float,
    samples: Sequence[Mapping],
    solver_source: str,
    convergence_protocol_source: str,
) -> dict:
    """Assess claimed h, h/r, h/r^2 values at identically sampled times.

    Let D1=|v_h-v_h/r| and D2=|v_h/r-v_h/r^2|. For order p and equal
    refinement ratio r, asymptotic D1/D2 approaches r**p. A conditional
    estimate of fine-grid error is D2/(r**p-1). A small D2 with an invalid
    ratio is NOT a successful convergence check. Exact D1=D2=0 is
    inconclusive, not evidence that errors vanish.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be lowercase 40-hex")
    if not isinstance(channel, str) or not _NAME.fullmatch(channel):
        raise ValueError("channel required")
    if type(expected_solver_order) is not int or not 1 <= expected_solver_order <= 8:
        raise ValueError("expected solver order must be an integer 1–8")
    coarse_h = _finite(coarse_step_s, "coarse_step_s", positive=True)
    ratio = _finite(fixed_time_step_ratio, "fixed_time_step_ratio", positive=True)
    if ratio < 2 or ratio > 16:
        raise ValueError("fixed_time_step_ratio must lie in [2,16]")
    max_error = _finite(maximum_estimated_fine_grid_error, "maximum_estimated_fine_grid_error", positive=True)
    ratio_error = _finite(maximum_relative_order_ratio_error, "maximum_relative_order_ratio_error")
    if ratio_error > .25:
        raise ValueError("maximum_relative_order_ratio_error must be in [0,0.25]")
    theoretical = ratio ** expected_solver_order
    if not math.isfinite(theoretical):
        raise ValueError("expected order/refinement overflow")
    for value, name in ((solver_source,"solver_source"),(convergence_protocol_source,"convergence_protocol_source")):
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
            raise ValueError(f"{name} required")
    if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence) or not 5 <= len(samples) <= 5000:
        raise ValueError("5–5000 common-time samples required")
    required = {"sample_id", "time_s", "coarse", "medium", "fine"}
    seen = set()
    prev_time = -1.
    rows = []
    fail_count = 0
    worst_est = 0.
    for sample in samples:
        if not isinstance(sample, Mapping) or set(sample) != required:
            raise ValueError("each sample must include exact three-grid fields")
        sid = sample["sample_id"]
        if not isinstance(sid, str) or not _NAME.fullmatch(sid) or sid in seen:
            raise ValueError("unique, valid sample IDs required")
        seen.add(sid)
        t = _finite(sample["time_s"], "time_s")
        if t < 0 or t <= prev_time:
            raise ValueError("sample times must strictly increase starting nonnegative")
        prev_time = t
        values = [_finite(sample[field], field) for field in ("coarse", "medium", "fine")]
        coarse, medium, fine = values
        d1 = abs(coarse-medium)
        d2 = abs(medium-fine)
        if not math.isfinite(d1) or not math.isfinite(d2):
            raise ValueError("grid delta overflow")
        if d2 == 0:
            observed_ratio = None
            fine_est = None
            accepted = False
        else:
            observed_ratio = d1/d2
            fine_est = d2/(theoretical-1)
            if not math.isfinite(observed_ratio) or not math.isfinite(fine_est):
                raise ValueError("grid ratio/error accumulation overflow")
            ratio_deviation = abs(observed_ratio/theoretical-1)
            accepted = ratio_deviation <= ratio_error and fine_est <= max_error
            worst_est = max(worst_est, fine_est)
        fail_count += int(not accepted)
        rows.append({
            "sample_id": sid, "time_s": t,
            "coarse_to_medium_abs_difference": d1,
            "medium_to_fine_abs_difference": d2,
            "observed_difference_ratio": observed_ratio,
            "conditional_fine_grid_error_estimate": fine_est,
            "asymptotic_order_and_error_gate_passed": accepted,
        })
    passed = fail_count == 0
    return {
        "status": ("REPORTED_THREE_GRID_CONVERGENCE_CONSISTENT_UNVERIFIED"
                   if passed else "REPORTED_THREE_GRID_CONVERGENCE_NOT_ESTABLISHED"),
        "channel": channel, "model_git_sha": frozen_model_git_sha,
        "expected_solver_order_operator_declared": expected_solver_order,
        "coarse_step_s": coarse_h, "medium_step_s": coarse_h/ratio,
        "fine_step_s": coarse_h/ratio**2,
        "expected_difference_ratio": theoretical,
        "samples": rows,
        "samples_failed_or_inconclusive": fail_count,
        "maximum_conditional_fine_grid_error_estimate": worst_est,
        "analytical_convergence_gate_passed": passed,
        "three_grid_runs_independently_authenticated": False,
        "asymptotic_regime_physically_proven": False,
        "real_world_prediction_accuracy_established": False,
        "flight_release_authorized": False,
        "limitations": [
            "Values and solver/order declarations are operator-supplied, not independently recomputed",
            "Richardson error estimate depends on asymptotic smooth convergence at declared order",
            "Identically equal three-grid values are inconclusive without an independently exact reference",
            "Numerical self-consistency cannot establish model-form fidelity or physical flight evidence",
        ],
    }
