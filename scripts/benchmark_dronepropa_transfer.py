"""Test transfer of frozen QDrone 2 altitude predictions and empirical error bands."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
from statistics import mean

import numpy as np

from benchmark_dronepropa_altitude import PLAN_PATH, load_flight, metrics, moving_reference_mask, predicted_altitude


CAMPAIGNS = PLAN_PATH.parent
MODEL_PATH = CAMPAIGNS / "m23_dronepropa_altitude_freeze.json"
TRANSFER_PATH = CAMPAIGNS / "m27_dronepropa_transfer_sources.json"
REGIMES = ("moving_reference", "remaining_window")


def residuals(folder: Path, record: dict, model: dict) -> dict[str, np.ndarray]:
    desired, measured, window = load_flight(folder, record)
    predicted = predicted_altitude(desired, model["selected_time_constant_s"], model["selected_delay_samples"])
    moving = moving_reference_mask(desired, window)
    errors = {"moving_reference": (predicted - measured)[moving], "remaining_window": (predicted - measured)[window & ~moving]}
    if any(len(values) == 0 for values in errors.values()):
        raise ValueError(f"Missing a scored command regime in {record['name']}")
    return errors


def calibrate(folder: Path, records: list[dict], model: dict, model_digest: str) -> dict:
    data = {record["name"]: residuals(folder, record, model) for record in records}
    # Round upward so persistence cannot shrink the measured maximum.
    bounds = {
        regime: ceil(max(float(np.max(np.abs(run[regime]))) for run in data.values()) * 1e9) / 1e9
        for regime in REGIMES
    }
    return {
        "frozen_altitude_model_sha256_with_lf": model_digest,
        "band_calibration_runs": list(data),
        "half_width_m": bounds,
    }


def score_regime(error: np.ndarray, half_width: float) -> dict:
    absolute = np.abs(error)
    covered = int(np.count_nonzero(absolute <= half_width))
    return {
        **metrics(error),
        "scored_samples": error.size,
        "covered_samples": covered,
        "max_band_excess_m": round(max(0.0, float(np.max(absolute)) - half_width), 9),
    }


def evaluate(folder: Path, cohorts: dict[str, list[dict]], model: dict, frozen: dict) -> dict:
    results = {}
    for cohort, records in cohorts.items():
        runs = []
        for record in records:
            error = residuals(folder, record, model)
            groups = {regime: score_regime(error[regime], frozen["half_width_m"][regime]) for regime in REGIMES}
            runs.append({
                "name": record["name"],
                **metrics(np.concatenate(list(error.values()))),
                "regimes": groups,
                "whole_flight_covered": all(group["covered_samples"] == group["scored_samples"] for group in groups.values()),
            })
        results[cohort] = {
            "flights": len(runs),
            "whole_flights_covered": sum(run["whole_flight_covered"] for run in runs),
            "mean_flight_mae_m": round(mean(run["mae_m"] for run in runs), 9),
            "worst_flight_max_absolute_error_m": max(run["max_absolute_error_m"] for run in runs),
            "worst_band_excess_m": max(group["max_band_excess_m"] for run in runs for group in run["regimes"].values()),
            "runs": runs,
        }
    return {
        "half_width_m": frozen["half_width_m"],
        "cohorts": results,
        "acceptance_status": "inconclusive_few_independent_flights_and_no_calibrated_coverage_requirement",
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
    model_text = MODEL_PATH.read_text(encoding="utf-8")
    model = json.loads(model_text)
    nominal = json.loads(PLAN_PATH.read_text(encoding="utf-8"))["holdout"]
    frozen = calibrate(arguments.source_dir, nominal, model, sha256(model_text.encode("utf-8")).hexdigest())
    if arguments.mode == "calibrate":
        result = frozen
    else:
        if frozen != json.loads(arguments.freeze.read_text(encoding="utf-8")):
            raise ValueError("Frozen transfer bands do not reproduce from their calibration flights")
        cohorts = json.loads(TRANSFER_PATH.read_text(encoding="utf-8"))["cohorts"]
        result = evaluate(arguments.source_dir, cohorts, model, frozen)
    arguments.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
