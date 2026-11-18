"""Compare APC Thin Electric 10x5 wind-tunnel CT and CP on reserved sweeps."""
from __future__ import annotations

import argparse
from bisect import bisect_left
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import mean


SOURCE = "https://m-selig.ae.illinois.edu/props/volume-1/data/"
BASE = Path(__file__).resolve().parents[1]
PLAN = BASE / "docs/campaigns/m24_uiuc_axial_sweeps_freeze.json"
STATIC_FILE = BASE / "data/benchmarks/uiuc/apce_10x5_static_pg0819.txt"


def read_table(
    path: Path, checksum: str, header: tuple[str, ...], *, normalize_line_endings: bool = False
) -> list[tuple[float, float, float]]:
    data = path.read_bytes()
    if normalize_line_endings:
        data = data.replace(b"\r\n", b"\n")
    if sha256(data).hexdigest() != checksum:
        raise ValueError(f"Unexpected SHA-256 for {path}")
    heading, *lines = data.decode("ascii").splitlines()
    if tuple(heading.split()) != header:
        raise ValueError(f"Unexpected columns in {path}")
    rows = []
    for line in lines:
        values = tuple(map(float, line.split()))
        if len(values) != len(header) or not all(map(isfinite, values)):
            raise ValueError(f"Invalid numeric row in {path}")
        x, thrust, power = values[:3]
        rows.append((x, thrust, power))
    if len(rows) < 2 or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError(f"Expected strictly increasing data in {path}")
    return rows


def mix(low: tuple[float, float], high: tuple[float, float], weight: float) -> tuple[float, float]:
    return low[0] + weight * (high[0] - low[0]), low[1] + weight * (high[1] - low[1])


def interpolate(curve: list[tuple[float, float, float]], x: float) -> tuple[float, float]:
    if not curve[0][0] <= x <= curve[-1][0]:
        raise ValueError("Interpolation query is outside the measured range")
    upper = max(1, bisect_left(curve, x, key=lambda row: row[0]))
    low_x, low_thrust, low_power = curve[upper - 1]
    high_x, high_thrust, high_power = curve[upper]
    return mix((low_thrust, low_power), (high_thrust, high_power), (x - low_x) / (high_x - low_x))


def metrics(errors: list[tuple[float, float]]) -> dict:
    if not errors:
        raise ValueError("No supported holdout observations")
    return {
        name: {
            "mae": round(mean(map(abs, column)), 10),
            "mean_signed_error": round(mean(column), 10),
            "max_absolute_error": round(max(map(abs, column)), 10),
        }
        for name, column in zip(("ct", "cp"), zip(*errors))
    }


def evaluate(source_dir: Path) -> dict:
    plan_bytes = PLAN.read_bytes().replace(b"\r\n", b"\n")
    plan = json.loads(plan_bytes)
    static = read_table(STATIC_FILE, plan["static_sha256"], ("RPM", "CT", "CP"), normalize_line_endings=True)

    def load(record: dict) -> list[tuple[float, float, float]]:
        return read_table(source_dir / record["file"], record["sha256"], ("J", "CT", "CP", "eta"))

    low_record, upper_low_record, upper_high_record = plan["calibration"]
    low = load(low_record)
    seam = plan["upper_plane_seam_j"]
    high = [row for row in load(upper_low_record) if row[0] < seam]
    high.extend(row for row in load(upper_high_record) if row[0] >= seam)
    low_rpm = low_record["rpm"]
    high_rpm = mean((upper_low_record["rpm"], upper_high_record["rpm"]))
    low_j = max(low[0][0], high[0][0])
    high_j = min(low[-1][0], high[-1][0])
    model_names = ("axial_interpolator", "advance_ratio_only", "static_reference")
    combined_errors = {name: [] for name in model_names}
    reports = []
    for record in plan["holdout"]:
        rpm = record["rpm"]
        if not low_rpm <= rpm <= high_rpm:
            raise ValueError(f"Holdout RPM {rpm} is outside the calibration envelope")
        weight = (rpm - low_rpm) / (high_rpm - low_rpm)
        static_prediction = interpolate(static, rpm)
        rows = load(record)
        errors = {name: [] for name in model_names}
        sign_disagreements = dict.fromkeys(model_names, 0)
        measured_nonpositive_ct = 0
        for j, ct, cp in rows:
            if not low_j <= j <= high_j:
                continue
            lower = interpolate(low, j)
            upper = interpolate(high, j)
            predictions = (mix(lower, upper, weight), mix(lower, upper, 0.5), static_prediction)
            measured_nonpositive_ct += ct <= 0.0
            for name, (predicted_ct, predicted_cp) in zip(model_names, predictions):
                errors[name].append((predicted_ct - ct, predicted_cp - cp))
                sign_disagreements[name] += (predicted_ct <= 0.0) != (ct <= 0.0)
        for name in model_names:
            combined_errors[name].extend(errors[name])
        scored = len(errors["axial_interpolator"])
        reports.append({
            "rpm": rpm,
            "rows_scored": scored,
            "rows_outside_calibration_j": len(rows) - scored,
            "measured_nonpositive_ct": measured_nonpositive_ct,
            "thrust_sign_disagreements": sign_disagreements,
            "errors": {name: metrics(errors[name]) for name in model_names},
        })
    return {
        "plan_sha256": sha256(plan_bytes).hexdigest(),
        "hardware": plan["hardware"],
        "source": SOURCE,
        "calibration_envelope": {"rpm": [low_rpm, high_rpm], "j": [low_j, high_j]},
        "heldout_sweeps": reports,
        "rows_scored": sum(report["rows_scored"] for report in reports),
        "rows_outside_calibration_j": sum(report["rows_outside_calibration_j"] for report in reports),
        "errors": {name: metrics(combined_errors[name]) for name in model_names},
        "acceptance_status": "inconclusive_no_predeclared_engineering_tolerances_or_uncertainty",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="Directory containing original publisher sweep files")
    parser.add_argument("output", type=Path, help="Path for the JSON comparison")
    arguments = parser.parse_args()
    text = json.dumps(evaluate(arguments.source_dir), indent=2) + "\n"
    arguments.output.write_text(text, encoding="utf-8", newline="\n")
