"""Test load-dependent voltage on NASA's instrumented Edge 540 battery installation."""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from scipy.io import loadmat
from scipy.optimize import nnls

ARCHIVE_SHA = "f6ca7b1eeaed8b75da92479a778bbef9253997a572cc20ab480f872a9ee3a9b0"
PREFIX = "15. HIRF Battery Data Set/Set"
SAMPLES_PER_SECOND = 200
ANCHOR_SECONDS = 5
MODELS = {"charge_only": 1, "charge_and_sag": 2}


def second_means(raw: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time, current, voltage = (np.asarray(raw[key], dtype=float) for key in ("t", "LLF20C", "LLF20V"))
    if time.ndim != 1 or current.shape != time.shape or voltage.shape != time.shape:
        raise ValueError("Expected one current and one voltage observation per timestamp")
    if not all(np.isfinite(x).all() for x in (time, current, voltage)):
        raise ValueError("Nonfinite recording")
    if not np.allclose(np.diff(time), 1 / SAMPLES_PER_SECOND, rtol=0, atol=1e-7):
        raise ValueError("Recording does not use the calibrated 200 Hz clock")
    n = len(time) // SAMPLES_PER_SECOND * SAMPLES_PER_SECOND
    if n < (ANCHOR_SECONDS + 1) * SAMPLES_PER_SECOND:
        raise ValueError("Recording too short for the initial anchor and scoring")
    def blocks(x):
        return x[:n].reshape(-1, SAMPLES_PER_SECOND).mean(axis=1)
    return blocks(current), blocks(voltage), blocks(current * voltage)


def centered_inputs(current: np.ndarray, voltage: np.ndarray):
    # Integrated Ah at each block midpoint, using signed current including sensor offsets.
    charge = (np.cumsum(current) - 0.5 * current) / 3600
    terms = np.column_stack((charge, current))
    initial_v = float(np.mean(voltage[:ANCHOR_SECONDS]))
    return (terms - terms[:ANCHOR_SECONDS].mean(axis=0))[ANCHOR_SECONDS:], initial_v


def records(archive: ZipFile, sets):
    for number in sets:
        with ZipFile(BytesIO(archive.read(f"{PREFIX}{number}.zip"))) as inner:
            for name in sorted(inner.namelist()):
                raw = inner.read(name)
                signals = loadmat(BytesIO(raw), simplify_cells=True)["data"]
                yield number, name, sha256(raw).hexdigest(), signals


def calibrate(archive: ZipFile) -> dict:
    matrices, targets, hashes = [], [], {}
    for _, name, digest, signals in records(archive, [1]):
        current, voltage, _ = second_means(signals)
        terms, initial_v = centered_inputs(current, voltage)
        weight = 1 / np.sqrt(len(terms))
        matrices.append(terms * weight)
        targets.append((initial_v - voltage[ANCHOR_SECONDS:]) * weight)
        hashes[name] = digest
    matrix, target = np.vstack(matrices), np.concatenate(targets)
    return {
        "archive_sha256": ARCHIVE_SHA, "calibration_sha256": hashes,
        "coefficients": {name: nnls(matrix[:, :size], target)[0].tolist() for name, size in MODELS.items()},
    }


def score(archive: ZipFile, frozen: dict) -> dict:
    if frozen["archive_sha256"] != ARCHIVE_SHA:
        raise ValueError("Model was frozen for a different source archive")
    for model, size in MODELS.items():
        coefficients = np.asarray(frozen["coefficients"][model])
        if coefficients.shape != (size,) or not np.all(np.isfinite(coefficients) & (coefficients >= 0)):
            raise ValueError(f"Unexpected frozen coefficients for {model}")
    output = {}
    used_digests = set(frozen["calibration_sha256"].values())
    for number, name, digest, signals in records(archive, range(2, 7)):
        if name in output or name in frozen["calibration_sha256"] or digest in used_digests:
            raise ValueError(f"Repeated physical record {name}")
        used_digests.add(digest)
        row = {"source_set": number, "sha256": digest}
        output[name] = row
        try:
            current, voltage, power = second_means(signals)
        except (KeyError, ValueError) as exc:
            row["unassessable"] = str(exc)
            continue
        terms, initial_v = centered_inputs(current, voltage)
        measured = voltage[ANCHOR_SECONDS:]
        current = current[ANCHOR_SECONDS:]
        measured_wh = float(power[ANCHOR_SECONDS:].sum() / 3600)
        row.update(seconds=len(terms), initial_v=round(initial_v, 5), measured_net_wh=round(measured_wh, 5),
                   current_range_a=[round(float(current.min()), 4), round(float(current.max()), 4)],
                   minimum_mean_voltage_v=round(float(measured.min()), 5))
        row["models"] = {}
        for model, size in MODELS.items():
            prediction = initial_v - terms[:, :size] @ frozen["coefficients"][model]
            error = prediction - measured
            row["models"][model] = {
                "mae_v": round(float(np.abs(error).mean()), 6),
                "rmse_v": round(float(np.sqrt(np.mean(error**2))), 6),
                "max_optimistic_v": round(float(error.max()), 6),
                "error_at_minimum_mean_voltage_v": round(float(error[np.argmin(measured)]), 6),
                "net_energy_error_wh": round(float(current @ prediction / 3600) - measured_wh, 6),
            }
    return {"archive_sha256": ARCHIVE_SHA, "runs": output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--evaluate", type=Path, help="Score later sets with a frozen coefficient file")
    args = parser.parse_args()
    with args.archive.open("rb") as stream:
        digest = sha256()
        for chunk in iter(lambda: stream.read(2**20), b""):
            digest.update(chunk)
        if digest.hexdigest() != ARCHIVE_SHA:
            raise ValueError("NASA archive SHA-256 mismatch")
        with ZipFile(stream) as archive:
            result = calibrate(archive) if args.evaluate is None else score(
                archive, json.loads(args.evaluate.read_text(encoding="utf-8"))
            )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
