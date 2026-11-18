"""Compare airframe drag laws using the NeuroBEM authors' processed flight data."""

from __future__ import annotations

import argparse
import json
import math
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
from scipy.optimize import nnls

CALIBRATION = {
    "2021-02-18-16-43-54": (1, 2, 3, 4),
    "2021-02-18-17-20-37": (1,),
    "2021-02-23-10-52-00": (1, 2),
    "2021-02-23-14-24-07": (1,),
}
TESTSET_SHA256 = "d59cd589105cf4cd3fcfe0a34a0b4824d6ae2560db13d34b9a7acd169deeb367"
COLUMNS = (
    "t,ang acc x,ang acc y,ang acc z,ang vel x,ang vel y,ang vel z,"
    "quat x,quat y,quat z,quat w,acc x,acc y,acc z,vel x,vel y,vel z,"
    "pos x,pos y,pos z,mot 1,mot 2,mot 3,mot 4,dmot 1,dmot 2,dmot 3,dmot 4,vbat"
)
MODELS = {"thrust_only": 1, "airframe_drag": 2, "rotor_drag": 3}


def read_segment(data_root: Path, segment: str) -> tuple[np.ndarray, str]:
    filename = f"merged_{segment}.csv"
    raw = (data_root / filename).read_bytes()
    if raw.split(b"\n", 1)[0].strip().decode("ascii") != COLUMNS:
        raise ValueError(f"Unexpected CSV columns in {filename}")
    data = np.loadtxt(BytesIO(raw), delimiter=",", skiprows=1, ndmin=2)
    if len(data) < 2 or data.shape[1] != 29 or not np.all(np.isfinite(data)):
        raise ValueError(f"Missing or nonfinite samples in {filename}")
    if np.any(np.diff(data[:, 0]) <= 0.0) or np.any(data[:, 20:24] < 0.0):
        raise ValueError(f"Invalid time or rotor speed in {filename}")
    return data, sha256(raw).hexdigest()


def features(data: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    body_velocity = data[:, 14:17]
    speed = np.linalg.norm(body_velocity, axis=1)
    normalized_rotation_rate = data[:, 20:24] / 1000.0
    terms = np.zeros((len(data), 3, 3))
    terms[:, 2, 0] = np.square(normalized_rotation_rate).sum(axis=1)
    terms[:, :, 1] = -speed[:, None] * body_velocity
    terms[:, :2, 2] = -normalized_rotation_rate.sum(axis=1)[:, None] * body_velocity[:, :2]
    return terms, data[:, 11:14], speed


def sample_seconds(segment: np.ndarray) -> np.ndarray:
    dt = np.diff(segment[:, 0]) / 2.0
    return np.r_[dt[0], dt[:-1] + dt[1:], dt[-1]]


def calibrate(data_root: Path) -> dict:
    inputs, targets, weights, sources = [], [], [], {}
    for flight, segment_numbers in CALIBRATION.items():
        flight_weights = []
        for number in segment_numbers:
            segment = f"{flight}_seg_{number}"
            data, sources[segment] = read_segment(data_root, segment)
            terms, measured, _ = features(data)
            inputs.append(terms)
            targets.append(measured)
            flight_weights.append(sample_seconds(data))
        flight_seconds = sum(weight.sum() for weight in flight_weights)
        weights.extend(weight / flight_seconds for weight in flight_weights)
    root_weight = np.sqrt(np.concatenate(weights))[:, None, None]
    weighted_inputs = (np.concatenate(inputs) * root_weight).reshape(-1, 3)
    weighted_targets = (np.concatenate(targets) * root_weight[:, :, 0]).reshape(-1)
    coefficients = {
        name: nnls(weighted_inputs[:, :count], weighted_targets)[0].tolist()
        for name, count in MODELS.items()
    }
    return {"source_sha256": sources, "coefficients": coefficients}


def summarize(squared_error: np.ndarray, weight: np.ndarray) -> dict:
    mean = np.average(squared_error, weights=weight, axis=0)
    return {
        "samples": len(squared_error),
        "seconds": round(float(weight.sum()), 6),
        "axis_rmse_m_s2": np.round(np.sqrt(mean), 6).tolist(),
        "vector_rmse_m_s2": round(math.sqrt(float(mean.sum())), 6),
    }


def score(data_root: Path, frozen: dict) -> dict:
    testset = (data_root / "testset.txt").read_bytes()
    if sha256(testset).hexdigest() != TESTSET_SHA256:
        raise ValueError("The authors' testset.txt does not match the campaign")
    holdouts = testset.decode("ascii").split()
    flight_ids = [segment.split("_seg_")[0] for segment in holdouts]
    if len(set(flight_ids)) != len(holdouts) or set(flight_ids) & CALIBRATION.keys():
        raise ValueError("Repeated or reused flight in test set")

    segments, test_hashes, all_weights, speeds = {}, {}, [], []
    model_errors: dict[str, list[np.ndarray]] = {name: [] for name in MODELS}
    for segment in holdouts:
        data, test_hashes[segment] = read_segment(data_root, segment)
        terms, measured, speed = features(data)
        weight = sample_seconds(data)
        scores = {}
        for name, count in MODELS.items():
            coefficients = np.asarray(frozen["coefficients"][name])
            if coefficients.shape != (count,) or not np.all(np.isfinite(coefficients) & (coefficients >= 0.0)):
                raise ValueError(f"Invalid frozen coefficients for {name}")
            squared_error = np.square(terms[:, :, :count] @ coefficients - measured)
            scores[name] = summarize(squared_error, weight)
            model_errors[name].append(squared_error)
        segments[segment] = {
            "sample_interval_ms": round(1000 * float(np.median(np.diff(data[:, 0]))), 6),
            "models": scores,
        }
        all_weights.append(weight)
        speeds.append(speed)

    weight = np.concatenate(all_weights)
    speed = np.concatenate(speeds)
    bands = {
        "under_5_m_s": speed < 5.0,
        "5_to_10_m_s": (speed >= 5.0) & (speed < 10.0),
        "at_least_10_m_s": speed >= 10.0,
    }
    summary = {}
    for name, parts in model_errors.items():
        errors = np.concatenate(parts)
        summary[name] = {"all": summarize(errors, weight)}
        for label, mask in bands.items():
            if np.any(mask):
                summary[name][label] = summarize(errors[mask], weight[mask])
    return {
        "status": "conditional_flight_specific_force_benchmark",
        "testset_sha256": TESTSET_SHA256,
        "source_sha256": test_hashes,
        "speed_range_m_s": [round(float(speed.min()), 6), round(float(speed.max()), 6)],
        "segments": segments,
        "summary": summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--freeze", type=Path, help="Write calibration coefficients without reading test files.")
    parser.add_argument("--evaluate", type=Path, help="Read frozen calibration coefficients and score test files.")
    parser.add_argument("--results", type=Path)
    args = parser.parse_args()
    if args.freeze is not None and args.evaluate is None and args.results is None:
        args.freeze.write_text(json.dumps(calibrate(args.source), indent=2) + "\n", encoding="utf-8")
    elif args.evaluate is not None and args.results is not None and args.freeze is None:
        frozen = json.loads(args.evaluate.read_text(encoding="utf-8"))
        args.results.write_text(json.dumps(score(args.source, frozen), indent=2) + "\n", encoding="utf-8")
    else:
        parser.error("Select --freeze or --evaluate with --results")


if __name__ == "__main__":
    main()
