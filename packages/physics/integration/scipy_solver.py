"""Adaptive ODE integration via scipy.integrate.solve_ivp — production solver.

Solver tolerances are explicit arguments so they can be recorded in the
simulation report (traceability) and swept in M7 convergence studies.
Note: quaternion renormalization is applied only at accepted output points;
intermediate stage evaluations see the raw state (drift is bounded by the
tight tolerances and is negligible relative to model error — documented).
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from scipy.integrate import solve_ivp


def integrate_ivp(
    f: Callable[[float, np.ndarray], np.ndarray],
    x0: np.ndarray,
    t0: float,
    t1: float,
    rtol: float = 1e-9,
    atol: float = 1e-11,
    max_step: float = np.inf,
    method: str = "RK45",
    post_step: Optional[Callable[[np.ndarray], np.ndarray]] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate x' = f(t, x) adaptively; returns (times, states)."""
    sol = solve_ivp(
        lambda t, x: f(t, x),
        (t0, t1),
        np.asarray(x0, dtype=float),
        method=method,
        rtol=rtol,
        atol=atol,
        max_step=max_step,
    )
    if not sol.success:
        raise RuntimeError(f"ODE integration failed: {sol.message}")
    states = sol.y.T
    if post_step is not None:
        states = np.array([post_step(s) for s in states])
    return sol.t, states
