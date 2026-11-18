"""Synthetic checks for chronology and the constant-power forecast equation."""
from pathlib import Path
import runpy

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_prediction_uses_only_the_prefix(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    bench = runpy.run_path(str(ROOT / "scripts/benchmark_sit_cutoff_forecast.py"))
    fit = {
        "max_charge_ah": 5.0, "charge_knots_ah": [0, 5],
        "one_rc": {
            "tau_s": 5, "series_ohm": [0.05] * 5, "polarization_ohm": [0.01] * 5,
            "ocv_v": [[96, 24, 24, 24, 24], [96, 24, 24, 24, 24]],
        },
    }
    times = np.arange(0, 432, 2, dtype=float)
    current = np.where(times < 354, 0.1, 100.0)
    charge = np.linspace(0, 1.5, len(times))
    voltages = np.column_stack((np.where(times < 354, 95.995, 90), np.full((len(times), 4), 23)))
    c = bench["Cycle"](1, times, current, charge, charge.copy(), voltages, np.zeros((len(times), 4)), np.zeros(len(times)))
    original = bench["forecast"](c, fit, update=True)
    assert original is not None
    assert original.current * original.voltage == pytest.approx(np.full(len(original.voltage), 9000))
    future = times > bench["ISSUE_TIME_S"]
    c.voltages[future, 0] = 10
    c.current[future] = 400
    c.charge_ah[future] = 99
    modified = bench["forecast"](c, fit, update=True)
    assert modified is not None
    assert modified.voltage == pytest.approx(original.voltage)
    assert modified.current == pytest.approx(original.current)


def test_unavailable_constant_power_returns_no_current(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    bench = runpy.run_path(str(ROOT / "scripts/benchmark_sit_cutoff_forecast.py"))
    assert bench["constant_power_current"](9000, 20, 1) is None
