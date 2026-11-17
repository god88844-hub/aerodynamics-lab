"""Reproduce the M21 VTC6 single-cell physical benchmark from CMU originals."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "packages/shared-schemas")]

from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import BatteryPack

DATASET = "https://doi.org/10.1184/R1/14226830.v3"
SOURCE_SHA256 = {
    "VAH01.csv": "596ab1e1e80eeac3509f789609f751527c2073a4310deec8274cbfaf4fef39c4",
    "VAH01_impedance.csv": "f92a2e6b141d732863fbf5ba09e8867c073f15df2d35c80c83887051a1d31b25",
    "VAH17.csv": "a20cf42e2a58eed8dff3a1d54816012c043664dbf4cfdcee61bf86bd5048b4d8",
}
PLAN_VERSION = "M21-vtc6-baseline-v1"
RUN_COUNT = 5
MAX_GAP_S = 2.0
PHASES = (("takeoff", 54, 75), ("cruise", 16, 800), ("landing", 54, 105))
DISCHARGE_STEPS = (4, 5, 6)


@dataclass(frozen=True)
class Sample:
    row: int
    time_s: float
    volts: float
    amps: float
    discharge_ah: float
    temperature_c: float


@dataclass(frozen=True)
class Segment:
    cycle: str
    step: int
    samples: list[Sample]


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def original(directory: Path, filename: str) -> Path:
    path = directory / filename
    if file_sha256(path) != SOURCE_SHA256[filename]:
        raise ValueError(f"{filename} does not match the frozen original SHA-256")
    return path


def segments(path: Path) -> Iterator[Segment]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        source = enumerate(csv.DictReader(stream), start=2)
        groups = itertools.groupby(source, key=lambda pair: (pair[1]["cycleNumber"], pair[1]["Ns"]))
        for (cycle, step), group in groups:
            samples = []
            for row, record in group:
                values = tuple(float(record[key]) for key in (
                    "time_s", "Ecell_V", "I_mA", "QDischarge_mA_h", "Temperature__C",
                ))
                if not all(math.isfinite(value) for value in values):
                    raise ValueError(f"nonfinite measurement on CSV line {row}")
                t_s, volts, current_ma, discharge_mah, temperature_c = values
                samples.append(Sample(row, t_s, volts, -current_ma / 1000, discharge_mah / 1000, temperature_c))
            yield Segment(cycle, int(step), samples)


def calibrate(directory: Path) -> dict:
    resistance_path = original(directory, "VAH01_impedance.csv")
    with resistance_path.open(newline="", encoding="utf-8-sig") as stream:
        resistance_row = next(csv.DictReader(stream))
    if int(resistance_row["cycle numbers"]) != 1:
        raise ValueError("first VAH01 impedance row is not the initial test")
    resistance = mean(float(resistance_row[key]) for key in ("20%_1_second", "60%_1_second"))

    source = original(directory, "VAH01.csv")
    rpt = list(itertools.islice(segments(source), 9))
    if [segment.step for segment in rpt] != list(range(9)) or len({s.cycle for s in rpt}) != 1:
        raise ValueError("unexpected initial VAH01 characterization sequence")
    loaded = []
    for step in (3, 5, 7):
        steady = [s for s in rpt[step].samples if 0.55 <= s.amps <= 0.66]
        loaded.extend(steady)
    charge = np.array([s.discharge_ah for s in loaded])
    if not len(charge) or not 0 <= charge[0] <= 0.001 or (np.diff(charge) <= 0).any():
        raise ValueError("invalid VAH01 characterization charge axis")
    charge -= charge[0]
    capacity = float(charge[-1])
    if not 2 <= capacity <= 4 or not 2.49 <= loaded[-1].volts <= 2.51:
        raise ValueError("initial VAH01 characterization did not reach the expected endpoint")
    soc = (100 * (1 - charge / capacity))[::-1]
    voltage = [s.volts + s.amps * resistance for s in reversed(loaded)]
    curve_soc = list(range(0, 101, 5))
    curve_volts = np.interp(curve_soc, soc, voltage)
    return {
        "plan": PLAN_VERSION,
        "dataset": DATASET,
        "source_sha256": SOURCE_SHA256,
        "characterization_csv_lines_inclusive": [loaded[0].row, loaded[-1].row],
        "baseline_mission_count": RUN_COUNT,
        "battery": {
            "id": "cmu_vtc6_vah01_baseline",
            "name": "Sony-Murata VTC6 single-cell model characterized on VAH01",
            "chemistry": "Li-ion",
            "cells_series": 1,
            "capacity_ah": capacity,
            "internal_resistance_ohm": resistance,
            "cutoff_cell_voltage_v": 2.5,
            "max_discharge_c": 10,
            "ocv_curve": [
                {"soc_pct": pct, "cell_voltage_v": round(float(volts), 9)}
                for pct, volts in zip(curve_soc, curve_volts, strict=True)
            ],
            "source": {
                "source": "Bills et al. eVTOL Battery Dataset v3, VAH01 initial characterization",
                "url": DATASET,
                "estimated": True,
                "notes": "Loaded C/5 voltage de-sagged by initial 1-second DCIR, an OCV proxy.",
            },
        },
    }


def early_missions(source: Path) -> Iterator[tuple[str, list[Segment]]]:
    groups = segments(source)
    # Initial characterization can share a cycle label with the first mission.
    # The mission signature begins with a normal charge/CV/rest sequence.
    window = []
    count = 0
    previous_cycle = None
    for group in groups:
        window = (window + [group])[-7:]
        if tuple(s.step for s in window) != (0, 1, 3, *DISCHARGE_STEPS, 7):
            continue
        if len({s.cycle for s in window}) != 1:
            raise ValueError("mission signature straddles multiple tester cycles")
        if previous_cycle is not None and int(group.cycle) != previous_cycle + 1:
            raise ValueError("early mission sequence skips a tester cycle")
        previous_cycle = int(group.cycle)
        yield group.cycle, window[3:6]
        count += 1
        if count == RUN_COUNT:
            return
    raise ValueError(f"found {count} complete early baseline missions, expected {RUN_COUNT}")


def expected_load(pack: BatteryPack, soc_pct: float, watts: float) -> tuple[float, float]:
    resistance = pack.spec.internal_resistance_ohm
    if resistance is None:
        raise ValueError("benchmark requires frozen DC internal resistance")
    ocv = pack.ocv_pack(soc_pct)
    discriminant = ocv ** 2 - 4 * resistance * watts
    if discriminant < 0:
        raise ValueError("frozen model cannot supply the published power")
    # I * (OCV - R * I) = P. Use the low-current, high-voltage root.
    amps = 2 * watts / (ocv + math.sqrt(discriminant))
    return amps, pack.voltage_under_load(soc_pct, amps)


def summarize_error(residuals: list[float]) -> dict:
    return {
        "mae": round(mean(abs(r) for r in residuals), 9),
        "rmse": round(math.sqrt(mean(r * r for r in residuals)), 9),
        "bias": round(mean(residuals), 9),
        "max_abs_error": round(max(abs(r) for r in residuals), 9),
    }


def replay_mission(
    pack: BatteryPack, cycle: str, mission: list[Segment]
) -> tuple[dict, dict[str, tuple[list[float], list[float]]]]:
    soc = 100.0  # Initial condition defined by the publisher's full-charge protocol.
    previous_time = None
    previous_amps = 0.0
    residuals = {}
    phase_results = {}
    for segment, (phase, watts, duration) in zip(mission, PHASES, strict=True):
        first, last = segment.samples[0], segment.samples[-1]
        if abs(last.time_s - first.time_s - duration) > MAX_GAP_S:
            raise ValueError(f"cycle {cycle} {phase} does not span the published duration")

        voltage_errors, current_errors, watts_measured, predictions = [], [], [], []
        measured_wh = 0.0
        previous_power = None
        for sample in segment.samples:
            if sample.volts <= 0 or sample.amps <= 0:
                raise ValueError(f"cycle {cycle} has an invalid discharge sample at line {sample.row}")
            elapsed = 0.0
            if previous_time is not None:
                elapsed = sample.time_s - previous_time
                if not 0 < elapsed <= MAX_GAP_S:
                    raise ValueError(f"cycle {cycle} has a missing or nonmonotonic sample at line {sample.row}")
                soc = pack.soc_after(soc, previous_amps, elapsed)
            if soc <= 0:
                raise ValueError(f"frozen model runs out of charge in cycle {cycle}")
            amps, volts = expected_load(pack, soc, watts)
            voltage_errors.append(volts - sample.volts)
            current_errors.append(amps - sample.amps)
            power = sample.volts * sample.amps
            watts_measured.append(power)
            if previous_power is not None:
                measured_wh += (power + previous_power) * elapsed / 7200
            previous_power = power
            predictions.append(volts)
            previous_time, previous_amps = sample.time_s, amps

        residuals[phase] = (voltage_errors, current_errors)
        phase_results[phase] = {
            "source_csv_lines_inclusive": [first.row, last.row],
            "samples": len(segment.samples),
            "commanded_power_w": watts,
            "mean_measured_power_w": round(mean(watts_measured), 6),
            "measured_energy_wh": round(measured_wh, 9),
            "commanded_energy_over_sample_span_wh": round(watts * (last.time_s - first.time_s) / 3600, 9),
            "duration_s": round(last.time_s - first.time_s, 6),
            "current_a": [min(s.amps for s in segment.samples), max(s.amps for s in segment.samples)],
            "temperature_c": [min(s.temperature_c for s in segment.samples), max(s.temperature_c for s in segment.samples)],
            "min_measured_voltage_v": min(s.volts for s in segment.samples),
            "min_predicted_voltage_v": round(min(predictions), 9),
            "voltage_residual_v": summarize_error(voltage_errors),
            "current_residual_a": summarize_error(current_errors),
        }
    end_soc = round(soc, 9)
    measured_cutoff = min(p["min_measured_voltage_v"] for p in phase_results.values()) <= 2.5
    predicted_cutoff = min(p["min_predicted_voltage_v"] for p in phase_results.values()) <= 2.5
    measured_temperature_stop = max(p["temperature_c"][1] for p in phase_results.values()) >= 70
    measured_current_limit = max(p["current_a"][1] for p in phase_results.values()) > 30
    return {
        "tester_cycle": cycle,
        "phase_results": phase_results,
        "modeled_final_soc_pct": end_soc,
        "measured_voltage_at_or_below_2_5_v": measured_cutoff,
        "predicted_voltage_at_or_below_2_5_v": predicted_cutoff,
        "measured_temperature_at_or_above_70_c": measured_temperature_stop,
        "measured_current_above_30_a": measured_current_limit,
    }, residuals


def evaluate(directory: Path, freeze_path: Path) -> dict:
    with freeze_path.open(encoding="utf-8") as stream:
        freeze = json.load(stream)
    if freeze != calibrate(directory):
        raise ValueError("freeze does not reproduce from the original characterization")
    pack = BatteryPack(BatterySpec.model_validate(freeze["battery"]))
    source = original(directory, "VAH17.csv")
    runs = []
    pooled = {phase: ([], []) for phase, _, _ in PHASES}
    for cycle, mission in early_missions(source):
        run, errors = replay_mission(pack, cycle, mission)
        runs.append(run)
        for phase, (voltage, current) in errors.items():
            pooled[phase][0].extend(voltage)
            pooled[phase][1].extend(current)
    all_voltage = [value for voltage, _ in pooled.values() for value in voltage]
    all_current = [value for _, current in pooled.values() for value in current]
    return {
        "plan": PLAN_VERSION,
        "freeze_sha256": file_sha256(freeze_path),
        "holdout": {"cell": "VAH17", "source_sha256": SOURCE_SHA256[source.name]},
        "verdict": "INCONCLUSIVE_FOR_PACK_ACCEPTANCE",
        "samples": len(all_voltage),
        "pooled_voltage_residual_v": summarize_error(all_voltage),
        "pooled_current_residual_a": summarize_error(all_current),
        "pooled_by_phase": {
            phase: {
                "samples": len(voltage),
                "voltage_residual_v": summarize_error(voltage),
                "current_residual_a": summarize_error(current),
            }
            for phase, (voltage, current) in pooled.items()
        },
        "missions": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "evaluate"))
    parser.add_argument("originals", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.action == "evaluate":
        if args.freeze is None:
            parser.error("evaluate requires --freeze")
        result = evaluate(args.originals, args.freeze)
    else:
        result = calibrate(args.originals)
    args.output.write_bytes((json.dumps(result, indent=2, allow_nan=False) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
