"""Regressions for command causality and source clock rejection."""
from pathlib import Path
import runpy

import numpy as np
import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_dronepropa_altitude.py"))


def test_two_stage_altitude_uses_only_current_and_past_commands():
    desired = np.concatenate([np.full(5, 0.2), np.full(75, 0.8)])
    model = bench["predicted_altitude"]
    predicted = model(desired, 0.10, 2)
    assert predicted[:7] == pytest.approx(np.full(7, 0.2))
    assert 0.2 < predicted[7] < 0.8
    assert predicted[-1] == pytest.approx(0.8, abs=1e-5)


def test_resample_rejects_duplicate_clock_ticks_and_retains_command_window():
    commander = np.zeros((37, 6))
    commander[0] = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05]
    commander[23] = [0.0, 0.0, 0.15, 0.18, 0.22, 0.23]
    commander[27] = [0.0, 0.0, 0.2, 0.4, 0.65, 0.8]
    desired, measured, window = bench["resample"](commander)
    assert desired == pytest.approx([0.0, 0.2, 0.65])
    assert measured == pytest.approx([0.0, 0.15, 0.22])
    assert list(window) == [False, True, True]
    commander[0, 3] = 0.02
    with pytest.raises(ValueError, match="strictly increasing"):
        bench["resample"](commander)
