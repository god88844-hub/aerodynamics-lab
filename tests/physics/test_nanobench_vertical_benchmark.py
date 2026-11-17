"""Focused solver and source-window checks. Fixtures contain synthetic data."""
from pathlib import Path
import runpy

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
bench = runpy.run_path(str(ROOT / "scripts/benchmark_nanobench_vertical.py"))


def hover_block():
    block = np.zeros(51, dtype=[(name, float) for name in bench["CHANNELS"]])
    block["t"] = np.arange(51) / 100
    block["pz"] = 1.0
    block["qw"] = 1.0
    block["pwr_pm_vbat"] = 4.0
    for key in bench["MOTOR_CHANNELS"]:
        block[key] = 65535 / 2
    return block


def test_vertical_prediction_does_not_consume_later_measured_altitude_or_vertical_velocity():
    block = hover_block()
    thrust = bench["MASS_KG"] * bench["STANDARD_GRAVITY"] / 16
    parameters = np.array([thrust, 0.01])
    model, baseline = bench["forecast"](block, parameters)
    assert model == pytest.approx([0, 0])
    assert baseline == pytest.approx([0, 0])

    block["pz"][1:] += 0.25
    block["vz"][1:] -= 0.5
    model, baseline = bench["forecast"](block, parameters)
    assert model == pytest.approx([-0.25, 0.5])
    assert baseline == pytest.approx([-0.25, 0.5])


def test_gap_rejects_window_without_filling_it():
    block = hover_block()
    flight = bench["Flight"]("synthetic", block, {})
    assert bench["admissible_windows"](flight, 0.5) == ([(0, 50)], {})
    block["t"][25:] += 0.03
    assert bench["admissible_windows"](flight, 0.5) == ([], {"sampling_gap_or_duration": 1})
