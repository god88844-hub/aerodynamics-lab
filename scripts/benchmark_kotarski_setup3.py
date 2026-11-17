"""Freeze and score the published Kotarski Setup 3 static propulsion bench."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.component import MotorSpec
from physics.constants import GF_TO_N
from physics.propulsion.dataset import PowertrainDataset

DATASET_DOI = "10.7910/DVN/J5L2P4"
PROPELLER = "G30 × 10.5"
HOLDOUT = "4.0"
PLAN = "M22-kotarski-setup3-static-v1"
FILES = {
    "3.8": (6940261, 15940, "31ae880d06637e8780b64a6b34e6fbc0828d5618f2a9a65bf4c1c6c5fab515bd"),
    "4.0": (6940259, 15839, "9d90497f5e13d5e0e449b04fc0850a167027caebcf0db9eb0f2f25448dd53feb"),
    "4.2": (6940266, 15872, "a59b8bb83226aa6f0108bd6fe5c6c40399e687b9f1d6fde349a2276694ec3ef8"),
}
CALIBRATION = (("3.8", 45.6), ("4.2", 50.4))
PWM_STEPS = range(1000, 2001, 100)


@dataclass(frozen=True)
class Observation:
    line: int
    pwm_us: int
    rpm: float
    bus_voltage_v: float
    thrust_n: float
    current_a: float
    torque_nm: float


def original_sweep(directory: Path, initial_cell_v: str) -> dict[int, list[Observation]]:
    _, byte_count, digest = FILES[initial_cell_v]
    path = directory / f"setup3_measurement_{initial_cell_v}V.csv"
    raw = path.read_bytes()
    if len(raw) != byte_count or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"{path.name} does not match the publisher original")
    channels = (
        "Motor Optical Speed A (RPM)", "Voltage A (V)", "Thrust A (N)",
        "Current A (A)", "Torque A (N·m)",
    )
    groups = defaultdict(list)
    for line, row in enumerate(csv.DictReader(raw.decode("utf-8-sig").splitlines()), start=2):
        pwm = int(row["ESC A (µs)"])
        values = tuple(float(row[channel]) for channel in channels)
        if not all(math.isfinite(v) for v in values):
            raise ValueError(f"invalid native measurement on CSV line {line}")
        if pwm >= 1200 and min(values) <= 0:
            raise ValueError(f"nonpositive rotating observation on CSV line {line}")
        groups[pwm].append(Observation(line, pwm, *values))
    if set(groups) != set(PWM_STEPS) or any(len(rows) != 4 for rows in groups.values()):
        raise ValueError(f"unexpected PWM groups in {path.name}")
    if any(row.rpm != 0 for step in (1000, 1100) for row in groups[step]):
        raise ValueError(f"expected stationary observations below 1200 µs in {path.name}")
    return groups


def calibrate(directory: Path) -> dict:
    source = {
        "source": "Kotarski et al., UAV Multirotor Propulsion—Experimental Data, Setup 3",
        "url": f"https://doi.org/{DATASET_DOI}",
        "report_id": DATASET_DOI,
        "notes": "Measured static test on an Alpha 80 A ESC, G30 × 10.5, optical RPM.",
    }
    knots = []
    for initial_cell_v, nominal_bus_v in CALIBRATION:
        sweep = original_sweep(directory, initial_cell_v)
        for step in range(1200, 2001, 100):
            rows = sweep[step]
            measured_v = median(row.bus_voltage_v for row in rows)
            amps = median(row.current_a for row in rows)
            knots.append({
                "prop": PROPELLER,
                "rpm": median(row.rpm for row in rows),
                "throttle_pct": (step - 1000) / 10,
                "voltage_v": nominal_bus_v,
                "voltage_measured_v": measured_v,
                "thrust_gf": median(row.thrust_n for row in rows) / GF_TO_N,
                "current_a": amps,
                "torque_nm": median(row.torque_nm for row in rows),
                "power_w": measured_v * amps,
                "source": source,
            })
    return {
        "plan": PLAN,
        "sources": {
            v: {"dataverse_file_id": i, "byte_count": n, "sha256": hash_}
            for v, (i, n, hash_) in FILES.items()
        },
        "calibration_start_cell_v": [v for v, _ in CALIBRATION],
        "holdout_start_cell_v": HOLDOUT,
        "motor": {
            "id": "kotarski_setup3_p80_100kv",
            "name": "Published Kotarski Setup 3 P80 100 Kv bench unit",
            "kv_rpm_per_v": 100,
            "source": source,
            "test_data": knots,
        },
    }


def error_summary(errors: list[float]) -> dict:
    return {
        "mae": round(mean(abs(e) for e in errors), 9),
        "rmse": round(math.sqrt(mean(e * e for e in errors)), 9),
        "bias": round(mean(errors), 9),
        "max_abs": round(max(abs(e) for e in errors), 9),
    }


def evaluate(directory: Path, freeze_path: Path) -> dict:
    raw_freeze = freeze_path.read_bytes()
    freeze = json.loads(raw_freeze)
    if freeze != calibrate(directory):
        raise ValueError("frozen model does not reproduce from the two characterization sweeps")
    motor = MotorSpec.model_validate(freeze["motor"])
    model = PowertrainDataset(motor, PROPELLER)
    rpm_lo = max(plane.rpm_range[0] for plane in model.planes)
    rpm_hi = min(plane.rpm_range[1] for plane in model.planes)
    voltage_lo, voltage_hi = (plane.voltage_v for plane in model.planes)
    records = []
    thrust_errors, current_errors = [], []
    source = original_sweep(directory, HOLDOUT)
    for group in source.values():
        for sample in group:
            row = asdict(sample)
            if sample.current_a > 80:
                row["sampled_esc_current_limit_exceeded"] = True
            if sample.rpm == 0:
                row["classification"] = "STATIONARY_BASELINE"
            elif not (
                rpm_lo <= sample.rpm <= rpm_hi
                and voltage_lo <= sample.bus_voltage_v <= voltage_hi
            ):
                row["classification"] = "OUT_OF_COMMON_CALIBRATION_ENVELOPE"
            else:
                thrust = model.thrust_n(sample.rpm).value
                amps = model.current_a(sample.rpm, sample.bus_voltage_v).value
                thrust_errors.append(thrust - sample.thrust_n)
                current_errors.append(amps - sample.current_a)
                row.update({
                    "classification": "SCORED",
                    "predicted_thrust_n": round(thrust, 9),
                    "predicted_current_a": round(amps, 9),
                    "thrust_error_n": round(thrust_errors[-1], 9),
                    "current_error_a": round(current_errors[-1], 9),
                })
                if amps > 80:
                    row["sampled_esc_current_limit_exceeded"] = True
            records.append(row)
    breach = any(row.get("sampled_esc_current_limit_exceeded", False) for row in records)
    return {
        "plan": PLAN,
        "freeze_sha256": hashlib.sha256(raw_freeze).hexdigest(),
        "verdict": "FAILED_SAMPLED_ESC_CURRENT_LIMIT" if breach else "INCONCLUSIVE_FOR_COMPONENT_ACCEPTANCE",
        "calibration_support": {"rpm": [rpm_lo, rpm_hi], "nominal_bus_v": [voltage_lo, voltage_hi]},
        "scored_samples": len(thrust_errors),
        "stationary_samples": sum(row["classification"] == "STATIONARY_BASELINE" for row in records),
        "out_of_envelope_samples": sum(
            row["classification"] == "OUT_OF_COMMON_CALIBRATION_ENVELOPE" for row in records
        ),
        "thrust_residual_n": error_summary(thrust_errors) if thrust_errors else None,
        "current_residual_a": error_summary(current_errors) if current_errors else None,
        "holdout_rows": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("calibrate", "evaluate"))
    parser.add_argument("originals", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.mode == "evaluate" and args.freeze is None:
        parser.error("evaluation requires --freeze")
    result = calibrate(args.originals) if args.mode == "calibrate" else evaluate(args.originals, args.freeze)
    args.output.write_bytes((json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
