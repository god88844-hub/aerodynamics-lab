"""Benchmark causal altitude tracking for healthy DronePropA QDrone 2 flights."""
from __future__ import annotations

import argparse
from hashlib import file_digest
import json
from math import exp
from pathlib import Path
from statistics import mean

import numpy as np
from scipy.io import loadmat
from scipy.signal import lfilter


PLAN_PATH = Path(__file__).resolve().parents[1] / "docs/campaigns/m23_dronepropa_altitude_sources.json"
SAMPLE_S = 0.02
MIN_REFERENCE_M = 0.19
MOVING_REFERENCE_M_S = 0.05
TIME_CONSTANTS_S = (0.04, 0.06, 0.10, 0.16, 0.25, 0.40, 0.63, 1.00)
DELAY_SAMPLES = (0, 2, 5, 10, 15, 25)


def resample(commander: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if commander.ndim != 2 or commander.shape[0] != 37 or commander.shape[1] < 2:
        raise ValueError("Expected a DronePropA commander_data matrix")
    timestamp, measured, desired = commander[[0, 23, 27]]
    if not np.isfinite([timestamp, measured, desired]).all():
        raise ValueError("Non-finite commander time or altitude")
    time = timestamp - timestamp[0]
    increments = np.diff(time)
    if np.any(increments <= 0) or np.any(increments > SAMPLE_S):
        raise ValueError("Commander clock must be strictly increasing without a gap above 20 ms")
    grid = np.arange(int(np.floor(time[-1] / SAMPLE_S)) + 1) * SAMPLE_S
    index = np.searchsorted(time, grid, side="right") - 1
    reference = desired[index]
    motion_capture = np.interp(grid, time, measured)
    candidates = np.flatnonzero(reference >= MIN_REFERENCE_M)
    if candidates.size < 2:
        raise ValueError("No commanded altitude evaluation interval")
    window = (grid >= grid[candidates[0]]) & (grid <= grid[candidates[-1]])
    return reference, motion_capture, window


def load_flight(folder: Path, record: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path = folder / record["name"]
    with path.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != record["sha256"]:
            raise ValueError(f"Publisher hash mismatch for {path.name}")
        stream.seek(0)
        commander = loadmat(stream, variable_names=["commander_data"])["commander_data"]
    return resample(commander)


def predicted_altitude(reference: np.ndarray, time_constant_s: float, delay_samples: int) -> np.ndarray:
    start = reference[0]
    lagged = np.pad(reference - start, (delay_samples, 0))[:reference.size]
    pole = exp(-SAMPLE_S / time_constant_s)
    numerator, denominator = [1 - pole], [1, -pole]
    # Cascade two identical stable, unity-gain stages.
    filtered = lfilter(numerator, denominator, lagged)
    return lfilter(numerator, denominator, filtered) + start


def fit(flights: list[tuple[np.ndarray, np.ndarray, np.ndarray]]) -> dict:
    def loss(time_constant: float, delay: int) -> float:
        return mean(float(np.mean(np.abs(predicted_altitude(desired, time_constant, delay)[window] - measured[window])))
                    for desired, measured, window in flights)

    mae, time_constant, delay = min((loss(tau, delay), tau, delay)
                                    for tau in TIME_CONSTANTS_S for delay in DELAY_SAMPLES)
    return {
        "sample_interval_s": SAMPLE_S,
        "min_reference_m": MIN_REFERENCE_M,
        "moving_reference_m_s": MOVING_REFERENCE_M_S,
        "time_constant_grid_s": list(TIME_CONSTANTS_S),
        "delay_grid_samples": list(DELAY_SAMPLES),
        "selected_time_constant_s": time_constant,
        "selected_delay_samples": delay,
        "mean_calibration_flight_mae_m": round(mae, 9),
    }


def metrics(error: np.ndarray) -> dict:
    return {
        "mae_m": round(float(np.mean(np.abs(error))), 9),
        "mean_signed_error_m": round(float(np.mean(error)), 9),
        "max_absolute_error_m": round(float(np.max(np.abs(error))), 9),
    }


def evaluate(folder: Path, records: list[dict], frozen: dict) -> dict:
    reports = []
    for record in records:
        desired, measured, window = load_flight(folder, record)
        estimate = predicted_altitude(desired, frozen["selected_time_constant_s"], frozen["selected_delay_samples"])
        moving = window & (np.abs(np.diff(desired, prepend=desired[0])) >= MOVING_REFERENCE_M_S * SAMPLE_S)
        if not np.any(moving):
            raise ValueError(f"No moving-reference samples in {record['name']}")
        reports.append({
            "name": record["name"],
            "scored_samples": int(np.sum(window)),
            "scored_duration_s": round((int(np.sum(window)) - 1) * SAMPLE_S, 4),
            "moving_reference_samples": int(np.sum(moving)),
            "direct_reference": metrics((desired - measured)[window]),
            "causal_two_stage": metrics((estimate - measured)[window]),
            "moving_reference": {
                "direct_reference": metrics((desired - measured)[moving]),
                "causal_two_stage": metrics((estimate - measured)[moving]),
            },
        })
    return {
        "holdout_flights": reports,
        "mean_flight_mae_m": {
            model: round(mean(flight[model]["mae_m"] for flight in reports), 9)
            for model in ("direct_reference", "causal_two_stage")
        },
        "acceptance_status": "inconclusive_research_benchmark_without_a_flight_acceptance_threshold",
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
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    calibration = [load_flight(arguments.source_dir, record) for record in plan["calibration"]]
    frozen = fit(calibration)
    if arguments.mode == "calibrate":
        result = frozen
    else:
        if frozen != json.loads(arguments.freeze.read_text(encoding="utf-8")):
            raise ValueError("Frozen altitude model does not reproduce from calibration flights")
        result = evaluate(arguments.source_dir, plan["holdout"], frozen)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
