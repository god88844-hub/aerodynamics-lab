"""Check the pre-pulse voltage boundary used for conditional predictions."""
from pathlib import Path
import runpy

import numpy as np
import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_melasta_pulse.py"))


def test_prepulse_anchor_excludes_pulse_samples_and_checks_duration():
    time = np.linspace(0, 30, 301)
    pulse = time >= 1.0
    data = {
        "time": time,
        "step_index": np.where(pulse, 17, 16),
        "voltage": np.where(pulse, 3.0, 3.7),
        "current": np.where(pulse, -68.0, -5.0),
    }
    anchor, voltage, power = bench["pulse_signals"](data)
    assert anchor == pytest.approx(3.7)
    assert voltage[0] == voltage[-1] == 3.0
    assert bench["average_power"](power) == pytest.approx(204.0)
    with pytest.raises(ValueError, match="29 seconds"):
        bench["pulse_signals"]({key: signal[:-1] for key, signal in data.items()})
