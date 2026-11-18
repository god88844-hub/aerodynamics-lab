"""Synthetic unit checks for the offline battery-module benchmark."""
from pathlib import Path
import runpy

import numpy as np
import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_sit_module.py"))


def test_monotone_ocv_fits_charged_cell_cap():
    charge = np.linspace(0, 1, 10)
    design = bench["ocv_basis"](charge, np.array([0, 1]))
    coeffs = bench["fit_bounded_ocv"](design, 4.4 - 0.5 * charge, 2, 1)
    fitted = design @ coeffs
    assert fitted[0] == pytest.approx(4.2)
    assert np.all(np.diff(fitted) <= 0)


def test_study_limits_flag_observed_misses():
    v = np.array([[80, 19.8, 20, 20, 20], [79.9, 19.7, 20, 20, 20]])
    t = np.array([[70, 68, 68, 68], [70.1, 68, 68, 68]])
    observed = bench["breaches"](v, t, np.array([5.0, 5.1]), np.array([400, 401]))
    assert all(flags.tolist() == [False, True] for flags in observed.values())
    modeled = bench["breaches"](v[:1], t[:1], np.array([5.0]), np.array([400]))
    verdict = bench["exposure"]([observed], [modeled])
    assert all(counts["missed_cycles"] == 1 for counts in verdict.values())
