"""Calibrate and test rotor-order vibration on published UAV-FD flights."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.signal import lombscargle

PLAN = "m25-uavfd-rotor-order-v1"
SOURCE = "https://doi.org/10.5281/zenodo.7648996"
FILES = {
    "NO_FAULT1.mat": (31_477_776, "8fa683680232dae902d7c906853fb80f5b89ffb6b43ff8e97b708bd8f8473ba5"),
    "NO_FAULT4.mat": (43_712_272, "2a41050325fb9315cd2fd12429a31d3d7b1b2fef2a4802dada2eaea57ea3fcd3"),
    "NO_FAULT5.mat": (41_697_864, "85349d743ae4ea17aeb8bb4ac3c74fbe4c3f33ab8dc21b5ae29464e398c14cc2"),
    "FAULT_M3_10.mat": (15_650_896, "9bd3284274615b2c1db7168ff930a2474abdda7a0686f4dba09f2cef46efa46b"),
    "FAULT_M4_10.mat": (14_544_382, "1e99ccf414ac483d1945982a79b966caed5fe3385d0967b126d4624d0ff1a913"),
}
TRAIN = ("NO_FAULT1.mat", "NO_FAULT4.mat")
HOLDOUT = {"NO_FAULT5.mat": False, "FAULT_M3_10.mat": True, "FAULT_M4_10.mat": True}
WINDOW_S = 2.0
IMU_GAP_S = 0.025
OTHER_GAP_S = 0.5
MIN_WINDOW_COUNT = 6
ALERT_RUN = 2
QUANTILE = 0.95
RPM_RANGE = (3600, 7800)
ROTOR_NEIGHBORHOOD_HZ = 4


@dataclass(frozen=True)
class Signal:
    t: np.ndarray
    values: np.ndarray

    def window(self, start: float, end: float, gap: float, count: int) -> Signal | None:
        left, right = self.t.searchsorted((start, end), side="left")
        t = self.t[left:right]
        if len(t) < count or t[0] - start > gap or end - t[-1] > gap or np.diff(t).max() > gap:
            return None
        return Signal(t, self.values[left:right])


@dataclass(frozen=True)
class WindowScore:
    index: int
    median_rpm: float
    rotor_order: float
    accel_rms: float


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def checked_signal(data: dict, name: str, label: str, channels: tuple[str, ...]) -> Signal:
    labels = list(data[label])
    if len(labels) != len(set(labels)) or np.asarray(data[name]).shape[-1] != len(labels):
        raise ValueError(f"{name} does not match its source column dictionary")
    t = data[name][:, labels.index("TimeUS")] / 1e6
    values = data[name][:, [labels.index(c) for c in channels]]
    if not np.isfinite(t).all() or not np.isfinite(values).all() or np.any(np.diff(t) <= 0):
        raise ValueError(f"{name} has invalid timestamps or data")
    return Signal(t, values)


def read_verified_mat(directory: Path, name: str, fingerprints: dict, channels: list[str]) -> dict:
    path = directory / name
    expected_bytes, expected_digest = fingerprints[name]
    with path.open("rb") as stream:
        if path.stat().st_size != expected_bytes or hashlib.file_digest(stream, "sha256").hexdigest() != expected_digest:
            raise ValueError(f"{name} does not match the pinned publisher bytes")
    return loadmat(path, variable_names=channels, simplify_cells=True)


def load(directory: Path, name: str, fingerprints: dict) -> tuple[Signal, Signal, list[Signal]]:
    esc_names = [f"ESC_{index}" for index in range(6)]
    data = read_verified_mat(
        directory, name, fingerprints, ["IMU_0", "IMU_label", "CTUN", "CTUN_label", *esc_names, "ESC_label"],
    )
    imu = checked_signal(data, "IMU_0", "IMU_label", ("AccX", "AccY", "AccZ"))
    altitude = checked_signal(data, "CTUN", "CTUN_label", ("Alt",))
    motors = [checked_signal(data, name_, "ESC_label", ("RPM",)) for name_ in esc_names]
    return imu, altitude, motors


def spectral_score(t: np.ndarray, acceleration: np.ndarray, motor_rpm: np.ndarray) -> tuple[float, float]:
    local_t = t - t[0]
    design = np.column_stack((np.ones(len(t)), local_t))
    centered = acceleration - design @ np.linalg.lstsq(design, acceleration, rcond=None)[0]
    frequencies = np.arange(55.0, 136.0)
    nearby = (np.abs(frequencies[:, None] - motor_rpm / 60) <= ROTOR_NEIGHBORHOOD_HZ).any(axis=1)
    near_frequencies = frequencies[nearby]
    if not len(near_frequencies) or near_frequencies[-1] >= 0.4 / float(np.median(np.diff(t))):
        raise ValueError("rotor order outside the logged frequency support")
    omega = 2 * np.pi * near_frequencies
    power = sum(lombscargle(local_t, axis, omega) for axis in centered.T)
    reference_factor = (np.median(motor_rpm) / 6000) ** 2
    score = np.sqrt(4 * np.max(power) / len(t)) / reference_factor
    rms = np.sqrt(np.mean(np.sum(centered ** 2, axis=1)))
    return float(score), float(rms)


def extract(directory: Path, name: str, fingerprints: dict = FILES) -> tuple[list[WindowScore], dict[str, int]]:
    imu, altitude, motors = load(directory, name, fingerprints)
    rejected = Counter()
    scores = []
    count = int((imu.t[-1] - imu.t[0]) // WINDOW_S)
    for index in range(count):
        start = float(imu.t[0] + index * WINDOW_S)
        end = start + WINDOW_S
        height = altitude.window(start, end, OTHER_GAP_S, 5)
        if height is None or (height.values < 1).any():
            rejected["altitude_or_ground_context"] += 1
            continue
        acceleration = imu.window(start, end, IMU_GAP_S, 300)
        if acceleration is None:
            rejected["imu_gap_or_count"] += 1
            continue
        active_motors = [m.window(start, end, OTHER_GAP_S, 5) for m in motors]
        if any(m is None for m in active_motors):
            rejected["esc_gap_or_count"] += 1
            continue
        if any((m.values < RPM_RANGE[0]).any() or (m.values > RPM_RANGE[1]).any() for m in active_motors):
            rejected["outside_rotor_speed_scope"] += 1
            continue
        rpm = np.array([np.median(m.values) for m in active_motors])
        try:
            rotor_order, accel_rms = spectral_score(acceleration.t, acceleration.values, rpm)
        except ValueError:
            rejected["outside_frequency_support"] += 1
            continue
        scores.append(WindowScore(index, float(np.median(rpm)), rotor_order, accel_rms))
    return scores, dict(rejected)


def calibrate(directory: Path) -> dict:
    by_flight = {name: extract(directory, name) for name in TRAIN}
    if any(len(values[0]) < MIN_WINDOW_COUNT for values in by_flight.values()):
        raise ValueError("insufficient eligible windows in a healthy calibration flight")
    pooled = [window for scores, _ in by_flight.values() for window in scores]
    rpm = [w.median_rpm for w in pooled]
    thresholds = {
        k: round(float(np.quantile([getattr(w, k) for w in pooled], QUANTILE, method="higher")), 9)
        for k in ("rotor_order", "accel_rms")
    }
    return {
        "plan": PLAN, "source": SOURCE,
        "source_files": {k: {"bytes": size, "sha256": sha} for k, (size, sha) in FILES.items()},
        "calibration_flights": {k: {"eligible_windows": len(items), "rejections": bad}
                                for k, (items, bad) in by_flight.items()},
        "healthy_calibration_median_rpm_support": [min(rpm), max(rpm)],
        "thresholds": thresholds,
    }


def decide(scores: list[WindowScore], feature: str, threshold: float) -> dict:
    exceedances = [w.index for w in scores if getattr(w, feature) > threshold]
    # A missing or discarded window breaks the consecutive alarm run.
    run = max_run = 0
    prev = None
    first_alert = None
    for index in exceedances:
        run = run + 1 if prev is not None and index == prev + 1 else 1
        max_run = max(max_run, run)
        if run == ALERT_RUN and first_alert is None:
            first_alert = index
        prev = index
    return {
        "threshold": threshold,
        "exceeding_windows": len(exceedances),
        "longest_consecutive_exceedance": max_run,
        "first_alert_window": first_alert if len(scores) >= MIN_WINDOW_COUNT else None,
        "verdict": ("INCONCLUSIVE_INSUFFICIENT_WINDOWS" if len(scores) < MIN_WINDOW_COUNT
                    else "FAULT_INDICATOR_ALERT" if first_alert is not None else "NO_ALERT"),
    }


def compare(directory: Path, freeze: dict) -> dict:
    lo, hi = freeze["healthy_calibration_median_rpm_support"]
    result = {}
    for source, known_fault in HOLDOUT.items():
        complete, rejected = extract(directory, source)
        comparable = [w for w in complete if lo <= w.median_rpm <= hi]
        rejected["outside_calibration_median_rpm_support"] = len(complete) - len(comparable)
        decisions = {key: decide(comparable, key, value) for key, value in freeze["thresholds"].items()}
        for decision in decisions.values():
            verdict = decision["verdict"]
            if verdict.startswith("INCONCLUSIVE"):
                decision["agreement"] = "UNTESTED"
            elif known_fault:
                decision["agreement"] = "DETECTED" if verdict == "FAULT_INDICATOR_ALERT" else "MISSED"
            else:
                decision["agreement"] = "FALSE_ALERT" if verdict == "FAULT_INDICATOR_ALERT" else "NO_ALERT_ON_HEALTHY_SOURCE"
        result[source] = {
            "published_fault_label": known_fault, "eligible_windows": len(comparable),
            "excluded_windows": rejected, "models": decisions,
        }
    return {"plan": PLAN, "frozen_thresholds_canonical_sha256": digest(freeze), "flights": result,
            "acceptance": "INCONCLUSIVE_FOR_STRUCTURAL_OR_FLIGHT_ACCEPTANCE"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "evaluate"))
    parser.add_argument("originals", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    fit = calibrate(args.originals)
    if args.action == "evaluate":
        if args.freeze is None or digest(json.loads(args.freeze.read_bytes())) != digest(fit):
            parser.error("the frozen thresholds must reproduce from the healthy source flights")
        report = compare(args.originals, fit)
    else:
        report = fit
    args.output.write_bytes((json.dumps(report, indent=2, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
