"""M10: 3D flight playback receives unmodified solver positions and attitude."""
import numpy as np
import pytest
from physics.scenarios.service import _states_telemetry

def test_replay_stream_is_sourced_from_solver_states():
    times = np.array([0.0, 0.5, 1.0])
    states = np.zeros((3, 13))
    states[:, :3] = [[0, 0, 0], [1, -1, 2], [2, -2, 4]]
    states[:, 6:10] = [[1, 0, 0, 0], [0.70710678, 0, 0, 0.70710678], [0, 0, 0, 1]]
    thrusts = np.ones((3, 4)) * 4.9
    replay = _states_telemetry(times, states, thrusts)
    assert replay["x"] == [0.0, 1.0, 2.0]
    assert replay["y"] == [0.0, -1.0, -2.0]
    assert replay["z"] == [0.0, 2.0, 4.0]
    assert len(replay["q_wxyz"]) == len(replay["t"]) == 3
    assert replay["q_wxyz"][1] == pytest.approx(states[1, 6:10].tolist())

def test_attitude_and_position_share_decimation_indices():
    n = 509
    times = np.arange(n, dtype=float) * 0.01
    states = np.zeros((n, 13))
    states[:, 0] = np.arange(n)
    states[:, 6] = 1.0
    thrusts = np.zeros((n, 4))
    replay = _states_telemetry(times, states, thrusts)
    assert len(replay["t"]) <= 400
    assert len(replay["t"]) == len(replay["q_wxyz"]) == len(replay["x"])
    assert replay["x"][0] == 0
    assert replay["x"][-1] == n - 1
    assert all(q == [1, 0, 0, 0] for q in replay["q_wxyz"])
