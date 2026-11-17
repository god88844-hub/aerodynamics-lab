"""Classical fixed-step RK4 integrator.

Role in AeroForge: verification fallback and deterministic reference solver.
The adaptive scipy solver (``physics.integration.scipy_solver``) is the
production default; fixed-step RK4 is kept because (a) the dynamics unit
tests verify against it deterministically, and (b) M7 convergence studies
need a fixed-step family for order verification.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

import numpy as np

from physics.integration.runtime_limit import check_time_limit


def rk4_step(
    f: Callable[[float, np.ndarray], np.ndarray],
    t: float,
    x: np.ndarray,
    dt: float,
) -> np.ndarray:
    """One classical Runge-Kutta 4 step for x' = f(t, x)."""
    k1 = f(t, x)
    k2 = f(t + dt / 2.0, x + dt / 2.0 * k1)
    k3 = f(t + dt / 2.0, x + dt / 2.0 * k2)
    k4 = f(t + dt, x + dt * k3)
    return x + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def integrate_fixed(
    f: Callable[[float, np.ndarray], np.ndarray],
    x0: np.ndarray,
    t0: float,
    t1: float,
    dt: float,
    post_step: Optional[Callable[[np.ndarray], np.ndarray]] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate x' = f(t, x) from t0 to t1 with fixed step ``dt``.

    The final step is trimmed to land exactly on t1. ``post_step`` is applied
    after every step (e.g. quaternion renormalization). Returns (times, states)
    including both endpoints.
    """
    if dt <= 0.0:
        raise ValueError("dt must be > 0")
    if t1 <= t0:
        raise ValueError("t1 must be > t0")

    steps = max(1, math.ceil((t1 - t0) / dt - 1e-12))
    times = [t0]
    states = [np.asarray(x0, dtype=float).copy()]
    x = np.asarray(x0, dtype=float).copy()
    t = t0
    for _ in range(steps):
        check_time_limit()
        h = min(dt, t1 - t)
        x = rk4_step(f, t, x, h)
        if post_step is not None:
            x = np.asarray(post_step(x), dtype=float)
        t += h
        times.append(t)
        states.append(x.copy())
    return np.array(times), np.array(states)
