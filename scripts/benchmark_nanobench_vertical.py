"""Fit and evaluate a conditional vertical-motion benchmark on NanoBench exports."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

import numpy as np
from scipy.integrate import trapezoid
from scipy.optimize import nnls

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from physics.aerodynamics.drag import AirframeDrag
from physics.constants import SEA_LEVEL_AIR_DENSITY, STANDARD_GRAVITY
from physics.integration.rk4 import rk4_step

SOURCE_RECEIPT = ROOT / "data/benchmarks/flight/nanobench_source_receipt.json"
PLAN = "m26-nanobench-vertical-v1"
MASS_KG = 0.04085
HORIZON_ROWS = {0.5: 50, 1.0: 100, 2.0: 200}
MAX_GAP_S = 0.02
MIN_START_ALTITUDE_M = 0.4
CALIBRATION_MIN_ALTITUDE_M = 0.4
BAND_QUANTILE = 0.9
QUATERNION_CHANNELS = ("qx", "qy", "qz", "qw")
MOTOR_CHANNELS = tuple(f"motor_motor_m{i}" for i in range(1, 5))
CHANNELS = ("t", "pz", "vx", "vy", "vz", *QUATERNION_CHANNELS, *MOTOR_CHANNELS, "pwr_pm_vbat")


@dataclass
class Flight:
    name: str
    data: np.ndarray
    raw_channel_counts: dict[str, int]

    @property
    def time(self) -> np.ndarray:
        return self.data["t"]


def sha(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def json_sha(value: dict | list) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verified(directory: Path, entry: dict) -> Path:
    path = directory / Path(entry["path"]).name
    if path.stat().st_size != entry["bytes"] or sha(path) != entry["sha256"]:
        raise ValueError(f"{path.name} differs from the pinned publisher export")
    return path


def read_flights(directory: Path, role: str) -> list[Flight]:
    entries = {Path(e["path"]).name: e for e in json.loads(SOURCE_RECEIPT.read_bytes())}
    result = []
    for filename, entry in entries.items():
        if entry["role"] != role or not filename.endswith(".csv"):
            continue
        file = verified(directory, entry)
        metadata_name = f"{file.stem}_metadata.yaml"
        metadata = verified(directory, entries[metadata_name]).read_text(encoding="utf-8")
        if not re.search(r"^crazyflie_id: CF_01$", metadata, re.MULTILINE) or not re.search(
            r"^firmware_version: 2025\.12\.1$", metadata, re.MULTILINE
        ):
            raise ValueError(f"{file.stem} has a different aircraft or firmware")
        counts = {
            key: int(value) for key, value in re.findall(
                r"^  (vicon|motor|power): ([1-9][0-9]*)$", metadata, re.MULTILINE
            )
        }
        if set(counts) != {"vicon", "motor", "power"}:
            raise ValueError(f"{metadata_name} lacks original sample counts")
        with file.open(encoding="utf-8", newline="") as stream:
            header = next(csv.reader(stream, strict=True))
        if len(header) != len(set(header)) or not set(CHANNELS).issubset(header):
            raise ValueError(f"{filename} lacks required unique columns")
        data = np.genfromtxt(
            file, delimiter=",", names=True, usecols=tuple(header.index(name) for name in CHANNELS),
            encoding="utf-8",
        )
        if data.ndim != 1 or len(data) < 201 or not np.isfinite(data["t"]).all():
            raise ValueError(f"{filename} lacks a usable time series")
        if (np.diff(data["t"]) <= 0).any():
            raise ValueError(f"{filename} has a non-increasing timestamp")
        result.append(Flight(file.stem, data, counts))
    return result


def admissible_windows(flight: Flight, horizon_s: float, *, calibration: bool = False):
    width = HORIZON_ROWS[horizon_s]
    rejected = Counter()
    accepted = []
    for start in range(0, len(flight.data) - width, width):
        end = start + width
        block = flight.data[start:end + 1]
        numeric = np.column_stack([block[channel] for channel in CHANNELS])
        motor = np.column_stack([block[channel] for channel in MOTOR_CHANNELS])
        attitude = np.column_stack([block[channel] for channel in QUATERNION_CHANNELS])
        if not np.isfinite(numeric).all():
            rejected["missing_or_nonfinite_channel"] += 1
        elif np.diff(block["t"]).max() > MAX_GAP_S or abs(
            block["t"][-1] - block["t"][0] - horizon_s
        ) > MAX_GAP_S:
            rejected["sampling_gap_or_duration"] += 1
        elif block["pz"][0] < MIN_START_ALTITUDE_M or (
            calibration and block["pz"].min() < CALIBRATION_MIN_ALTITUDE_M
        ):
            rejected["below_initial_or_calibration_height"] += 1
        elif (motor < 0).any() or (motor > 65535).any() or (
            block["pwr_pm_vbat"] <= 0
        ).any():
            rejected["invalid_input"] += 1
        elif np.max(abs(np.linalg.norm(attitude, axis=1) - 1)) > 0.01:
            rejected["invalid_attitude"] += 1
        else:
            accepted.append((start, end))
    return accepted, dict(rejected)


def model_inputs(block: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    q_norm_sq = sum(block[key] ** 2 for key in QUATERNION_CHANNELS)
    up_cosine = 1 - 2 * (block["qx"] ** 2 + block["qy"] ** 2) / q_norm_sq
    pwm_squared = sum((block[key] / 65535) ** 2 for key in MOTOR_CHANNELS)
    thrust_proxy = up_cosine * block["pwr_pm_vbat"] ** 2 * pwm_squared
    return thrust_proxy, np.hypot(block["vx"], block["vy"])


def fit(flights: list[Flight]) -> tuple[np.ndarray, dict[str, int]]:
    equations = []
    counts = {}
    for flight in flights:
        windows, _ = admissible_windows(flight, 0.5, calibration=True)
        counts[flight.name] = len(windows)
        for start, end in windows:
            block = flight.data[start:end + 1]
            t, vz = block["t"], block["vz"]
            thrust, horizontal = model_inputs(block)
            drag = -0.5 * SEA_LEVEL_AIR_DENSITY * np.hypot(horizontal, vz) * vz
            equations.append((trapezoid(thrust, t), trapezoid(drag, t),
                              MASS_KG * (vz[-1] - vz[0] + STANDARD_GRAVITY * (t[-1] - t[0]))))
    design = np.array(equations)
    if len(equations) < 20 or np.linalg.matrix_rank(design[:, :2]) != 2:
        raise ValueError("calibration flights do not identify both model inputs")
    parameters, _ = nnls(design[:, :2], design[:, 2])
    return np.round(parameters, 12), counts


def forecast(block: np.ndarray, parameters: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    thrust, horizontal_speed = model_inputs(block)
    altitude, speed = block["pz"], block["vz"]
    state = np.array([altitude[0], speed[0]])
    t = block["t"]
    drag = AirframeDrag(float(parameters[1])) if parameters[1] > 0 else None
    for i, dt in enumerate(np.diff(t)):
        start_t = t[i]

        def derivative(at: float, vertical_state: np.ndarray) -> np.ndarray:
            fraction = min(1.0, max(0.0, (at - start_t) / dt))
            thrust_at = thrust[i] + fraction * (thrust[i + 1] - thrust[i])
            horizontal = horizontal_speed[i] + fraction * (horizontal_speed[i + 1] - horizontal_speed[i])
            velocity = float(vertical_state[1])
            drag_n = drag.force_world(np.array([horizontal, 0.0, velocity]))[2] if drag else 0.0
            return np.array([velocity, (parameters[0] * thrust_at + drag_n) / MASS_KG - STANDARD_GRAVITY])

        state = rk4_step(derivative, start_t, state, dt)
    measurement = np.array([altitude[-1], speed[-1]])
    baseline = np.array([altitude[0] + speed[0] * (t[-1] - t[0]), speed[0]])
    return state - measurement, baseline - measurement


def residuals(flight: Flight, horizon: float, parameters: np.ndarray, *, calibration: bool = False):
    windows, rejected = admissible_windows(flight, horizon, calibration=calibration)
    rows = []
    for start, end in windows:
        block = flight.data[start:end + 1]
        model, baseline = forecast(block, parameters)
        rows.append({
            "csv_lines": [start + 2, end + 2],
            "model_error": model.tolist(),
            "baseline_error": baseline.tolist(),
            "visits_below_0_4_m": bool(block["pz"].min() < MIN_START_ALTITUDE_M),
        })
    return rows, rejected


def calibrate(directory: Path) -> dict:
    flights = read_flights(directory, "calibration")
    if len(flights) != 2:
        raise ValueError("the freeze requires the two pinned calibration flights")
    parameters, counts = fit(flights)
    folds = [(test, fit([train])[0]) for test, train in (flights, flights[::-1])]
    bands = {}
    for horizon in HORIZON_ROWS:
        fold_errors = [
            row["model_error"]
            for test_flight, fitted in folds
            for row in residuals(test_flight, horizon, fitted, calibration=True)[0]
        ]
        if not fold_errors:
            raise ValueError(f"no cross-flight calibration residuals for {horizon} s")
        bands[str(horizon)] = {
            "absolute_half_width_altitude_m_and_velocity_m_s": np.round(
                np.quantile(np.abs(fold_errors), BAND_QUANTILE, axis=0, method="higher"), 9
            ).tolist(),
            "calibration_windows": len(fold_errors),
        }
    return {
        "plan": PLAN,
        "source_receipt_canonical_json_sha256": json_sha(json.loads(SOURCE_RECEIPT.read_bytes())),
        "vehicle_id": "CF_01",
        "firmware": "2025.12.1",
        "flight_mass_kg": MASS_KG,
        "thrust_n_per_v_squared": parameters[0],
        "effective_drag_area_m2": parameters[1],
        "fit_windows_0_5_s": counts,
        "cross_flight_90th_percentile_bands": bands,
    }


def summarize(rows: list[dict], band: list[float]) -> dict:
    report = {"windows": len(rows), "visits_below_0_4_m": sum(row["visits_below_0_4_m"] for row in rows)}
    if rows:
        for model in ("model", "baseline"):
            errors = np.asarray([row[f"{model}_error"] for row in rows])
            outputs = {}
            for index, name in enumerate(("altitude_m", "vertical_velocity_m_s")):
                series = errors[:, index]
                outputs[name] = {
                    "mae": round(float(np.mean(np.abs(series))), 9),
                    "rmse": round(float(np.sqrt(np.mean(series ** 2))), 9),
                    "bias": round(float(np.mean(series)), 9),
                    "max_abs": round(float(np.max(np.abs(series))), 9),
                }
                if model == "model":
                    outputs[name]["calibration_band_coverage"] = round(
                        float(np.mean(np.abs(series) <= band[index])), 9
                    )
            report[model] = outputs
    return report


def evaluate(directory: Path, freeze_path: Path) -> dict:
    freeze = json.loads(freeze_path.read_bytes())
    if freeze != calibrate(directory):
        raise ValueError("the freeze does not reproduce from the pinned calibration flights")
    parameters = np.array([freeze["thrust_n_per_v_squared"], freeze["effective_drag_area_m2"]])
    if not np.isfinite(parameters).all() or (parameters < 0).any():
        raise ValueError("invalid frozen force-model parameter")
    flights = read_flights(directory, "holdout")
    if len(flights) != 3:
        raise ValueError("the campaign requires three whole held-out flights")
    report = {}
    for horizon in HORIZON_ROWS:
        key = str(horizon)
        band = freeze["cross_flight_90th_percentile_bands"][key]["absolute_half_width_altitude_m_and_velocity_m_s"]
        scored = {}
        for flight in flights:
            rows, rejected = residuals(flight, horizon, parameters)
            scored[flight.name] = {
                "summary": summarize(rows, band),
                "source_channel_counts_before_resampling": flight.raw_channel_counts,
                "published_rows": len(flight.data),
                "excluded_windows_by_reason": rejected,
                "window_residuals": [
                    {**row, "model_error": [round(v, 9) for v in row["model_error"]],
                     "baseline_error": [round(v, 9) for v in row["baseline_error"]]}
                    for row in rows
                ],
            }
        report[key] = {
            "calibration_band_altitude_m_and_velocity_m_s": band,
            "summary": summarize(list(chain.from_iterable(s["window_residuals"] for s in scored.values())), band),
            "holdout_flights": scored,
        }
    return {"plan": PLAN, "frozen_calibration_canonical_json_sha256": json_sha(freeze),
            "verdict": "INCONCLUSIVE_FOR_FLIGHT_ACCEPTANCE", "horizons_s": report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "evaluate"))
    parser.add_argument("originals", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.action == "calibrate":
        result = calibrate(args.originals)
    else:
        if args.freeze is None:
            parser.error("evaluation requires --freeze")
        result = evaluate(args.originals, args.freeze)
    args.output.write_bytes((json.dumps(result, indent=2, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
