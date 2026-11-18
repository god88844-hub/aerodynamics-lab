"""Guard the static comparison against unsupported commands."""

from pathlib import Path
import runpy

import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_gemfan_bench.py"))


def test_static_interpolator_rejects_extrapolation():
    calibration = [{"pwm_us": 1200, "thrust_n": 2}, {"pwm_us": 1400, "thrust_n": 6}]
    interpolate = bench["interpolated_output"]
    assert interpolate(1300, calibration, "thrust_n") == pytest.approx(4)
    assert interpolate(1400, calibration, "thrust_n") == pytest.approx(6)
    with pytest.raises(ValueError, match="outside calibration support"):
        interpolate(1410, calibration, "thrust_n")
