"""Forecast the SIT module's final constant-power stage from earlier samples."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from benchmark_sit_module import (
    CAPACITY_AH, LIMITS, SOURCE_SHA256, Cycle, battery_models, calibrate, digest,
    errors, filtered, load_cycles,
)

PLAN = "m21-sit-cutoff-forecast-v1"
ISSUE_TIME_S = 370
FORECAST_TIMES_S = np.arange(ISSUE_TIME_S + 2, 427, 2)
LANDING_POWER_W = 9000.0
GUARD_CALIBRATION = range(51, 151)
HOLDOUT = {"first": range(201, 251), "second": range(279, 329)}
LOWER_BAND_QUANTILE = 0.95


@dataclass(frozen=True)
class Forecast:
    voltage: np.ndarray
    current: np.ndarray


def constant_power_current(power_w: float, effective_source_v: float, ohms: float) -> float | None:
    discriminant = effective_source_v ** 2 - 4 * ohms * power_w
    if discriminant < 0 or effective_source_v <= 0:
        return None
    return 2 * power_w / (effective_source_v + np.sqrt(discriminant))


def forecast(cycle: Cycle, fit: dict, *, update: bool) -> Forecast | None:
    # Only this prefix may contribute to state initialization and corrections.
    selected = cycle.t <= ISSUE_TIME_S
    t, q, current = cycle.t[selected], cycle.charge_ah[selected], cycle.current[selected]
    module_v = cycle.voltages[selected, 0]
    if t[-1] != ISSUE_TIME_S or q[-1] > fit["max_charge_ah"]:
        return None

    model = fit["one_rc"]
    b = battery_models(
        np.array(model["ocv_v"]), np.array(model["series_ohm"]), np.array(fit["charge_knots_ah"])
    )[0]
    series = model["series_ohm"][0]
    rc = model["polarization_ohm"][0]
    tau = model["tau_s"]
    memory = filtered(current, t, tau)
    offset = 0.0
    if update:
        rest = (t >= 300) & (t <= 320) & (current < 1)
        loaded = (t >= 354) & (t <= ISSUE_TIME_S) & (current >= 90)
        if rest.sum() < 5 or loaded.sum() < 5:
            return None
        reference = np.array([
            b.voltage_under_load(100 * (1 - charge / CAPACITY_AH), amps)
            for charge, amps in zip(q, current, strict=True)
        ]) - rc * memory
        residual = module_v - reference
        offset = float(np.median(residual[rest]))
        slope = (float(np.median(residual[loaded])) - offset) / np.median(current[loaded])
        series -= slope
        if series < 0:
            return None

    charge_ah, prev_amps, v_state = q[-1], current[-1], memory[-1]
    dt = 2
    decay = np.exp(-dt / tau)
    predicted_v = np.full(len(FORECAST_TIMES_S), np.nan)
    predicted_i = np.full(len(FORECAST_TIMES_S), np.nan)
    for index in range(len(FORECAST_TIMES_S)):
        charge_ah += prev_amps * dt / 3600
        if charge_ah > fit["max_charge_ah"]:
            break
        v_state = decay * v_state + (1 - decay) * prev_amps
        source_v = b.ocv_pack(100 * (1 - charge_ah / CAPACITY_AH)) + offset - rc * v_state
        amps = constant_power_current(LANDING_POWER_W, source_v, series)
        if amps is None:
            break
        predicted_i[index] = amps
        predicted_v[index] = source_v - series * amps
        prev_amps = amps
    return Forecast(predicted_v, predicted_i)


def pair(cycle: Cycle, fit: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    original = forecast(cycle, fit, update=False)
    updated = forecast(cycle, fit, update=True)
    observed = cycle.voltages[
        (cycle.t > ISSUE_TIME_S) & (cycle.t <= FORECAST_TIMES_S[-1]), 0
    ]
    if original is None or updated is None or not len(observed):
        return None
    return observed, original.voltage[:len(observed)], updated.voltage[:len(observed)]


def guard_band(path: Path, base_fit: dict) -> dict:
    cycles, bad = load_cycles(path, GUARD_CALIBRATION)
    maxima = []
    for c in cycles:
        comparison = pair(c, base_fit)
        if comparison is None:
            continue
        observed, original, updated = comparison
        if not (np.isfinite(original).all() and np.isfinite(updated).all()):
            continue
        maxima.append(float(np.max(updated - observed)))
    if len(maxima) < 30:
        raise ValueError("too few source cycles to calibrate the empirical band")
    return {
        "plan": PLAN, "source_sha256": SOURCE_SHA256,
        "parent_fit_canonical_sha256": digest(base_fit),
        "guard_calibration_cycles": len(maxima), "source_rejections": bad,
        "one_sided_cycle_residual_v": round(max(0.0, float(np.quantile(maxima, LOWER_BAND_QUANTILE, method="higher"))), 9),
    }


def compare(path: Path, base_fit: dict, freeze: dict) -> dict:
    pad = freeze["one_sided_cycle_residual_v"]
    limit = LIMITS["module_v"]
    results = {}
    for name, numbers in HOLDOUT.items():
        cycles, bad = load_cycles(path, numbers)
        counts = Counter({k: 0 for k in (
            "full_pairs", "unsupported_or_missing_pair", "observed_post_issue_cutoff",
            "observed_cutoff_outside_pairs", "original_cutoff_missed", "updated_cutoff_missed",
            "original_point_cutoff_any", "updated_point_cutoff_any", "guard_warning_any",
            "guard_cutoff_missed", "guard_only_without_observed_crossing",
            "guard_only_in_early_ending_recordings", "lower_band_covered_entire_compared_segment",
        )})
        original_errors, updated_errors = [], []
        leads = []
        for c in cycles:
            present = (c.t > ISSUE_TIME_S) & (c.t <= FORECAST_TIMES_S[-1])
            measured = c.voltages[present, 0]
            over = np.flatnonzero(measured < limit)
            counts["observed_post_issue_cutoff"] += bool(over.size)
            matched = pair(c, base_fit)
            if matched is None or not (np.isfinite(matched[1]).all() and np.isfinite(matched[2]).all()):
                counts["unsupported_or_missing_pair"] += 1
                counts["observed_cutoff_outside_pairs"] += bool(over.size)
                continue
            observed, original, updated = matched
            counts["full_pairs"] += 1
            original_errors.append(original - observed)
            updated_errors.append(updated - observed)
            lower = updated - pad
            counts["lower_band_covered_entire_compared_segment"] += bool((observed >= lower).all())
            guard = np.flatnonzero(lower < limit)
            counts["original_point_cutoff_any"] += bool((original < limit).any())
            counts["updated_point_cutoff_any"] += bool((updated < limit).any())
            counts["guard_warning_any"] += bool(guard.size)
            if over.size:
                endpoint = over[0]
                counts["original_cutoff_missed"] += bool((original[:endpoint + 1] >= limit).all())
                counts["updated_cutoff_missed"] += bool((updated[:endpoint + 1] >= limit).all())
                timely = bool(guard.size and guard[0] <= endpoint)
                counts["guard_cutoff_missed"] += not timely
                if timely:
                    leads.append(int(2 * (endpoint - guard[0])))
            elif guard.size:
                counts["guard_only_without_observed_crossing"] += 1
                counts["guard_only_in_early_ending_recordings"] += bool(c.t[-1] < FORECAST_TIMES_S[-1])
        results[name] = {
            "selected_cycles": len(numbers), "source_rejections": bad, **dict(counts),
            "original_voltage_error_v": errors(original_errors) if original_errors else None,
            "updated_voltage_error_v": errors(updated_errors) if updated_errors else None,
            "guard_lead_time_s_median": float(np.median(leads)) if leads else None,
            "status": (
                "FAILED_SAMPLED_STUDY_LIMIT" if counts["observed_post_issue_cutoff"] or counts["updated_point_cutoff_any"]
                else "INCONCLUSIVE_FOR_PACK_ACCEPTANCE"
            ),
        }
    return {"plan": PLAN, "frozen_guard_canonical_sha256": digest(freeze),
            "one_sided_cycle_residual_v": pad, "cohorts": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "evaluate"))
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    base = calibrate(args.workbook)
    fit = guard_band(args.workbook, base)
    if args.action == "evaluate":
        if args.freeze is None or digest(json.loads(args.freeze.read_bytes())) != digest(fit):
            parser.error("the frozen guard must reproduce from the earlier source cycles")
        result = compare(args.workbook, base, fit)
    else:
        result = fit
    args.output.write_bytes((json.dumps(result, indent=2, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
