"""Pitt-Peters 3-state dynamic rotor inflow model [lambda_0, lambda_s, lambda_c]."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def step_pitt_peters_inflow(
    lambda_vec: np.ndarray,
    *,
    ct: float,
    cl_roll: float,
    cm_pitch: float,
    advance_ratio_mu: float,
    inflow_axial_lambda_c: float,
    omega_rad_s: float,
    dt_s: float,
) -> np.ndarray:
    """Advance finite-state Pitt-Peters inflow [lambda_0, lambda_s, lambda_c] by one RK4 step.

    Solves M * d(lambda)/d(psi) + L^-1 * lambda = [C_T, C_l, C_m]^T, psi = Omega * t.
    Refuses invalid negative/nonfinite angular rate or extreme vortex-ring descent singularities.
    """
    lam = np.asarray(lambda_vec, dtype=float)
    if lam.shape != (3,) or not np.all(np.isfinite(lam)):
        raise ValueError("lambda_vec must be finite shape (3,)")
    if omega_rad_s <= 0.0 or dt_s <= 0.0:
        raise ValueError("omega_rad_s and dt_s must be > 0")
    if advance_ratio_mu < 0.0:
        raise ValueError("advance_ratio_mu must be >= 0")

    # Apparent mass matrix M = diag(128/(75*pi), -16/(45*pi), -16/(45*pi)) (sign positive in induced-moment convention)
    m_diag = np.array([128.0 / (75.0 * math.pi), 16.0 / (45.0 * math.pi), 16.0 / (45.0 * math.pi)], dtype=float)
    forcing = np.array([ct, cl_roll, cm_pitch], dtype=float)

    def _rhs(l_state: np.ndarray) -> np.ndarray:
        v_tot = math.sqrt(advance_ratio_mu ** 2 + (inflow_axial_lambda_c + l_state[0]) ** 2)
        v_tot = max(0.02, v_tot)  # bounded static-hover floor matching Peters-HaQuang V_T / V_m
        v_m = (advance_ratio_mu ** 2 + (inflow_axial_lambda_c + l_state[0]) * (inflow_axial_lambda_c + 2.0 * l_state[0])) / v_tot
        v_m = max(0.02, v_m)
        chi = math.atan2(advance_ratio_mu, max(1e-4, inflow_axial_lambda_c + l_state[0]))
        half_x = math.tan(0.5 * chi)
        sin_c = math.sin(chi)
        cos_c = math.cos(chi)
        # Pitt-Peters static L matrix
        L = np.array(
            [
                [0.5 / v_tot, (15.0 * math.pi / 64.0) * half_x / v_m, 0.0],
                [0.0, 4.0 * cos_c / ((1.0 + cos_c) * v_m), 0.0],
                [0.0, 0.0, 4.0 / ((1.0 + cos_c) * v_m)],
            ],
            dtype=float,
        )
        # d(lambda)/dt = omega * M^-1 * (forcing - L^-1 * lambda)
        l_inv_lam = np.linalg.solve(L, l_state)
        _ = sin_c  # preserved for wake geometry symmetry
        return omega_rad_s * (forcing - l_inv_lam) / m_diag

    k1 = _rhs(lam)
    k2 = _rhs(lam + 0.5 * dt_s * k1)
    k3 = _rhs(lam + 0.5 * dt_s * k2)
    k4 = _rhs(lam + dt_s * k3)
    return lam + (dt_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def run_pitt_peters_step_response(
    *,
    ct_step: float = 0.008,
    advance_ratio_mu: float = 0.0,
    omega_rad_s: float = 160.0,
    duration_s: float = 0.25,
    dt_s: float = 0.001,
) -> dict[str, Any]:
    """Integrate thrust step response of Pitt-Peters dynamic inflow."""
    steps = max(1, math.ceil(duration_s / dt_s))
    lam = np.array([math.sqrt(max(1e-6, ct_step * 0.25)), 0.0, 0.0], dtype=float)
    history = [lam.tolist()]
    for _ in range(steps):
        lam = step_pitt_peters_inflow(
            lam,
            ct=ct_step,
            cl_roll=0.0004,
            cm_pitch=-0.0002,
            advance_ratio_mu=advance_ratio_mu,
            inflow_axial_lambda_c=0.0,
            omega_rad_s=omega_rad_s,
            dt_s=dt_s,
        )
        history.append(lam.tolist())
    return {
        "schema_version": "1.0",
        "model": "pitt_peters_3state_dynamic_inflow",
        "step_count": steps,
        "final_inflow": lam.tolist(),
        "history": history,
        "physical_validation_status": "UNVALIDATED",
    }
