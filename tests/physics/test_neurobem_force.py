"""Verify time weighting and the body-axis drag convention."""

import runpy
from pathlib import Path

import numpy as np
import pytest

bench = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/benchmark_neurobem_force.py"))


def test_uneven_timestamps_score_by_elapsed_time():
    segment = np.array([[0.0], [1.0], [4.0]])
    weights = bench["sample_seconds"](segment)
    assert weights == pytest.approx([0.5, 2.0, 1.5])
    squared_error = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [4.0, 0.0, 0.0]])
    result = bench["summarize"](squared_error, weights)
    assert result["seconds"] == 4.0
    assert result["vector_rmse_m_s2"] == pytest.approx(np.sqrt(2.0))


def test_drag_opposes_body_motion_and_rotor_drag_stays_in_plane():
    sample = np.zeros((1, 29))
    sample[0, 14:17] = [3.0, -4.0, 0.0]
    sample[0, 20:24] = [1000.0, 2000.0, 1000.0, 2000.0]
    terms, _, speed = bench["features"](sample)
    assert speed == pytest.approx([5.0])
    assert terms[0, :, 0] == pytest.approx([0.0, 0.0, 10.0])
    assert terms[0, :, 1] == pytest.approx([-15.0, 20.0, 0.0])
    assert terms[0, :, 2] == pytest.approx([-18.0, 24.0, 0.0])
