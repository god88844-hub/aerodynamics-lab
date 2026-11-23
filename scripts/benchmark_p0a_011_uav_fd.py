"""P0A-011: opt-in pinned-UAV-FD adapter for the shared physics detector.

The frozen M25 benchmark scripts remain untouched; these provide verified MAT
parsing/window eligibility only. ALL repaired scoring, train-only fitting and
alert logic lives in packages.physics.validation.uav_fd_fault_detector.
The source fault labels are attached only after decisions have been frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.signal import lombscargle

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "scripts")]

import benchmark_uav_fd_rotor_order as vib  # noqa: E402
import benchmark_uav_fd_esc_power as esc  # noqa: E402
from physics.validation import uav_fd_fault_detector as detector  # noqa: E402

PLAN = "p0a-011-uavfd-detector-development-v1"
FINGERPRINTS = {**vib.FILES, **esc.NEW_FILES}
HOLDOUTS = {**vib.HOLDOUT, **esc.HOLDOUT}
VIB_RESULTS = ROOT / "docs/campaigns/m25_uav_fd_rotor_order_results.json"
ESC_RESULTS = ROOT / "docs/campaigns/m25_uav_fd_esc_power_results.json"
DEFAULT_ARTIFACT = ROOT / "docs/campaigns/m25_p0a_011_detector_delta.json"


def sha(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _own_1p(t: np.ndarray, acceleration: np.ndarray, rpm: np.ndarray) -> tuple[float, ...]:
    """Shared IMU, independent RPM-associated bands; no fleet-wide maximum."""
    local = t - t[0]
    design = np.column_stack((np.ones(len(local)), local))
    centered = acceleration - design @ np.linalg.lstsq(design, acceleration, rcond=None)[0]
    frequencies = np.arange(55.0, 136.0)
    union = (np.abs(frequencies[:, None] - rpm / 60.0) <= vib.ROTOR_NEIGHBORHOOD_HZ).any(axis=1)
    frequencies = frequencies[union]
    if not len(frequencies) or frequencies[-1] >= 0.4 / float(np.median(np.diff(t))):
        raise ValueError("1P motor bands outside measured IMU frequency support")
    power = sum(lombscargle(local, axis, 2 * np.pi * frequencies) for axis in centered.T)
    result = []
    for r in rpm:
        own = np.abs(frequencies - r / 60.0) <= vib.ROTOR_NEIGHBORHOOD_HZ
        if not own.any():
            raise ValueError("1P motor band unsupported")
        result.append(float(np.sqrt(4 * np.max(power[own]) / len(t))))
    return tuple(result)


def windows(directory: Path, name: str) -> tuple[detector.TrainingFlight, dict]:
    """Source-hash verified, two independent timebases, preserved eligibility."""
    eold, e_excluded = esc.extract(directory, name, FINGERPRINTS)
    vold, v_excluded = vib.extract(directory, name, FINGERPRINTS)
    imu, height, motor_rpm = vib.load(directory, name, FINGERPRINTS)
    # Window starts follow each FROZEN adapter's own source clock.
    esc_t = float(height.t[0])
    vib_t = float(imu.t[0])
    electrical = []
    for w in eold:
        start = esc_t + w.index * vib.WINDOW_S
        sensed = [m.window(start, start + vib.WINDOW_S, vib.OTHER_GAP_S, 5) for m in motor_rpm]
        if any(m is None for m in sensed):
            raise ValueError("ESC eligibility inconsistency")
        rpm = tuple(float(np.median(m.values[:, 0])) for m in sensed)
        electrical.append(detector.ElectricalWindow(
            w.index, w.index * vib.WINDOW_S, rpm, tuple(map(float, w.speed_normalized_power))))
    vibration = []
    for w in vold:
        start = vib_t + w.index * vib.WINDOW_S
        acceleration = imu.window(start, start + vib.WINDOW_S, vib.IMU_GAP_S, 300)
        sensed = [m.window(start, start + vib.WINDOW_S, vib.OTHER_GAP_S, 5) for m in motor_rpm]
        if acceleration is None or any(m is None for m in sensed):
            raise ValueError("vibration eligibility inconsistency")
        rpm = np.array([np.median(m.values[:, 0]) for m in sensed])
        vibration.append(detector.VibrationWindow(
            w.index, w.index * vib.WINDOW_S, tuple(map(float, rpm)),
            _own_1p(acceleration.t, acceleration.values, rpm)))
    coverage = {
        "electrical_total_windows": int((height.t[-1] - height.t[0]) // vib.WINDOW_S),
        "vibration_total_windows": int((imu.t[-1] - imu.t[0]) // vib.WINDOW_S),
        "electrical_exclusions": e_excluded,
        "vibration_exclusions": v_excluded,
    }
    return detector.TrainingFlight(tuple(electrical), tuple(vibration)), coverage


def before_rows() -> tuple[dict, dict]:
    v = json.loads(VIB_RESULTS.read_text(encoding="utf-8"))
    e = json.loads(ESC_RESULTS.read_text(encoding="utf-8"))
    old = {}
    for name, flight in v["flights"].items():
        old[name] = {
            "rotor_order": flight["models"]["rotor_order"]["agreement"],
            "broad_accel_rms": flight["models"]["accel_rms"]["agreement"],
            "speed_normalized_power": None, "combined": None,
            "exclusions": flight["excluded_windows"],
        }
    for name, flight in e["flights"].items():
        old[name] = {
            "rotor_order": flight["comparisons"]["rotor_order_vibration"]["agreement"],
            "broad_accel_rms": None,
            "speed_normalized_power": flight["comparisons"]["speed_normalized_power"]["agreement"],
            "combined": flight["comparisons"]["either_indicator"]["agreement"],
            "exclusions": flight["window_exclusions"],
        }
    return old, {"rotor_order_frozen_results_sha256": sha(v), "esc_power_frozen_results_sha256": sha(e)}


def reproduce(directory: Path) -> dict:
    old, pinned_baseline = before_rows()
    if set(old) != set(HOLDOUTS) or set(FINGERPRINTS) != (set(HOLDOUTS) | detector.TRAIN_IDS):
        raise ValueError("source file split changed")
    trains = {name: windows(directory, name)[0] for name in sorted(detector.TRAIN_IDS)}
    fit = detector.calibrate(trains)
    out = {}
    for name in sorted(HOLDOUTS):
        flight, coverage = windows(directory, name)
        unsupported = any(
            coverage[channel].get(reason, 0) > 0
            for channel, reasons in (
                ("electrical_exclusions", (
                    "rotor_speed_or_nonpositive_electrical_input",)),
                ("vibration_exclusions", (
                    "outside_rotor_speed_scope", "outside_frequency_support")))
            for reason in reasons
        )
        result = detector.evaluate(
            fit, flight.electrical, flight.vibration,
            expected_electrical_windows=coverage["electrical_total_windows"],
            expected_vibration_windows=coverage["vibration_total_windows"],
            unsupported_telemetry_observed=unsupported)
        # The only label read is here, AFTER all scoring and decisions.
        truth = HOLDOUTS[name]
        after = ("TP" if truth else "FP") if result["state"] == "DETECT" else (
            ("FN" if truth else "TN") if result["state"] == "NO-ALERT" else "INCONCLUSIVE")
        out[name] = {
            "publisher_label": "FAULT" if truth else "NO_FAULT",
            "ground_truth_fault_type": name.removesuffix(".mat") if truth else None,
            "before": old[name],
            "after": {**result, "confusion": after},
            "source_exclusions_after": coverage,
            "sha256": FINGERPRINTS[name][1],
        }
    return {
        "plan": PLAN,
        "scientific_status": "DEVELOPMENT",
        "physical_acceptance": False,
        "recordings_are_not_independent_prospective_validation": True,
        "train_recordings": sorted(detector.TRAIN_IDS),
        "holdout_recordings": sorted(HOLDOUTS),
        "pinned_source_files": {name: {"bytes": size, "sha256": checksum}
                                for name, (size, checksum) in sorted(FINGERPRINTS.items())},
        "frozen_baseline": pinned_baseline,
        "calibration": fit,
        "calibration_canonical_sha256": sha(fit),
        "holdouts": out,
        "no_fault_onset_timestamp": True,
        "deadline_claim": "NOT_ASSESSABLE_FROM_RECORDING_LEVEL_PUBLISHER_LABELS",
        "limitation": "Shared IMU 1P bands can overlap; ESC-index evidence is not physical rotor isolation.",
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--originals", type=Path, default=os.environ.get("AEROFORGE_UAV_FD_DIR"))
    p.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT)
    p.add_argument("--check", action="store_true", help="require exact equality to committed delta")
    args = p.parse_args()
    if not args.originals or not Path(args.originals).is_dir():
        p.error("AEROFORGE_UAV_FD_DIR must identify eight pinned publisher MAT files")
    report = reproduce(Path(args.originals))
    before, frozen = before_rows()
    if {n: row["before"] for n, row in report["holdouts"].items()} != before:
        raise ValueError("Frozen P0A-010 before classifications drifted")
    delta = {
        "plan": PLAN,
        "scientific_status": "DEVELOPMENT",
        "physical_acceptance": False,
        "train_recordings": sorted(detector.TRAIN_IDS),
        "holdout_recordings": sorted(HOLDOUTS),
        "frozen_baseline": frozen,
        "before": before,
        "after_status": "REPRODUCED_FROM_PINNED_PUBLISHER_BYTES",
        "after": report["holdouts"],
        "calibration": report["calibration"],
        "calibration_canonical_sha256": report["calibration_canonical_sha256"],
        "live_result": report,
        "limitation": (
            "DEVELOPMENT retrospective on one rig; shared-IMU motor-frequency "
            "attribution is not physical isolation; no fault-onset timestamp "
            "permits measured detection-deadline compliance."
        ),
    }
    if args.check:
        committed = json.loads(args.output.read_text(encoding="utf-8"))
        if delta != committed:
            raise SystemExit("P0A-011 delta differs from pinned publisher replay")
        print("P0A-011 live result bit-identical to committed DEVELOPMENT delta")
    else:
        args.output.write_text(json.dumps(delta, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(f"wrote DEVELOPMENT before/after comparison: {args.output}")


if __name__ == "__main__":
    main()
