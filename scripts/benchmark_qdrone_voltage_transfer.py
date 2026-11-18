"""Test QDrone 2 tracking and voltage predictions under low-voltage transfer."""

from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
from math import exp, isfinite
from pathlib import Path

import numpy as np
from scipy.integrate import trapezoid
from scipy.optimize import nnls
from scipy.signal import lfilter


MANIFEST = Path(__file__).resolve().parents[1] / "docs/campaigns/m26_qdrone_voltage_sources.json"
DT_S = 0.0025
BASELINE_S = 0.5
REFERENCE_LINE_V = 14.0
TIME_CONSTANTS_S = (0.02, 0.05, 0.10, 0.20, 0.40, 0.80, 1.60)
TIME = "Time (s)"
COMMAND = "zd (m)"
AUXILIARY = "zauxd (m)"
ALTITUDE = "zw (m)"
VOLTAGE = "Battery Voltage (V)"
ACTUATORS = tuple(f"m{i} (V)" for i in range(1, 5))


def read_export(folder: Path, entry: dict, fields: tuple[str, ...]) -> dict[str, np.ndarray]:
    from openpyxl import load_workbook

    original = (folder / entry["file"]).read_bytes()
    if sha256(original).hexdigest() != entry["sha256"]:
        raise ValueError(f"Publisher file hash mismatch: {entry['file']}")
    workbook = load_workbook(io.BytesIO(original), read_only=True, data_only=True)
    try:
        table = workbook.active.values
        header = next(table)
        positions = [header.index(name) for name in fields]
        rows = [tuple(row[i] for i in positions) for row in table]
    finally:
        workbook.close()
    if not rows or any(not isinstance(value, (int, float)) or not isfinite(value) for row in rows for value in row):
        raise ValueError(f"Missing or non-finite exported signal: {entry['file']}")
    data = dict(zip(fields, np.asarray(rows, dtype=float).T))
    if len(data[TIME]) != 2801 or not np.allclose(data[TIME], np.arange(2801) * DT_S, atol=1e-10, rtol=0):
        raise ValueError(f"Unexpected time grid in {entry['file']}")
    return data


def load_flight(folder: Path, record: dict, exports: dict) -> dict:
    fields = (TIME, COMMAND, ALTITUDE, VOLTAGE, *ACTUATORS)
    if record["controller"] == "battery_aware_mpc":
        fields += (AUXILIARY,)
    return read_export(folder, exports[record["trajectory"]], fields)


def smooth(signal: np.ndarray, tau_s: float) -> np.ndarray:
    decay = exp(-DT_S / tau_s)
    return lfilter([1 - decay], [1, -decay], signal)


def altitude_prediction(flight: dict, tau_s: float) -> np.ndarray:
    command = flight.get(AUXILIARY, flight[COMMAND])
    baseline = float(np.median(flight[ALTITUDE][flight[TIME] <= BASELINE_S]))
    return baseline + smooth(smooth(command - command[0], tau_s), tau_s)


def voltage_inputs(flight: dict, tau_s: float) -> tuple[float, np.ndarray]:
    baseline = flight[TIME] <= BASELINE_S
    drive = np.mean(np.square([flight[key] for key in ACTUATORS]), axis=0)
    delta = drive - np.median(drive[baseline])
    return float(np.median(flight[VOLTAGE][baseline])), np.column_stack((delta, smooth(delta, tau_s)))


def fit(calibration: list[dict], manifest_hash: str) -> dict:
    def tracking_error(tau_s: float) -> float:
        errors = [altitude_prediction(flight, tau_s) - flight[ALTITUDE] for flight in calibration]
        return float(np.mean([np.mean(np.abs(error[flight[TIME] > BASELINE_S]))
                              for error, flight in zip(errors, calibration)]))

    altitude_mae, altitude_tau = min((tracking_error(tau), tau) for tau in TIME_CONSTANTS_S)
    voltage_candidates = []
    for tau in TIME_CONSTANTS_S:
        designs, targets = [], []
        for flight in calibration:
            baseline_voltage, matrix = voltage_inputs(flight, tau)
            score = flight[TIME] > BASELINE_S
            designs.append(matrix[score])
            targets.append(baseline_voltage - flight[VOLTAGE][score])
        input_matrix, sag = np.vstack(designs), np.concatenate(targets)
        coefficients, residual = nnls(input_matrix, sag)
        voltage_candidates.append((float(residual), tau, coefficients.tolist()))
    _, voltage_tau, coefficients = min(voltage_candidates)
    return {
        "manifest_sha256": manifest_hash,
        "baseline_s": BASELINE_S,
        "voltage_reference_line_v": REFERENCE_LINE_V,
        "time_constant_grid_s": list(TIME_CONSTANTS_S),
        "altitude_time_constant_s": altitude_tau,
        "calibration_altitude_mae_m": round(altitude_mae, 9),
        "voltage_time_constant_s": voltage_tau,
        "voltage_coefficients": [round(value, 12) for value in coefficients],
    }


def first_below(time: np.ndarray, voltage: np.ndarray) -> float | None:
    below = np.flatnonzero(voltage < REFERENCE_LINE_V)
    return round(float(time[below[0]]), 9) if len(below) else None


def error_metrics(expected: np.ndarray, observed: np.ndarray) -> dict:
    error = expected - observed
    return {"mae": round(float(np.mean(np.abs(error))), 9),
            "mean_signed_error": round(float(np.mean(error)), 9),
            "maximum_absolute_error": round(float(np.max(np.abs(error))), 9)}


def evaluate(folder: Path, manifest: dict, frozen: dict) -> dict:
    results = []
    for record in manifest["holdout"]:
        flight = load_flight(folder, record, manifest["exports"])
        energy = read_export(folder, manifest["exports"][record["reported_energy"]], (TIME, "Power (W)", "Energy (J)"))
        if not np.allclose(flight[TIME], energy[TIME], atol=1e-10, rtol=0):
            raise ValueError("Trajectory and reported energy clocks differ")
        altitude = altitude_prediction(flight, frozen["altitude_time_constant_s"])
        baseline_voltage, voltage_matrix = voltage_inputs(flight, frozen["voltage_time_constant_s"])
        voltage = baseline_voltage - voltage_matrix @ frozen["voltage_coefficients"]
        after = flight[TIME] > BASELINE_S
        time = flight[TIME][after]
        observed_voltage = flight[VOLTAGE][after]
        results.append({
            "controller": record["controller"],
            "trajectory": record["trajectory"],
            "scored_samples": len(time),
            "altitude_prediction_error_m": error_metrics(altitude[after], flight[ALTITUDE][after]),
            "observed_nominal_tracking_error_m": error_metrics(flight[COMMAND][after], flight[ALTITUDE][after]),
            "measured_end_altitude_m": round(float(flight[ALTITUDE][-1]), 9),
            "predicted_end_altitude_m": round(float(altitude[-1]), 9),
            "voltage_prediction_error_v": error_metrics(voltage[after], observed_voltage),
            "held_baseline_voltage_error_v": error_metrics(np.full_like(observed_voltage, baseline_voltage), observed_voltage),
            "measured_min_voltage_v": round(float(np.min(observed_voltage)), 9),
            "predicted_min_voltage_v": round(float(np.min(voltage[after])), 9),
            "measured_first_below_reference_s": first_below(time, observed_voltage),
            "predicted_first_below_reference_s": first_below(time, voltage[after]),
            "reported_energy_delta_j": round(float(energy["Energy (J)"][-1] - energy["Energy (J)"][0]), 9),
            "integral_of_reported_power_j": round(float(trapezoid(energy["Power (W)"], energy[TIME])), 9),
        })
    return {"holdout": results, "acceptance_status": "two_conditional_flights_without_full_aircraft_acceptance"}


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
    calibration = [load_flight(args.source_dir, record, manifest["exports"]) for record in manifest["calibration"]]
    frozen = fit(calibration, sha256(manifest_text.encode()).hexdigest())
    if args.mode == "calibrate":
        result = frozen
    else:
        if frozen != json.loads(args.freeze.read_text(encoding="utf-8")):
            raise ValueError("Calibration did not reproduce the frozen model")
        result = evaluate(args.source_dir, manifest, frozen)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
