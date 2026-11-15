"""Integrator verification: fixed-step RK4 behavior and scipy agreement."""

import numpy as np
import pytest

from physics.constants import STANDARD_GRAVITY as G
from physics.integration.rk4 import integrate_fixed, rk4_step
from physics.integration.scipy_solver import integrate_ivp


def free_fall(_: float, x: np.ndarray) -> np.ndarray:
    """2-state free fall x = [z, v_z], x' = [v, -g]."""
    return np.array([x[1], -G])


def test_rk4_step_exact_for_quadratic_position():
    """RK4 integrates z'' = -g exactly for constant acceleration: z(t) = z0 + v t - g t²/2."""
    x0 = np.array([0.0, 0.0])
    dt = 0.5
    x1 = rk4_step(free_fall, 0.0, x0, dt)
    assert x1[0] == pytest.approx(-G * dt**2 / 2.0, abs=1e-14)
    assert x1[1] == pytest.approx(-G * dt, abs=1e-14)


def test_integrate_fixed_hits_endpoints():
    times, _ = integrate_fixed(free_fall, np.zeros(2), 0.0, 1.0, 0.037)  # non-dividing dt
    assert times[0] == 0.0
    assert times[-1] == pytest.approx(1.0, abs=1e-12)
    assert np.all(np.diff(times) > 0)


def test_fourth_order_convergence():
    """RK4 error for x' = -x (non-polynomial) falls as dt^4: gate /50."""
    decay = lambda t, x: -np.asarray(x, dtype=float)  # noqa: E731
    exact = float(np.exp(-1.0))
    _, states_coarse = integrate_fixed(decay, np.array([1.0]), 0.0, 1.0, 0.1)
    _, states_fine = integrate_fixed(decay, np.array([1.0]), 0.0, 1.0, 0.025)
    e_coarse = abs(states_coarse[-1][0] - exact)
    e_fine = abs(states_fine[-1][0] - exact)
    assert e_fine < e_coarse / 50.0


def test_scipy_solver_agrees_with_rk4():
    _, states_rk4 = integrate_fixed(free_fall, np.zeros(2), 0.0, 1.0, 0.01)
    times, states_ivp = integrate_ivp(free_fall, np.zeros(2), 0.0, 1.0)
    assert times[-1] == pytest.approx(1.0)
    assert np.allclose(states_ivp[-1], states_rk4[-1], atol=1e-9)


def test_invalid_arguments_raise():
    with pytest.raises(ValueError):
        integrate_fixed(free_fall, np.zeros(2), 0.0, 1.0, 0.0)
    with pytest.raises(ValueError):
        integrate_fixed(free_fall, np.zeros(2), 1.0, 0.0, 0.1)
