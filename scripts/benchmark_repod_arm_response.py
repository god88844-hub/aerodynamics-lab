"""Frozen bench response comparison for the RepOD printed drone-arm data."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from statistics import mean

import numpy as np

PLAN = "m25-repod-drone-arm-force-v1"
SOURCE = "https://doi.org/10.18150/JG8XQS"
SOURCE_BYTES = 3_052_355
SOURCE_SHA256 = "eb7c6df138780bcda7b44154c9ddf690d19708cba25a99e84c219b7de00166fd"
HEADER = ("Material", "Infill", "Sample", "Subsample", "Distance[mm]", "adc_mm", "Force[N]")
CONFIGURATIONS = tuple((material, infill) for material in ("PETG", "PLA") for infill in ("25%", "100%"))
CALIBRATION_SAMPLES = (1, 2, 3)
HOLDOUT_SAMPLES = (4, 5)
STROKES = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Stroke:
    material: str
    infill: str
    sample: int
    distance_mm: int
    force_q95_n: float
    source_rows: int

    @property
    def label(self) -> str:
        return f"{self.material}/{self.infill}"


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def measurements(path: Path, selected: tuple[int, ...]) -> list[Stroke]:
    with path.open("rb") as source:
        if path.stat().st_size != SOURCE_BYTES or hashlib.file_digest(source, "sha256").hexdigest() != SOURCE_SHA256:
            raise ValueError("CSV does not match the pinned RepOD original-format release")
    return read_strokes(path, selected)


def read_strokes(path: Path, selected: tuple[int, ...]) -> list[Stroke]:
    expected = {(m, i, s, d) for m, i in CONFIGURATIONS for s in selected for d in STROKES}
    force = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, strict=True)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise ValueError("unexpected columns in the original arm CSV")
        for row in reader:
            sample = int(row["Sample"])
            # Force and displacement from the other partition are never parsed.
            if sample not in selected:
                continue
            material, infill = row["Material"], row["Infill"]
            subsample = int(row["Subsample"])
            key = material, infill, sample, subsample
            distance, measured_force = float(row["Distance[mm]"]), float(row["Force[N]"])
            if key not in expected or distance != subsample or not np.isfinite(measured_force):
                raise ValueError(f"invalid stroke or force at source row {reader.line_num}")
            force[key].append(measured_force)
    if force.keys() != expected or min(map(len, force.values()), default=0) < 30:
        raise ValueError("the selected partition lacks a complete measured stroke group")
    return [
        Stroke(*key, float(np.quantile(samples, 0.95, method="linear")), len(samples))
        for key, samples in sorted(force.items())
    ]


def stiffness(strokes: list[Stroke]) -> float:
    return sum(r.distance_mm * r.force_q95_n for r in strokes) / sum(r.distance_mm ** 2 for r in strokes)


def calibrate(path: Path) -> dict:
    rows = measurements(path, CALIBRATION_SAMPLES)
    baseline = {
        material: round(stiffness([r for r in rows if r.material == material]), 9)
        for material in sorted({m for m, _ in CONFIGURATIONS})
    }
    by_config = {}
    for material, infill in CONFIGURATIONS:
        group = [r for r in rows if (r.material, r.infill) == (material, infill)]
        fold_errors = []
        for sample in CALIBRATION_SAMPLES:
            fitted = stiffness([r for r in group if r.sample != sample])
            fold_errors.extend(fitted * r.distance_mm - r.force_q95_n for r in group if r.sample == sample)
        by_config[f"{material}/{infill}"] = {
            "effective_n_per_mm": round(stiffness(group), 9),
            "leave_sample_out_max_abs_error_n": round(max(map(abs, fold_errors)), 9),
            "leave_sample_out_mae_n": round(mean(map(abs, fold_errors)), 9),
        }
    if any(model["effective_n_per_mm"] <= 0 for model in by_config.values()):
        raise ValueError("calibration did not identify positive fixture stiffness")
    return {
        "plan": PLAN, "source": SOURCE, "source_bytes": SOURCE_BYTES, "source_sha256": SOURCE_SHA256,
        "calibration_samples": list(CALIBRATION_SAMPLES), "holdout_samples": list(HOLDOUT_SAMPLES),
        "models": by_config, "infill_blind_baseline_n_per_mm": baseline,
    }


def error_summary(errors: list[float]) -> dict:
    return {
        "mae_n": round(mean(map(abs, errors)), 9),
        "rmse_n": round(float(np.sqrt(mean(e ** 2 for e in errors))), 9),
        "bias_n": round(mean(errors), 9), "max_abs_n": round(max(map(abs, errors)), 9),
    }


def evaluate(path: Path, freeze: dict) -> dict:
    if freeze != calibrate(path):
        raise ValueError("calibration artifact does not reproduce from its original sample groups")
    details = []
    for r in measurements(path, HOLDOUT_SAMPLES):
        model = freeze["models"][r.label]
        predicted = r.distance_mm * model["effective_n_per_mm"]
        baseline = r.distance_mm * freeze["infill_blind_baseline_n_per_mm"][r.material]
        error = predicted - r.force_q95_n
        details.append({
            "configuration": r.label, "sample": r.sample, "nominal_stroke_mm": r.distance_mm,
            "source_rows": r.source_rows, "measured_force_q95_n": round(r.force_q95_n, 9),
            "predicted_force_q95_n": round(predicted, 9), "infill_blind_prediction_n": round(baseline, 9),
            "error_n": round(error, 9), "baseline_error_n": round(baseline - r.force_q95_n, 9),
            "inside_empirical_calibration_band": abs(error) <= model["leave_sample_out_max_abs_error_n"],
        })
    configs = {}
    for material, infill in CONFIGURATIONS:
        label = f"{material}/{infill}"
        group = [row for row in details if row["configuration"] == label]
        configs[label] = {
            "model": error_summary([r["error_n"] for r in group]),
            "infill_blind_baseline": error_summary([r["baseline_error_n"] for r in group]),
            "strokes_inside_empirical_band": sum(r["inside_empirical_calibration_band"] for r in group),
            "whole_groups_inside_empirical_band": sum(
                all(r["inside_empirical_calibration_band"] for r in group if r["sample"] == sample)
                for sample in HOLDOUT_SAMPLES
            ),
        }
    return {
        "plan": PLAN, "frozen_calibration_canonical_sha256": digest(freeze),
        "status": "INCONCLUSIVE_FOR_STRUCTURAL_STRENGTH_OR_FLIGHT_ACCEPTANCE",
        "heldout_source_groups": len(CONFIGURATIONS) * len(HOLDOUT_SAMPLES), "heldout_strokes": len(details),
        "model": error_summary([r["error_n"] for r in details]),
        "infill_blind_baseline": error_summary([r["baseline_error_n"] for r in details]),
        "by_configuration": configs, "strokes": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("calibrate", "evaluate"))
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.action == "calibrate":
        report = calibrate(args.original)
    else:
        if args.freeze is None:
            parser.error("evaluation requires --freeze")
        report = evaluate(args.original, json.loads(args.freeze.read_bytes()))
    args.output.write_bytes((json.dumps(report, indent=2, allow_nan=False) + "\n").encode())


if __name__ == "__main__":
    main()
