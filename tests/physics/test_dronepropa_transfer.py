"""Check inclusive coverage and retain flight-level failures."""
import importlib
from pathlib import Path

import numpy as np
import pytest


def test_transfer_counts_boundary_and_whole_flight_failure(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    bench = importlib.import_module("benchmark_dronepropa_transfer")
    monkeypatch.setattr(bench, "residuals", lambda *_: {
        "moving_reference": np.array([-0.1, 0.1]), "remaining_window": np.array([-0.2, 0.21])
    })
    records = {"vehicle": [{"name": "example.mat"}]}
    fit = {"half_width_m": {"moving_reference": 0.1, "remaining_window": 0.2}}
    cohort = bench.evaluate(Path(), records, {}, fit)["cohorts"]["vehicle"]
    assert cohort["whole_flights_covered"] == 0
    assert cohort["worst_band_excess_m"] == pytest.approx(0.01)
    assert cohort["runs"][0]["regimes"]["moving_reference"]["covered_samples"] == 2
