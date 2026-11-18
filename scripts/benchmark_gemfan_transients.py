"""Compare static and causal lag models on a reserved Emax/Gemfan sweep."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
from io import StringIO
from itertools import groupby
import json
from math import exp, isfinite
from pathlib import Path
from statistics import mean, median
from typing import NamedTuple

from benchmark_gemfan_bench import GRAVITY_N_PER_GF, MANIFEST as STATIC_MANIFEST, interpolated_output


MANIFEST = STATIC_MANIFEST.with_name("m22_gemfan_transients_sources.json")
OUTPUTS = ("thrust_n", "current_a")
PWM_LEVELS = (1100, 1150, 1200, 1250, 1300, 1350)
TAU_S = (0.0, 0.04, 0.08, 0.16, 0.25, 0.40, 0.63, 1.0)
MAX_INTERVAL_S = 0.25
FIELDS = ("Time (s)", "ESC signal (µs)", "Thrust (gf)", "Current (A)")


class Row(NamedTuple):
    time_s: float
    pwm_us: float
    thrust_gf: float
    current_a: float


def load(source_dir: Path, entry: dict) -> list[Row]:
    filename = Path(entry["path"]).name
    raw = (source_dir / filename).read_bytes()
    if sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError(f"Source hash differs for {filename}")
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    if not set(FIELDS).issubset(reader.fieldnames or ()):
        raise ValueError(f"Required data channels are missing in {filename}")
    rows = []
    for row in reader:
        if not any(row[field] for field in FIELDS) or (not rows and not row[FIELDS[1]]):
            # Some exports start logging sensors before the PWM channel is armed.
            continue
        rows.append(Row(*(float(row[field]) for field in FIELDS)))
    if not rows or not all(isfinite(value) for row in rows for value in row):
        raise ValueError(f"Non-finite or absent recorded samples in {filename}")
    return rows


def target(row: Row, output: str) -> float:
    return row.thrust_gf * GRAVITY_N_PER_GF if output == "thrust_n" else row.current_a


def plateaus(rows: list[Row]) -> list[dict]:
    points = []
    for command, group in groupby(rows, key=lambda sample: sample.pwm_us):
        segment = list(group)
        if command not in PWM_LEVELS or segment[-1].time_s - segment[0].time_s < 5:
            continue
        tail = [sample for sample in segment if sample.time_s >= segment[-1].time_s - 2.0]
        if len(tail) < 10 or any(not 0 < b.time_s - a.time_s <= MAX_INTERVAL_S for a, b in zip(tail, tail[1:])):
            raise ValueError(f"Plateau for {command:g} μs has insufficient continuous support")
        points.append({"pwm_us": command, **{name: median(target(row, name) for row in tail) for name in OUTPUTS}})
    if tuple(point["pwm_us"] for point in points) != PWM_LEVELS:
        raise ValueError("Calibration sweep differs from the six declared command plateaus")
    return points


def replay(rows: list[Row], static: list[dict], tau_s: float, output: str) -> list[float | None]:
    estimates: list[float | None] = []
    state = previous_target = None
    previous_time = None
    for row in rows:
        if not PWM_LEVELS[0] <= row.pwm_us <= PWM_LEVELS[-1]:
            state = previous_target = None
            previous_time = None
            estimates.append(None)
            continue
        steady = interpolated_output(row.pwm_us, static, output)
        continuous = previous_time is not None and 0 < row.time_s - previous_time <= MAX_INTERVAL_S
        if not continuous:
            state = steady
            estimates.append(None)
        elif tau_s == 0:
            state = steady
            estimates.append(state)
        else:
            decay = exp(-(row.time_s - previous_time) / tau_s)
            state = previous_target + (state - previous_target) * decay
            estimates.append(state)
        previous_time, previous_target = row.time_s, steady
    return estimates


def error_series(rows: list[Row], predictions: list[float | None], output: str, excluded: set[Row]) -> list[float]:
    return [estimate - target(row, output) for row, estimate in zip(rows, predictions)
            if estimate is not None and row not in excluded]


def fit(rows: list[Row], manifest_digest: str) -> dict:
    static = plateaus(rows)
    selected = {}
    for output in OUTPUTS:
        options = []
        for tau_s in TAU_S:
            errors = error_series(rows, replay(rows, static, tau_s, output), output, set())
            options.append((mean(map(abs, errors)), tau_s))
        error, tau_s = min(options)
        selected[output] = {"lag_s": tau_s, "calibration_mae": round(error, 9)}
    return {"manifest_sha256": manifest_digest, "plateau_medians": static, "lag_grid_s": list(TAU_S),
            "max_step_interval_s": MAX_INTERVAL_S, "selected": selected}


def evaluate(calibration: list[Row], holdout: list[Row], previous: set[Row], freeze: dict) -> dict:
    excluded = previous | set(calibration)
    metrics = {}
    for output in OUTPUTS:
        for name, tau_s in (("static", 0.0), ("frozen_lag", freeze["selected"][output]["lag_s"])):
            errors = error_series(holdout, replay(holdout, freeze["plateau_medians"], tau_s, output), output, excluded)
            metrics.setdefault(name, {})[output] = {"samples": len(errors), "mae": round(mean(map(abs, errors)), 9),
                                                   "mean_signed_error": round(mean(errors), 9), "max_error": round(max(map(abs, errors)), 9)}
    return {
        "holdout_rows": len(holdout),
        "holdout_rows_within_pwm_support": sum(PWM_LEVELS[0] <= row.pwm_us <= PWM_LEVELS[-1] for row in holdout),
        "overlapping_prior_rows_within_pwm_support": sum(row in excluded and PWM_LEVELS[0] <= row.pwm_us <= PWM_LEVELS[-1] for row in holdout),
        "metrics": metrics,
        "acceptance_status": "single_reserved_sweep_without_instrument_timing_or_transient_acceptance",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("calibrate", "evaluate"))
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.mode == "evaluate" and args.freeze is None:
        parser.error("evaluate requires --freeze")
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    calibration = load(args.source_dir, manifest["calibration"])
    frozen = fit(calibration, sha256(manifest_text.encode()).hexdigest())
    if args.mode == "calibrate":
        result = frozen
    else:
        if frozen != json.loads(args.freeze.read_text(encoding="utf-8")):
            raise ValueError("Calibration differs from frozen sweep model")
        older = json.loads(STATIC_MANIFEST.read_text(encoding="utf-8"))
        prior = {row for entry in older["calibration"] + older["holdout"] for row in load(args.source_dir, entry)}
        result = evaluate(calibration, load(args.source_dir, manifest["holdout"]), prior, frozen)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
