"""Calibrate and test vertical force on the static MODERA quadcopter fixture."""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import io
import json
from math import fsum, isfinite
from pathlib import Path
from statistics import mean, median
from zipfile import ZipFile


SOURCE = "https://doi.org/10.5281/zenodo.17457069"
FORCES_SHA256 = "7d2ad1e86e2a30f12f9105b6f5f6aeaa03738ce173e694e55946a92ebaf89d8b"
ANGLES = (0, 30, 60, 90, 120, 150, 180)
THROTTLES = (0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 1.00)
HOLDOUT_PAIRS = ((0.10, 0.55), (0.10, 0.70), (0.25, 0.85), (0.40, 0.85), (0.55, 1.00), (0.70, 1.00))
ARRANGEMENTS = ("adjacent", "diagonal")
HEADER = ("Throttle0", "Throttle1", "Throttle2", "Throttle3", "Fx[N]", "Fy[N]", "Fz[N]", "Mx[Nm]", "My[Nm]", "Mz[Nm]")

Command = tuple[float, float, float, float]
Records = dict[Command, dict[int, str]]


def read_commands(text: str) -> tuple[dict[Command, str], int]:
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != HEADER:
        raise ValueError("Unexpected force CSV columns")
    commands = {}
    off_grid = 0
    for row in reader:
        throttle = tuple(float(row[name]) for name in HEADER[:4])
        key = tuple(min(THROTTLES, key=lambda level: abs(raw - level)) for raw in throttle)
        if any(not abs(raw - value) <= 1e-8 for raw, value in zip(throttle, key)):
            off_grid += 1
            continue
        if key in commands:
            raise ValueError(f"Duplicate canonical throttle command {key}")
        commands[key] = row["Fz[N]"]
    return commands, off_grid


def load_archive(path: Path) -> tuple[Records, dict]:
    data = path.read_bytes()
    if sha256(data).hexdigest() != FORCES_SHA256:
        raise ValueError("Force archive SHA-256 differs from the pinned source")
    rows_by_angle = {}
    discarded = {}
    with ZipFile(io.BytesIO(data)) as archive:
        for angle in ANGLES:
            table = archive.read(f"forces/yaw+{angle:02}_forces.csv").decode("utf-8-sig")
            rows_by_angle[angle], discarded[angle] = read_commands(table)
    common = sorted(set.intersection(*(set(rows) for rows in rows_by_angle.values())))
    records = {key: {angle: rows[key] for angle, rows in rows_by_angle.items()} for key in common}
    coverage = {
        "off_grid_rows_by_heading_deg": discarded,
        "rows_without_all_headings_by_heading_deg": {angle: len(rows) - len(common) for angle, rows in rows_by_angle.items()},
        "matched_configurations": len(common),
    }
    return records, coverage


def arrangement(command: Command) -> str:
    high = max(command)
    indexes = tuple(index for index, value in enumerate(command) if value == high)
    if len(indexes) != 2 or len(set(command)) != 2:
        raise ValueError("Expected two equal high and two equal low rotor commands")
    return "diagonal" if indexes in ((0, 1), (2, 3)) else "adjacent"


def forces_for_heading(readings: dict[int, str]) -> list[float]:
    forces = [float(readings[angle]) for angle in ANGLES]
    if not all(map(isfinite, forces)):
        raise ValueError("Non-finite vertical force in a selected configuration")
    return forces


def fit(records: Records) -> dict:
    equal_force = {
        level: median(forces_for_heading(records[(level,) * 4]))
        for level in THROTTLES
    }
    regressors = {name: [] for name in ARRANGEMENTS}
    for command, readings in records.items():
        low, high = min(command), max(command)
        if low == high or (low, high) in HOLDOUT_PAIRS:
            continue
        additive = (equal_force[low] + equal_force[high]) / 2
        residual = median(forces_for_heading(readings)) - additive
        regressors[arrangement(command)].append(((high - low) ** 2, residual))
    pooled = [entry for entries in regressors.values() for entry in entries]
    coefficient = {
        name: round(fsum(x * residual for x, residual in entries) / fsum(x * x for x, _ in entries), 12)
        for name, entries in (*regressors.items(), ("pooled", pooled))
    }
    return {
        "source": SOURCE,
        "forces_sha256": FORCES_SHA256,
        "holdout_pairs": [list(pair) for pair in HOLDOUT_PAIRS],
        "equal_throttle_force_n": {str(level): value for level, value in equal_force.items()},
        "calibration_mixed_configurations": {name: len(entries) for name, entries in regressors.items()},
        "quadratic_throttle_difference_coefficient_n": coefficient,
    }


def error_metrics(errors: list[float]) -> dict:
    return {
        "mean_absolute_error_n": round(mean(map(abs, errors)), 10),
        "mean_signed_error_n": round(mean(errors), 10),
        "max_absolute_error_n": round(max(map(abs, errors)), 10),
    }


def evaluate(records: Records, frozen: dict, coverage: dict) -> dict:
    if fit(records) != frozen:
        raise ValueError("The frozen calibration does not reproduce from the source")
    equal_force = frozen["equal_throttle_force_n"]
    coefficient = frozen["quadratic_throttle_difference_coefficient_n"]
    predictions = []
    for command, readings in records.items():
        low, high = min(command), max(command)
        if (low, high) not in HOLDOUT_PAIRS:
            continue
        geometry = arrangement(command)
        forces = forces_for_heading(readings)
        additive = (equal_force[str(low)] + equal_force[str(high)]) / 2
        contrast_squared = (high - low) ** 2
        predictions.append({
            "command": list(command),
            "high_rotor_arrangement": geometry,
            "heading_repeats": len(forces),
            "measured_median_force_n": median(forces),
            "measured_force_range_n": round(max(forces) - min(forces), 10),
            "additive_prediction_n": round(additive, 10),
            "pooled_prediction_n": round(additive + coefficient["pooled"] * contrast_squared, 10),
            "arrangement_prediction_n": round(additive + coefficient[geometry] * contrast_squared, 10),
        })
    if any(sum(min(row["command"]) == low and max(row["command"]) == high for row in predictions) != 6
           for low, high in HOLDOUT_PAIRS):
        raise ValueError("A held-out pair is missing motor arrangements")
    groups = {name: [row for row in predictions if row["high_rotor_arrangement"] == name] for name in ARRANGEMENTS}
    groups["all"] = predictions
    summary = {
        name: {
            "configurations": len(rows),
            "median_between_heading_force_range_n": round(median(row["measured_force_range_n"] for row in rows), 10),
            **{
                model: error_metrics([row[f"{model}_prediction_n"] - row["measured_median_force_n"] for row in rows])
                for model in ("additive", "pooled", "arrangement")
            },
        }
        for name, rows in groups.items()
    }
    return {
        "source": SOURCE,
        "forces_sha256": FORCES_SHA256,
        "coverage": coverage,
        "holdout_force_readings": len(predictions) * len(ANGLES),
        "metrics": summary,
        "holdouts": predictions,
        "acceptance_status": "research_fixture_comparison_inconclusive_for_operational_prediction",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("calibrate", "evaluate"))
    parser.add_argument("source_archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path, help="Frozen calibration JSON for evaluation")
    arguments = parser.parse_args()
    if arguments.mode == "evaluate" and arguments.freeze is None:
        parser.error("evaluate requires --freeze")
    measurements, coverage = load_archive(arguments.source_archive)
    if arguments.mode == "calibrate":
        result = fit(measurements)
    else:
        result = evaluate(measurements, json.loads(arguments.freeze.read_text(encoding="utf-8")), coverage)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
