"""Reproduce a retrospective capacity comparison on measured CFRP column traces."""
from __future__ import annotations

import argparse
import json
import math
from hashlib import sha256
from io import BytesIO
from pathlib import Path

WORKBOOK_SHA256 = "60a111532fe91494bd586eda3dd7f22142f5270fdf201f4fd7f3726ba1e9e883"
GAUGE_MM = (30, 65, 130)
KGF_TO_N = 9.80665
# Supplementary Table 5 lists experimental values rounded by the authors.
SERIES = {
    "e1": ("SFig. 7a", (744.0, 228.6, 82.8)),
    "e2": ("SFig. 7b", (976.6, 836.8, 180.5)),
    "e5": ("SFig. 7c", (2198.0, 1155.0, 682.8)),
}


def compare_lengths(peaks: list[float]) -> dict:
    short, middle, long = peaks
    if not all(math.isfinite(p) and p > 0 for p in peaks) or long >= short:
        raise ValueError("The endpoint model requires positive loads and a lower long-column capacity")
    short_mm, middle_mm, long_mm = GAUGE_MM
    # Reciprocal capacity linear in squared unsupported length (Rankine form).
    fraction = (middle_mm**2 - short_mm**2) / (long_mm**2 - short_mm**2)
    predicted = {
        "euler_from_long": long * (long_mm / middle_mm) ** 2,
        "reciprocal_from_endpoints": 1 / ((1 - fraction) / short + fraction / long),
    }
    return {
        name: {"prediction_n": round(value, 4), "prediction_minus_peak_n": round(value - middle, 4),
               "overestimates_observed_peak": value > middle}
        for name, value in predicted.items()
    }


def benchmark(path: Path) -> dict:
    from openpyxl import load_workbook

    raw = path.read_bytes()
    if sha256(raw).hexdigest() != WORKBOOK_SHA256:
        raise ValueError("Publisher workbook SHA-256 mismatch")
    workbook = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    series = {}
    try:
        for identifier, (sheet, published) in SERIES.items():
            rows = iter(workbook[sheet].values)
            headings, units = next(rows), next(rows)
            if headings[::2] != tuple(f"{identifier}_{n}" for n in (50, 85, 150)) or units != ("kgf", "mm") * 3:
                raise ValueError(f"Unexpected specimen identity or units in {sheet}")
            peaks = [0.0] * 3
            counts = [0] * 3
            for row in rows:
                for i in range(3):
                    force, displacement = row[2*i:2*i+2]
                    if force is None and displacement is None:
                        continue
                    if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in (force, displacement)):
                        raise ValueError(f"Invalid force/displacement pair in {sheet}")
                    peaks[i] = max(peaks[i], force * KGF_TO_N)
                    counts[i] += 1
            if any(abs(peak - reference) > 1.0 for peak, reference in zip(peaks, published)):
                raise ValueError(f"Measured peaks disagree with Supplementary Table 5 in {sheet}")
            series[identifier] = {
                "sample_counts": counts, "observed_peaks_n": [round(p, 4) for p in peaks],
                "published_peaks_n": published, "middle_length_comparison": compare_lengths(peaks),
            }
    finally:
        workbook.close()
    return {"source_sha256": WORKBOOK_SHA256, "design": "retrospective_length_transfer",
            "gauge_lengths_mm": GAUGE_MM, "series": series}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(benchmark(args.workbook), indent=2) + "\n", encoding="utf-8")
