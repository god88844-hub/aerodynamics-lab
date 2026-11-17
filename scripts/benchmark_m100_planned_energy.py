"""Freeze and score planned-route energy predictions on the CMU M100 flights."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from scipy.integrate import trapezoid
from scipy.optimize import nnls

PLAN = "m26-m100-planned-energy-v1"
CUTOFF = "2019-08-01"
FILES = {
    "CMU-M100-flights.zip": (26385070, 41274360, "98f65a1ab54a8b618c169fdf49311a53ff1fefed86fdc3f440d6a0166ce49fb1"),
    "CMU-M100-parameters.csv": (26385034, 7867, "568dffaed11a4d335ef4f8a932b342c836907af2f4aa54da9b4a0e2ffef2108a"),
    "CMU-M100-README.txt": (26405786, 25101, "8601dd211d6c297c5411992dc34923bdb98b72cdc287517ed18e479f0e9540fd"),
}
REQUIRED_CHANNELS = ("time", "battery_voltage", "battery_current")


def digest_json(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def pinned(directory: Path, filename: str) -> Path:
    _, count, expected = FILES[filename]
    path = directory / filename
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if path.stat().st_size != count or actual != expected:
        raise ValueError(f"{filename} does not match the pinned publisher release")
    return path


@dataclass(frozen=True)
class Mission:
    flight: int
    date: str
    speed_m_s: int
    altitude_m: int
    payload_g: int

    @property
    def setting(self) -> str:
        return f"{self.speed_m_s}/{self.altitude_m}/{self.payload_g}"

    @property
    def duration_inputs(self) -> tuple[float, ...]:
        return 1.0, 1 / self.speed_m_s, float(self.altitude_m)

    @property
    def power_inputs(self) -> tuple[float, ...]:
        return 1.0, self.payload_g / 1000


def partition(directory: Path, mode: str) -> list[Mission]:
    path = pinned(directory, "CMU-M100-parameters.csv")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    eligible = []
    for row in rows:
        if row["route"] != "R1":
            continue
        speed, payload, altitude = (float(row[key]) for key in ("speed", "payload", "altitude"))
        if (
            speed in (4, 6, 8, 10, 12)
            and altitude in (25, 50, 75, 100) and payload in (0, 250, 500)
        ):
            role = "calibration" if row["date"] < CUTOFF else "holdout"
            if role == mode:
                eligible.append(Mission(int(row["flight"]), row["date"], int(speed), int(altitude), int(payload)))
    if len({m.flight for m in eligible}) != len(eligible):
        raise ValueError("duplicate flight in manifest")
    return eligible


def metered_record(archive: ZipFile, mission: Mission) -> dict:
    with archive.open(f"flights/{mission.flight}.csv") as stream:
        header = next(csv.reader([stream.readline().decode("utf-8-sig")]))
        if len(header) != len(set(header)) or not set(REQUIRED_CHANNELS).issubset(header):
            return {"status": "MISSING_UNAMBIGUOUS_METER_CHANNELS"}
        try:
            t, voltage, current = np.loadtxt(
                stream, delimiter=",", usecols=tuple(header.index(c) for c in REQUIRED_CHANNELS),
                unpack=True, ndmin=2,
            )
        except ValueError:
            return {"status": "MISSING_OR_MALFORMED_METER_DATA"}
    if len(t) < 5 or not np.isfinite([t, voltage, current]).all():
        return {"status": "INSUFFICIENT_FINITE_METER_DATA"}
    spacing = np.diff(t)
    bounds = {"rows": len(t), "max_gap_s": round(float(np.max(spacing)), 9)}
    if np.min(spacing) <= 0 or np.max(spacing) > 1:
        return {"status": "CLOCK_OR_GAP_REJECTION", **bounds}
    if (voltage <= 0).any() or (voltage > 33).any() or (np.abs(current) > 200).any():
        return {"status": "OUTSIDE_DOCUMENTED_METER_RANGE", **bounds}
    energy = float(trapezoid(voltage * current, t) / 3600)
    if energy <= 0:
        return {"status": "NONPOSITIVE_NET_RECORDED_ENERGY", **bounds}
    return {"status": "SCORED", "measured_energy_wh": energy, "record_duration_s": float(t[-1] - t[0]), **bounds}


def coefficients(rows: list[tuple[Mission, dict]]) -> tuple[np.ndarray, np.ndarray]:
    times = np.array([m.duration_inputs for m, _ in rows])
    powers = np.array([m.power_inputs for m, _ in rows])
    duration = np.array([r["record_duration_s"] for _, r in rows])
    average = np.array([r["measured_energy_wh"] for _, r in rows]) * 3600 / duration
    if np.linalg.matrix_rank(times) != 3 or np.linalg.matrix_rank(powers) != 2:
        raise ValueError("insufficient variation for the planned-route model")
    return np.round(nnls(times, duration)[0], 10), np.round(nnls(powers, average)[0], 10)


def predict(mission: Mission, time_weights: np.ndarray, power_weights: np.ndarray) -> tuple[float, float]:
    duration = float(mission.duration_inputs @ time_weights)
    watts = float(mission.power_inputs @ power_weights)
    return duration, duration * watts / 3600


def calibrate(directory: Path) -> dict:
    pinned(directory, "CMU-M100-README.txt")
    missions = partition(directory, "calibration")
    records, exclusions = [], {}
    with ZipFile(pinned(directory, "CMU-M100-flights.zip")) as archive:
        for mission in missions:
            result = metered_record(archive, mission)
            if result["status"] == "SCORED":
                records.append((mission, result))
            else:
                exclusions[str(mission.flight)] = result
    dates = sorted({m.date for m, _ in records})
    folds = []
    for date in dates:
        time_weights, power_weights = coefficients([r for r in records if r[0].date != date])
        for mission, actual in records:
            if mission.date == date:
                _, energy = predict(mission, time_weights, power_weights)
                folds.append(abs(energy - actual["measured_energy_wh"]))
    time_weights, power_weights = coefficients(records)
    settings = defaultdict(list)
    for mission, record in records:
        settings[mission.setting].append(record["measured_energy_wh"])
    return {
        "plan": PLAN,
        "provider_doi": "10.1184/R1/12683453.v1",
        "source_files": {name: {"file_id": i, "bytes": n, "sha256": h} for name, (i, n, h) in FILES.items()},
        "cutoff_date": CUTOFF,
        "calibration_days": dates,
        "calibration_scored_flights": [m.flight for m, _ in records],
        "calibration_exclusions": exclusions,
        "duration_intercept_effective_distance_climb_time": time_weights.tolist(),
        "power_intercept_and_payload_w_per_kg": power_weights.tolist(),
        "global_mean_energy_wh": round(float(np.mean([r["measured_energy_wh"] for _, r in records])), 9),
        "settings_mean_energy_wh": {k: round(float(np.mean(v)), 9) for k, v in sorted(settings.items())},
        "leave_date_out_90th_percentile_energy_half_width_wh": round(float(np.quantile(folds, 0.9, method="higher")), 9),
    }


def error_summary(errors: np.ndarray) -> dict:
    if not errors.size:
        return {}
    return {k: round(float(v), 9) for k, v in {
        "mae": np.mean(np.abs(errors)), "rmse": np.sqrt(np.mean(errors ** 2)),
        "bias": np.mean(errors), "max_abs": np.max(np.abs(errors)),
    }.items()}


def evaluate(directory: Path, freeze_path: Path) -> dict:
    freeze = json.loads(freeze_path.read_bytes())
    if freeze != calibrate(directory):
        raise ValueError("frozen model does not reproduce from its calibration partition")
    time_weights = np.array(freeze["duration_intercept_effective_distance_climb_time"])
    power_weights = np.array(freeze["power_intercept_and_payload_w_per_kg"])
    band = freeze["leave_date_out_90th_percentile_energy_half_width_wh"]
    settings = freeze["settings_mean_energy_wh"]
    missions = partition(directory, "holdout")
    rows = []
    with ZipFile(pinned(directory, "CMU-M100-flights.zip")) as archive:
        for mission in missions:
            # This prediction consumes only the planned configuration.
            duration, energy = predict(mission, time_weights, power_weights)
            baseline = settings.get(mission.setting, freeze["global_mean_energy_wh"])
            actual = metered_record(archive, mission)
            row = {
                "flight": mission.flight, "date": mission.date, "setting_speed_altitude_payload": mission.setting,
                "predicted_record_duration_s": round(duration, 9), "predicted_energy_wh": round(energy, 9),
                "configuration_baseline_wh": baseline,
                "configuration_baseline_has_exact_match": mission.setting in settings,
                **actual,
            }
            if actual["status"] == "SCORED":
                wh = actual["measured_energy_wh"]
                row.update({
                    "energy_error_wh": round(energy - wh, 9), "baseline_error_wh": round(baseline - wh, 9),
                    "duration_error_s": round(duration - actual["record_duration_s"], 9),
                    "inside_calibration_error_band": abs(energy - wh) <= band,
                })
            rows.append(row)
    scored = [r for r in rows if r["status"] == "SCORED"]
    return {
        "plan": PLAN, "frozen_calibration_canonical_json_sha256": digest_json(freeze),
        "verdict": "INCONCLUSIVE_FOR_FLIGHT_ACCEPTANCE",
        "scored": len(scored), "total_holdouts": len(rows),
        "empirical_energy_half_width_wh": band,
        "heldout_energy_band_coverage": round(float(np.mean([r["inside_calibration_error_band"] for r in scored])), 9) if scored else None,
        "energy_errors_wh": error_summary(np.array([r["energy_error_wh"] for r in scored])),
        "configuration_baseline_errors_wh": error_summary(np.array([r["baseline_error_wh"] for r in scored])),
        "record_duration_errors_s": error_summary(np.array([r["duration_error_s"] for r in scored])),
        "holdouts": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "evaluate"))
    parser.add_argument("originals", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.action == "calibrate":
        report = calibrate(args.originals)
    else:
        if args.freeze is None:
            parser.error("evaluation requires --freeze")
        report = evaluate(args.originals, args.freeze)
    args.output.write_bytes((json.dumps(report, indent=2, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
