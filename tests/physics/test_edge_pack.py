"""Guard clock alignment, energy aggregation and the initial voltage anchor."""
import runpy
from pathlib import Path

import numpy as np
import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_edge_pack.py"))


def test_native_power_and_clock_gaps():
    time = np.arange(1200) / 200
    current = np.tile([0.0, 2.0], 600)
    raw = {"t": time, "LLF20C": current, "LLF20V": 20 - current}
    i, v, power = bench["second_means"](raw)
    assert i * v == pytest.approx(np.full(6, 19.0))
    assert power == pytest.approx(np.full(6, 18.0))
    time[400:] += 0.005
    with pytest.raises(ValueError, match="clock"):
        bench["second_means"](raw)


def test_later_voltage_is_used_only_as_an_observation():
    current = np.arange(9.0)
    voltage = np.full(9, 20.0)
    x, v0 = bench["centered_inputs"](current, voltage)
    voltage[5:] = 0.0
    changed, anchor = bench["centered_inputs"](current, voltage)
    assert changed == pytest.approx(x)
    assert anchor == v0 == 20.0
