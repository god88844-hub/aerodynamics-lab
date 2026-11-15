"""Convergence studies (M7): time-step refinement until results stabilize.

Two families:
1. analytic — torque-free Euler dynamics vs a fine-reference solution
   (constant-acceleration free fall is integrated exactly by RK4 and carries
   no information);
2. closed-loop — the takeoff scenario re-run with increasing integrator
   substeps at a fixed control period; the metric is the RMS z-deviation
   against the finest refinement.

Converged = the coarsest refinement that stays inside the declared
tolerance; the study records the family so reports can state at what
discretization the published numbers are valid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from physics.dynamics.quaternion import rotation_matrix
from physics.dynamics.rigid_body import RigidBody, make_state, normalize_state, unpack_state
from physics.integration.rk4 import integrate_fixed

INERTIA = np.diag([0.08, 0.06, 0.12])


@dataclass
class ConvergenceStudy:
    name: str
    metric: str
    tolerance: float
    refinements: list[dict] = field(default_factory=list)
    converged: bool = False
    converged_level: int | None = None
    notes: str = ""

    def summary(self) -> dict:
        return {
            "name": self.name,
            "metric": self.metric,
            "tolerance": self.tolerance,
            "refinements": self.refinements,
            "converged": self.converged,
            "converged_level": self.converged_level,
            "notes": self.notes,
        }


def analytic_convergence(t_final: float = 1.0, tolerance: float = 1e-6) -> ConvergenceStudy:
    """Torque-free Euler dynamics: omega(1 s) vs a fine reference."""
    body = RigidBody(mass_kg=1.5, inertia_about_cog=INERTIA)
    w0 = np.array([2.0, 0.7, 0.3])
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], w0)
    f = lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3), gravity=False)  # noqa: E731

    ref_dt = 6.25e-4
    _, ref_states = integrate_fixed(f, x0, 0.0, t_final, ref_dt, post_step=normalize_state)
    ref_w = unpack_state(ref_states[-1])[3]

    study = ConvergenceStudy(
        name="time-step convergence (torque-free Euler dynamics)",
        metric="max |omega - omega_ref| [rad/s]",
        tolerance=tolerance,
        notes=f"reference dt={ref_dt}",
    )
    for level, dt in enumerate([0.02, 0.01, 0.005, 0.0025]):
        _, states = integrate_fixed(f, x0, 0.0, t_final, dt, post_step=normalize_state)
        w = unpack_state(states[-1])[3]
        err = float(np.linalg.norm(w - ref_w))
        study.refinements.append({"level": level, "dt_s": dt, "error": err})
        if err <= tolerance and not study.converged:
            study.converged = True
            study.converged_level = level
    return study


def closed_loop_convergence(design, library, tolerance_m: float = 2e-3) -> ConvergenceStudy:
    """Takeoff scenario at control dt 4 ms with integrator substeps 1/2/4:
    RMS z deviation against the finest refinement."""
    from physics.scenarios.runner import takeoff_climb_scenario, run_scenario

    study = ConvergenceStudy(
        name="closed-loop integrator convergence (takeoff scenario)",
        metric="RMS z deviation vs finest refinement [m]",
        tolerance=tolerance_m,
    )

    runs: dict[int, np.ndarray] = {}
    times_ref = None
    for level, substeps in enumerate([1, 2, 4]):
        scenario = takeoff_climb_scenario(5.0, duration_s=16.0)
        res = run_scenario(design, scenario, library, control_dt_s=0.004, substeps=substeps)
        if level == 0:
            times_ref = res.times
        runs[substeps] = res.states[:, 2]

    ref = runs[4]
    for level, substeps in enumerate([1, 2, 4]):
        rms = float(np.sqrt(np.mean((runs[substeps] - ref) ** 2)))
        study.refinements.append({"level": level, "substeps": substeps, "rms_z_deviation_m": rms})
        if rms <= tolerance_m and not study.converged:
            study.converged = True
            study.converged_level = level
    return study


def solver_tolerance_study(t_final: float = 1.0) -> ConvergenceStudy:
    """scipy adaptive tolerances on free fall: v(1 s) error vs the exact g."""
    from physics.integration.scipy_solver import integrate_ivp

    body = RigidBody(mass_kg=1.5, inertia_about_cog=INERTIA)
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3))
    f = lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3))  # noqa: E731

    study = ConvergenceStudy(
        name="adaptive solver tolerance (free fall)",
        metric="|v(1s) - g| [m/s]",
        tolerance=1e-8,
    )
    for level, rtol in enumerate([1e-6, 1e-8, 1e-10]):
        _, states = integrate_ivp(f, x0, 0.0, t_final, rtol=rtol, atol=rtol * 1e-2,
                                  post_step=normalize_state)
        err = abs(abs(states[-1][5]) - 9.80665)
        study.refinements.append({"level": level, "rtol": rtol, "error": err})
        if err <= study.tolerance and not study.converged:
            study.converged = True
            study.converged_level = level
    return study
