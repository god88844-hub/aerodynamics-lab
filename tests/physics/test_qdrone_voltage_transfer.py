"""Check causal smoothing and the study's strict voltage crossing rule."""

from pathlib import Path
import runpy

import numpy as np

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_qdrone_voltage_transfer.py"))


def test_voltage_reference_uses_first_sample_strictly_below_line():
    timestamps = np.array([1.0, 1.0025, 1.005])
    assert bench["first_below"](timestamps, np.array([14.1, 14.0, 13.9])) == 1.005
    assert bench["first_below"](timestamps, np.array([14.1, 14.0, 14.2])) is None


def test_smoothing_responds_only_at_or_after_input_change():
    signal = np.zeros(500)
    signal[100:] = 1.0
    result = bench["smooth"](signal, 0.05)
    assert np.all(result[:100] == 0.0)
    assert 0 < result[100] < result[-1] < 1.0
