"""Synthetic controls for the offline UAV-FD indicator."""
from pathlib import Path
import runpy

import numpy as np
import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_uav_fd_rotor_order.py"))


def test_order_one_follows_rotor_speed_at_irregular_sample_times():
    t = np.arange(700) / 350 + 0.0002 * np.sin(np.arange(700))
    vibration = np.column_stack((0.4 * np.sin(2 * np.pi * 100 * t), np.zeros((len(t), 2))))
    score, rms = bench["spectral_score"](t, vibration, np.full(6, 6000.0))
    off_order, rms_again = bench["spectral_score"](t, vibration, np.full(6, 4800.0))
    assert score == pytest.approx(0.4, abs=0.015)
    assert off_order < score / 5
    assert rms_again == pytest.approx(rms)


def test_excluded_windows_break_alarm_runs():
    windows = [bench["WindowScore"](i, 6000, float(i in (0, 2)), 0) for i in (0, 2, 4, 5, 6, 7)]
    one = bench["decide"](windows, "rotor_order", 0.5)
    assert one["verdict"] == "NO_ALERT"
    windows[3] = bench["WindowScore"](5, 6000, 1, 0)
    windows[4] = bench["WindowScore"](6, 6000, 1, 0)
    two = bench["decide"](windows, "rotor_order", 0.5)
    assert two["verdict"] == "FAULT_INDICATOR_ALERT"
    assert two["first_alert_window"] == 6
    assert bench["decide"](windows[:5], "rotor_order", 0.5)["verdict"] == "INCONCLUSIVE_INSUFFICIENT_WINDOWS"
