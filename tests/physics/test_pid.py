"""PID unit verification: steady-state error, damping, anti-windup."""

import numpy as np
import pytest

from physics.controller.pid import PID


def simulate_plant(pid: PID, target: float, duration: float, dt: float, x0: float = 0.0):
    """First-order plant x' = -x + u (time constant 1 s)."""
    n = int(duration / dt)
    x = x0
    xs = []
    for _ in range(n):
        u = pid.step(target - x, x, dt)
        x = x + (-x + u) * dt
        xs.append(x)
    return np.array(xs)


def test_proportional_only_leaves_steady_state_error():
    pid = PID(kp=2.0)
    xs = simulate_plant(pid, target=1.0, duration=20.0, dt=0.01)
    expected_value = 2.0 / (1.0 + 2.0)  # x_inf = kp/(1+kp) * target
    assert xs[-1] == pytest.approx(expected_value, abs=1e-6)


def test_integral_eliminiates_steady_state_error():
    pid = PID(kp=2.0, ki=1.0, output_limits=(-10.0, 10.0))
    xs = simulate_plant(pid, target=1.0, duration=30.0, dt=0.01)
    assert xs[-1] == pytest.approx(1.0, abs=1e-4)


def test_derivative_reduces_overshoot():
    """Second-order plant x'' = u (double integrator): kd provides damping."""
    dt = 0.01
    target = 1.0

    def simulate(pid: PID, duration: float) -> np.ndarray:
        n = int(duration / dt)
        x = 0.0
        v = 0.0
        xs = []
        for _ in range(n):
            u = pid.step(target - x, x, dt)
            a = u  # x'' = u (unit mass)
            v += a * dt
            x += v * dt
            xs.append(x)
        return np.array(xs)

    xs_p = simulate(PID(kp=8.0), 8.0)
    xs_pd = simulate(PID(kp=8.0, kd=4.0), 8.0)  # zeta = kd/(2*sqrt(kp)) = 0.71
    overshoot_p = float(np.max(xs_p) - target)
    overshoot_pd = float(np.max(xs_pd) - target)
    assert overshoot_p > 0.2                     # P-only clearly overshoots
    assert overshoot_pd < overshoot_p * 0.25


def test_anti_windup_recovers_quickly():
    """Sustained large error saturates the output; when the error reverses, the
    output must leave the limit promptly (no stored windup)."""
    pid = PID(kp=1.0, ki=5.0, output_limits=(-1.0, 1.0))
    dt = 0.01
    x = 0.0
    # 5 s of large positive error -> output pinned at the upper limit.
    for _ in range(500):
        u = pid.step(50.0 - x, x, dt)
        x += (-x + u) * 0.01
    assert pid.step(50.0 - x, x, dt) == pytest.approx(1.0)
    # Error reverses: output must drop well below the upper limit within 0.2 s.
    left_limit_at = None
    for i in range(20):
        u = pid.step(-1.0 - x, x, dt)
        if u < 0.5:
            left_limit_at = i
            break
        x += (-x + u) * 0.01
    assert left_limit_at is not None, "output stayed windup-pinned after reversal"


def test_invalid_dt_raises():
    pid = PID(kp=1.0)
    with pytest.raises(ValueError):
        pid.step(1.0, 0.0, 0.0)
