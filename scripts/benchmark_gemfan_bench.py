"""Compare steady thrust and current on held-out Gemfan 7042 bench records."""

from __future__ import annotations

import argparse
from bisect import bisect_left
import csv
from hashlib import sha256
from io import StringIO
import json
from math import exp, isfinite, log
from pathlib import Path
from statistics import linear_regression, mean, median, quantiles


MANIFEST = Path(__file__).resolve().parents[1] / "docs/campaigns/m22_gemfan_bench_sources.json"
GRAVITY_N_PER_GF = 0.00980665
MIN_SIGNAL_US = 1000
OUTPUTS = ("thrust_n", "current_a")
CHANNELS = ("Time (s)", "ESC signal (µs)", "Voltage (V)", "Current (A)", "Thrust (gf)",
            "Motor Optical Speed (RPM)", "Motor Electrical Speed (RPM)")


def summarize(source: bytes) -> dict:
    reader = csv.DictReader(StringIO(source.decode("utf-8-sig")))
    if not set(CHANNELS).issubset(reader.fieldnames or ()):
        raise ValueError("Required bench channels are missing")
    rows = [tuple(float(row[name]) for name in CHANNELS) for row in reader]
    if len(rows) < 30 or not all(isfinite(value) for row in rows for value in row):
        raise ValueError("Insufficient finite bench samples")
    elapsed, command, voltage, current, thrust, optical, electrical = zip(*rows)
    if len(set(command)) != 1 or command[0] <= MIN_SIGNAL_US or min(voltage) <= 0:
        raise ValueError("Expected one positive-drive setpoint and positive bus voltage")
    force = [value * GRAVITY_N_PER_GF for value in thrust]
    force_q25, _, force_q75 = quantiles(force)
    current_q25, _, current_q75 = quantiles(current)
    return {
        "rows": len(rows),
        "pwm_us": command[0],
        "bus_voltage_v": median(voltage),
        "thrust_n": median(force),
        "current_a": median(current),
        "thrust_iqr_n": force_q75 - force_q25,
        "current_iqr_a": current_q75 - current_q25,
        "negative_thrust_rows": sum(value < 0 for value in force),
        "nonincreasing_time_pairs": sum(a >= b for a, b in zip(elapsed, elapsed[1:])),
        "time_gaps_above_half_second": sum(b - a > 0.5 for a, b in zip(elapsed, elapsed[1:])),
        "positive_rpm_rows": sum(a > 0 or b > 0 for a, b in zip(optical, electrical)),
    }


def read_records(folder: Path, entries: list[dict]) -> list[dict]:
    records = []
    for entry in entries:
        path = folder / Path(entry["path"]).name
        source = path.read_bytes()
        if sha256(source).hexdigest() != entry["sha256"]:
            raise ValueError(f"Source hash mismatch for {path.name}")
        records.append({"file": path.name, **summarize(source)})
    return sorted(records, key=lambda record: record["pwm_us"])


def drive(record: dict) -> float:
    return (record["pwm_us"] - MIN_SIGNAL_US) / MIN_SIGNAL_US * record["bus_voltage_v"]


def fit(records: list[dict]) -> dict:
    if len({row["pwm_us"] for row in records}) != len(records):
        raise ValueError("Calibration setpoints must be distinct")
    coefficients = {}
    commands = [log(drive(row)) for row in records]
    for output in OUTPUTS:
        regression = linear_regression(commands, [log(row[output]) for row in records])
        coefficients[output] = {"slope": round(regression.slope, 12), "intercept": round(regression.intercept, 12)}
    return {"calibration_records": records, "power_law": coefficients, "pwm_zero_us": MIN_SIGNAL_US}


def interpolated_output(pwm_us: float, calibration: list[dict], output: str) -> float:
    commands = [row["pwm_us"] for row in calibration]
    if not commands[0] <= pwm_us <= commands[-1]:
        raise ValueError("Command is outside calibration support")
    upper = max(1, bisect_left(commands, pwm_us))
    a, b = calibration[upper - 1:upper + 1]
    weight = (pwm_us - a["pwm_us"]) / (b["pwm_us"] - a["pwm_us"])
    return a[output] + weight * (b[output] - a[output])


def evaluate(records: list[dict], frozen: dict) -> dict:
    reports = []
    for row in records:
        predictions = {"pwm_interpolation": {}, "drive_power_law": {}}
        for output in OUTPUTS:
            predictions["pwm_interpolation"][output] = round(interpolated_output(row["pwm_us"], frozen["calibration_records"], output), 9)
            law = frozen["power_law"][output]
            predictions["drive_power_law"][output] = round(exp(law["intercept"] + law["slope"] * log(drive(row))), 9)
        reports.append({"measurement": row, "predictions": predictions})
    errors = {
        model: {
            output: round(mean(abs(row["predictions"][model][output] - row["measurement"][output]) for row in reports), 9)
            for output in OUTPUTS
        }
        for model in ("pwm_interpolation", "drive_power_law")
    }
    return {
        "held_out_setpoints": reports,
        "mean_absolute_error": errors,
        "acceptance_status": "static_bench_comparison_without_independent_repeat_runs_or_acceptance_thresholds",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("calibrate", "evaluate"))
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    arguments = parser.parse_args()
    if arguments.mode == "evaluate" and arguments.freeze is None:
        parser.error("evaluate requires --freeze")
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    frozen = {"source_manifest_sha256": sha256(manifest_text.encode()).hexdigest(),
              **fit(read_records(arguments.source_dir, manifest["calibration"]))}
    if arguments.mode == "calibrate":
        result = frozen
    else:
        if frozen != json.loads(arguments.freeze.read_text(encoding="utf-8")):
            raise ValueError("Calibration does not reproduce the frozen model")
        result = evaluate(read_records(arguments.source_dir, manifest["holdout"]), frozen)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
