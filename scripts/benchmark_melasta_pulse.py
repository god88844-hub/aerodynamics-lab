"""Forecast a prescribed 68 A pulse in held-out Melasta pouch cells."""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from statistics import mean
from zipfile import ZipFile

import numpy as np
from scipy.integrate import trapezoid
from scipy.io import loadmat


SOURCE = "https://doi.org/10.5281/zenodo.12543440"
SOURCE_SHA256 = "a879965afef8691cb2a845e217581d4f5275249fb80dbb615f2cb56418876ff6"
CALIBRATION_CELLS = (1, 2, 3)
HOLDOUT_CELLS = (4, 5)
REPEATS = (1, 2, 3, 4, 5)
PULSE_STEP = 17
PROGRAMMED_CURRENT_A = 68.0
PREPULSE_WINDOW_S = 0.5
GRID = np.linspace(0.0, 29.0, 146)


def pulse_signals(data: dict) -> tuple[float, np.ndarray, np.ndarray]:
    time, voltage, current, step = (np.asarray(data[name]) for name in ("time", "voltage", "current", "step_index"))
    if time.ndim != 1 or any(signal.shape != time.shape for signal in (voltage, current, step)):
        raise ValueError("Expected matching one-dimensional pulse records")
    if not np.isfinite([time, voltage, current]).all() or np.any(np.diff(time) <= 0):
        raise ValueError("Expected finite signals on a strictly increasing clock")
    indices = np.flatnonzero(step == PULSE_STEP)
    if indices.size < 2 or indices[0] == 0 or np.any(np.diff(indices) != 1):
        raise ValueError("Expected a contiguous pulse following the dynamic load")
    pulse_time = time[indices] - time[indices[0]]
    if pulse_time[-1] < GRID[-1] or abs(np.median(current[indices]) + PROGRAMMED_CURRENT_A) > 0.5:
        raise ValueError("Pulse lacks 29 seconds of support or the prescribed current")
    before = (time >= time[indices[0]] - PREPULSE_WINDOW_S) & (time < time[indices[0]]) & (step == PULSE_STEP - 1)
    if np.count_nonzero(before) < 2:
        raise ValueError("Insufficient preceding dynamic voltage observations")
    anchor = float(np.mean(voltage[before]))
    observed_voltage = np.interp(GRID, pulse_time, voltage[indices])
    observed_power = np.interp(GRID, pulse_time, -voltage[indices] * current[indices])
    return anchor, observed_voltage, observed_power


def measurements(archive: ZipFile, cells: tuple[int, ...]) -> dict:
    runs = {}
    for cell in cells:
        for repeat in REPEATS:
            name = f"Experiment-I/ANOVA_ID{cell}_{repeat}.mat"
            fields = loadmat(BytesIO(archive.read(name)), simplify_cells=True)["data"]
            runs[(cell, repeat)] = pulse_signals(fields)
    return runs


def fit(runs: dict) -> dict:
    mean_sag = np.mean([anchor - voltage for anchor, voltage, _ in runs.values()], axis=0)
    matrix = np.column_stack((np.ones(len(GRID)), np.sqrt(GRID)))
    intercept, slope = np.linalg.lstsq(matrix, mean_sag, rcond=None)[0]
    return {
        "source": SOURCE,
        "sha256": SOURCE_SHA256,
        "calibration_cells": list(CALIBRATION_CELLS),
        "holdout_cells": list(HOLDOUT_CELLS),
        "repeats_per_cell": len(REPEATS),
        "prepulse_voltage_window_s": PREPULSE_WINDOW_S,
        "score_through_s": float(GRID[-1]),
        "grid_spacing_s": float(GRID[1]),
        "programmed_current_a": PROGRAMMED_CURRENT_A,
        "constant_sag_v": round(float(np.mean(mean_sag)), 10),
        "sqrt_time_intercept_v": round(float(intercept), 10),
        "sqrt_time_slope_v_per_sqrt_s": round(float(slope), 10),
    }


def average_power(power: np.ndarray) -> float:
    return float(trapezoid(power, x=GRID) / GRID[-1])


def evaluate(runs: dict, frozen: dict) -> dict:
    falloff = frozen["sqrt_time_intercept_v"] + frozen["sqrt_time_slope_v_per_sqrt_s"] * np.sqrt(GRID)
    reports = []
    for (cell, repeat), (anchor, observed, observed_power) in runs.items():
        predictions = {"constant_sag": np.full(GRID.size, anchor - frozen["constant_sag_v"]), "sqrt_time_sag": anchor - falloff}
        measured_average_power = average_power(observed_power)
        errors = {}
        for name, prediction in predictions.items():
            error = prediction - observed
            errors[name] = {
                "voltage_mae_v": round(float(np.mean(np.abs(error))), 9),
                "max_absolute_voltage_error_v": round(float(np.max(np.abs(error))), 9),
                "terminal_voltage_error_v": round(float(error[-1]), 9),
                "mean_pulse_power_error_w": round(average_power(prediction * PROGRAMMED_CURRENT_A) - measured_average_power, 9),
            }
        reports.append({
            "cell": cell,
            "repeat": repeat,
            "prepulse_voltage_v": round(anchor, 9),
            "measured_terminal_voltage_v": round(float(observed[-1]), 9),
            "measured_mean_pulse_power_w": round(measured_average_power, 9),
            "models": errors,
        })
    groups = {str(cell): [row for row in reports if row["cell"] == cell] for cell in HOLDOUT_CELLS}
    groups["all"] = reports
    summary = {
        name: {
            "runs": len(group),
            **{
                model: {
                    "mean_voltage_mae_v": round(mean(row["models"][model]["voltage_mae_v"] for row in group), 9),
                    "mean_absolute_terminal_error_v": round(mean(abs(row["models"][model]["terminal_voltage_error_v"]) for row in group), 9),
                    "mean_absolute_average_power_error_w": round(mean(abs(row["models"][model]["mean_pulse_power_error_w"]) for row in group), 9),
                    "max_absolute_voltage_error_v": max(row["models"][model]["max_absolute_voltage_error_v"] for row in group),
                }
                for model in ("constant_sag", "sqrt_time_sag")
            },
        }
        for name, group in groups.items()
    }
    return {
        "source": SOURCE,
        "summary": summary,
        "holdout_runs": reports,
        "acceptance_status": "conditional_cell_pulse_benchmark_without_pack_or_endurance_acceptance",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("calibrate", "evaluate"))
    parser.add_argument("experiment_archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    arguments = parser.parse_args()
    if arguments.mode == "evaluate" and arguments.freeze is None:
        parser.error("evaluate requires --freeze")
    original = arguments.experiment_archive.read_bytes()
    if sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("Experiment I archive hash differs from the pinned publisher file")
    with ZipFile(BytesIO(original)) as archive:
        frozen = fit(measurements(archive, CALIBRATION_CELLS))
        if arguments.mode == "calibrate":
            result = frozen
        else:
            if frozen != json.loads(arguments.freeze.read_text(encoding="utf-8")):
                raise ValueError("Frozen pulse model does not match the calibration source")
            result = evaluate(measurements(archive, HOLDOUT_CELLS), frozen)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
