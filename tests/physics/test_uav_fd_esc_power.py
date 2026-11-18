"""Checks for the offline ESC benchmark. These examples are synthetic."""
from pathlib import Path
import runpy

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def test_alarm_requires_consecutive_deficits_on_the_same_esc(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    bench = runpy.run_path(str(ROOT / "scripts/benchmark_uav_fd_esc_power.py"))

    def record(index, motor=None):
        normalized = np.ones(6)
        if motor is not None:
            normalized[motor] = 0.5
        return bench["EscWindow"](index, 6000, normalized, np.ones(6))

    model = {"motor_healthy_centers": [1] * 6, "deficit_threshold": 0.25}
    different = [record(0, 0), record(1, 1), record(2, 0), record(4, 0), record(5), record(6)]
    assert bench["decide"](different, "speed_normalized_power", model)["verdict"] == "NO_ALERT"
    same = [*different, record(7, 4), record(8, 4)]
    report = bench["decide"](same, "speed_normalized_power", model)
    assert report["first_alert_window"] == 8
    assert report["repeat_alarms_by_source_esc"] == {"ESC_4": 1}
