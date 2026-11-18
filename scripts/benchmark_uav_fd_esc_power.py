"""Evaluate ESC power deficits on physically labeled UAV-FD flights."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import benchmark_uav_fd_rotor_order as vibration
from benchmark_uav_fd_rotor_order import (
    ALERT_RUN, FILES as EARLIER_FILES, MIN_WINDOW_COUNT, OTHER_GAP_S, QUANTILE,
    RPM_RANGE, SOURCE, TRAIN, WINDOW_S, checked_signal, digest, read_verified_mat,
)

PLAN = "m25-uavfd-esc-power-v1"
HOLDOUT = {"NO_FAULT6.mat": False, "FAULT_M1_10.mat": True, "FAULT_M5_10.mat": True}
NEW_FILES = {
    "NO_FAULT6.mat": (45_466_208, "fe5d6f3f02fc8a99a076ba5d251f7f341c7ff7c5759bc42283c971b9aff52cab"),
    "FAULT_M1_10.mat": (18_742_480, "5bfcc4846cc265fa2fe58d65561f09260644090a3f5cd02582a10fb4ea86a840"),
    "FAULT_M5_10.mat": (17_520_095, "503844932d09b0ab8c243e6b986c2f979271843af3de7709f15a172f09a45d53"),
}
ESC_NAMES = [f"ESC_{i}" for i in range(6)]
FEATURES = ("speed_normalized_power", "power_baseline")


@dataclass(frozen=True)
class EscWindow:
    index: int
    rpm: float
    speed_normalized_power: np.ndarray
    power_baseline: np.ndarray


def extract(directory: Path, filename: str, fingerprints: dict) -> tuple[list[EscWindow], dict]:
    data = read_verified_mat(
        directory, filename, fingerprints, ["CTUN", "CTUN_label", "ATT", "ATT_label", *ESC_NAMES, "ESC_label"],
    )
    height = checked_signal(data, "CTUN", "CTUN_label", ("Alt",))
    attitude = checked_signal(data, "ATT", "ATT_label", ("Roll", "Pitch"))
    motors = [checked_signal(data, name, "ESC_label", ("RPM", "Volt", "Curr")) for name in ESC_NAMES]
    result = []
    rejected = Counter()
    count = int((height.t[-1] - height.t[0]) // WINDOW_S)
    for index in range(count):
        start = float(height.t[0] + index * WINDOW_S)
        end = start + WINDOW_S
        h = height.window(start, end, OTHER_GAP_S, 5)
        a = attitude.window(start, end, OTHER_GAP_S, 5)
        if h is None or a is None or (h.values < 1).any() or (np.abs(a.values) > 20).any():
            rejected["unsupported_altitude_or_attitude"] += 1
            continue
        sensed = [m.window(start, end, OTHER_GAP_S, 5) for m in motors]
        if any(m is None for m in sensed):
            rejected["incomplete_esc_windows"] += 1
            continue
        rows = [m.values for m in sensed]
        if any(
            (v[:, 0] < RPM_RANGE[0]).any() or (v[:, 0] > RPM_RANGE[1]).any() or (v[:, 1:] <= 0).any()
            for v in rows
        ):
            rejected["rotor_speed_or_nonpositive_electrical_input"] += 1
            continue
        speed = np.stack([np.median(v[:, 0]) for v in rows])
        watts = [v[:, 1] * v[:, 2] for v in rows]
        coefficient = np.array([
            float(np.median(w / (v[:, 0] / 6000) ** 3)) for w, v in zip(watts, rows, strict=True)
        ])
        electrical_power = np.array([float(np.median(w)) for w in watts])
        result.append(EscWindow(index, float(np.median(speed)), coefficient, electrical_power))
    return result, dict(rejected)


def deficit(window: EscWindow, feature: str, healthy_center: np.ndarray) -> tuple[int, float]:
    relative = getattr(window, feature) / healthy_center
    residual = 1 - relative / np.median(relative)
    motor = int(np.argmax(residual))
    return motor, float(residual[motor])


def calibrate(directory: Path) -> dict:
    fingerprints = {**EARLIER_FILES, **NEW_FILES}
    records = {filename: extract(directory, filename, fingerprints) for filename in TRAIN}
    if any(len(windows) < MIN_WINDOW_COUNT for windows, _ in records.values()):
        raise ValueError("too few eligible healthy calibration windows")
    all_windows = [window for windows, _ in records.values() for window in windows]
    models = {}
    for feature in FEATURES:
        center = np.median([getattr(w, feature) for w in all_windows], axis=0).round(9)
        threshold = np.quantile([deficit(w, feature, center)[1] for w in all_windows], QUANTILE, method="higher")
        models[feature] = {"motor_healthy_centers": center.tolist(), "deficit_threshold": round(float(threshold), 9)}
    rpm = [w.rpm for w in all_windows]
    vibration_fit = vibration.calibrate(directory)
    return {
        "plan": PLAN, "source": SOURCE,
        "source_files": {n: {"bytes": size, "sha256": sha} for n, (size, sha) in fingerprints.items()
                         if n in TRAIN or n in HOLDOUT},
        "calibration_flights": {n: {"eligible_windows": len(w), "exclusions": r} for n, (w, r) in records.items()},
        "calibrated_median_rpm": [min(rpm), max(rpm)],
        "vibration_calibration": vibration_fit,
        "models": models,
    }


def decide(windows: list[EscWindow], feature: str, fit: dict) -> dict:
    center = np.array(fit["motor_healthy_centers"])
    threshold = fit["deficit_threshold"]
    previous = None
    run = 0
    repeated = Counter()
    first = None
    above = 0
    for w in windows:
        motor, score = deficit(w, feature, center)
        if score <= threshold:
            continue
        above += 1
        run = run + 1 if previous == (w.index - 1, motor) else 1
        previous = (w.index, motor)
        if run == ALERT_RUN:
            repeated[f"ESC_{motor}"] += 1
            if first is None:
                first = w.index
    supported = len(windows) >= MIN_WINDOW_COUNT
    return {
        "tested_windows": len(windows), "above_threshold_windows": above,
        "repeat_alarms_by_source_esc": dict(repeated),
        "first_alert_window": first if supported else None,
        "verdict": ("INCONCLUSIVE_INSUFFICIENT_WINDOWS" if not supported
                    else "ESC_POWER_ALERT" if first is not None else "NO_ALERT"),
    }


def compare(directory: Path, freeze: dict) -> dict:
    fingerprints = {**EARLIER_FILES, **NEW_FILES}
    lo, hi = freeze["calibrated_median_rpm"]
    vibration_fit = freeze["vibration_calibration"]
    low_vib, high_vib = vibration_fit["healthy_calibration_median_rpm_support"]
    results = {}
    for name, fault in HOLDOUT.items():
        windows, rejected = extract(directory, name, fingerprints)
        accepted = [w for w in windows if lo <= w.rpm <= hi]
        rejected["outside_healthy_median_rpm"] = len(windows) - len(accepted)
        scores = {f: decide(accepted, f, freeze["models"][f]) for f in FEATURES}
        vib, vib_exclusions = vibration.extract(directory, name, fingerprints)
        vib_accepted = [w for w in vib if low_vib <= w.median_rpm <= high_vib]
        vib_exclusions["outside_healthy_median_rpm"] = len(vib) - len(vib_accepted)
        scores["rotor_order_vibration"] = {
            "tested_windows": len(vib_accepted), "window_exclusions": vib_exclusions,
            **vibration.decide(vib_accepted, "rotor_order", vibration_fit["thresholds"]["rotor_order"]),
        }
        primary = (scores["speed_normalized_power"]["verdict"], scores["rotor_order_vibration"]["verdict"])
        if any(status.endswith("_ALERT") for status in primary):
            combined = "COMBINED_ALERT"
        elif any(status.startswith("INCONCLUSIVE") for status in primary):
            combined = "INCONCLUSIVE_INSUFFICIENT_WINDOWS"
        else:
            combined = "NO_ALERT"
        scores["either_indicator"] = {"verdict": combined}
        for score in scores.values():
            if score["verdict"].startswith("INCONCLUSIVE"):
                score["agreement"] = "UNTESTED"
            elif fault:
                score["agreement"] = "DETECTED" if score["verdict"].endswith("_ALERT") else "MISSED"
            else:
                score["agreement"] = (
                    "FALSE_ALERT" if score["verdict"].endswith("_ALERT") else "NO_ALERT_ON_HEALTHY_SOURCE"
                )
        results[name] = {"published_fault_label": fault, "window_exclusions": rejected, "comparisons": scores}
    return {"plan": PLAN, "frozen_canonical_sha256": digest(freeze), "flights": results,
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
            parser.error("the frozen calibration must reproduce from the healthy source flights")
        report = compare(args.originals, fit)
    else:
        report = fit
    args.output.write_bytes((json.dumps(report, indent=2, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
