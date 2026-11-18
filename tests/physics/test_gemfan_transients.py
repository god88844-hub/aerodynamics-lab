"""Check causal replay, timestamp discontinuities, and reused-row exclusion."""

import importlib
from pathlib import Path

import pytest


def test_lag_uses_previous_command_and_restarts_on_a_gap(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    bench = importlib.import_module("benchmark_gemfan_transients")
    static = [{"pwm_us": 1100, "current_a": 1.0}, {"pwm_us": 1350, "current_a": 6.0}]
    rows = [bench.Row(t, command, 0.0, 4.0) for t, command in [(0, 1100), (0.1, 1350), (0.2, 1350), (1.0, 1100), (1.1, 1350)]]
    estimates = bench.replay(rows, static, 0.1, "current_a")
    assert estimates == pytest.approx([None, 1.0, 4.160602794, None, 1.0])
    assert bench.error_series(rows, estimates, "current_a", {rows[1]}) == pytest.approx([0.160602794, -3.0])
