"""Full 6-DoF JSBSim-style stability & control derivative fixed-wing aircraft FDM."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np

from physics.constants import STANDARD_GRAVITY
from physics.dynamics.quaternion import conjugate, normalize, rotate
from physics.dynamics.rigid_body import RigidBody, make_state, unpack_state
from physics.environment.isa_atmosphere import isa_atmosphere_1976
from physics.integration.rk4 import rk4_step


@dataclass(frozen=True)
class FixedWingAeroDerivatives:
    """6-DoF nondimensional stability & control derivatives (body/wind axes)."""

    wing_area_m2: float
    wingspan_m: float
    mean_chord_m: float
    cl0: float = 0.28
    cl_alpha: float = 4.9
    cl_q: float = 3.8
    cl_de: float = 0.42
    cd0: float = 0.025
    k_induced: float = 0.048
    cy_beta: float = -0.35
    cy_dr: float = 0.14
    cm0: float = 0.02
    cm_alpha: float = -0.65  # statically pitch-stable (< 0)
    cm_q: float = -12.0
    cm_de: float = -1.10
    cl_beta: float = -0.08  # dihedral roll stability (< 0)
    cl_p: float = -0.45
    cl_r: float = 0.12
    cl_da: float = 0.22
    cn_beta: float = 0.10   # directional weathercock stability (> 0)
    cn_p: float = -0.05
    cn_r: float = -0.14
    cn_dr: float = -0.09
    alpha_stall_deg: float = 15.0


def compute_fixed_wing_wrench_body(
    aero: FixedWingAeroDerivatives,
    *,
    vel_body_m_s: np.ndarray,
    omega_body_rad_s: np.ndarray,
    rho_kg_m3: float,
    controls: dict[str, float],
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Evaluate 6-DoF aerodynamic forces & moments from Z-up body (v, omega) using standard FRD stability axes."""
    # Map AeroForge Z-up (+x fwd, +y left, +z up) -> standard aerospace FRD (+x fwd, +y right, +z down)
    u = float(vel_body_m_s[0])
    v_frd = -float(vel_body_m_s[1])
    w_frd = -float(vel_body_m_s[2])
    p = float(omega_body_rad_s[0])
    q_frd = -float(omega_body_rad_s[1])
    r_frd = -float(omega_body_rad_s[2])

    airspeed = math.sqrt(u * u + v_frd * v_frd + w_frd * w_frd)
    if airspeed < 2.0:
        raise ValueError("Airspeed < 2.0 m/s below fixed-wing aerodynamic model support")
    alpha = math.atan2(w_frd, max(1e-6, u))
    beta = math.asin(max(-0.99, min(0.99, v_frd / airspeed)))
    if abs(math.degrees(alpha)) > aero.alpha_stall_deg:
        raise ValueError(f"Post-stall AoA |alpha|={abs(math.degrees(alpha)):.2f} deg > {aero.alpha_stall_deg} deg")

    de = float(controls.get("elevator_rad", 0.0))
    da = float(controls.get("aileron_rad", 0.0))
    dr = float(controls.get("rudder_rad", 0.0))
    thrust_n = max(0.0, float(controls.get("thrust_n", 0.0)))

    qbar = 0.5 * rho_kg_m3 * airspeed * airspeed
    b = aero.wingspan_m
    c = aero.mean_chord_m
    s = aero.wing_area_m2
    inv_2v = 1.0 / (2.0 * airspeed)

    cl = aero.cl0 + aero.cl_alpha * alpha + aero.cl_q * (q_frd * c * inv_2v) + aero.cl_de * de
    cd = aero.cd0 + aero.k_induced * cl * cl
    cy = aero.cy_beta * beta + aero.cy_dr * dr

    c_roll = aero.cl_beta * beta + aero.cl_p * (p * b * inv_2v) + aero.cl_r * (r_frd * b * inv_2v) + aero.cl_da * da
    c_pitch = aero.cm0 + aero.cm_alpha * alpha + aero.cm_q * (q_frd * c * inv_2v) + aero.cm_de * de
    c_yaw = aero.cn_beta * beta + aero.cn_p * (p * b * inv_2v) + aero.cn_r * (r_frd * b * inv_2v) + aero.cn_dr * dr

    # Wind -> FRD body forces (+L is up = -z_frd), then map back to AeroForge Z-up body (+x fwd, +y left, +z up)
    ca, sa = math.cos(alpha), math.sin(alpha)
    lift = qbar * s * cl
    drag = qbar * s * cd
    side_frd = qbar * s * cy

    fx = thrust_n - drag * ca + lift * sa
    fz_frd = -drag * sa - lift * ca
    mx_frd = qbar * s * b * c_roll
    my_frd = qbar * s * c * c_pitch
    mz_frd = qbar * s * b * c_yaw

    forces = np.array([fx, -side_frd, -fz_frd], dtype=float)
    moments = np.array([mx_frd, -my_frd, -mz_frd], dtype=float)
    return forces, moments, {"airspeed_m_s": airspeed, "alpha_deg": math.degrees(alpha), "beta_deg": math.degrees(beta), "cl": cl, "cd": cd}


def simulate_6dof_fixed_wing(
    *,
    mass_kg: float = 2.4,
    inertia_diag_kg_m2: tuple[float, float, float] = (0.08, 0.11, 0.17),
    aero: FixedWingAeroDerivatives | None = None,
    initial_airspeed_m_s: float = 18.0,
    initial_altitude_m: float = 40.0,
    aileron_rad: float = 0.0,
    elevator_rad: float = -0.02,
    rudder_rad: float = 0.0,
    thrust_n: float = 3.2,
    duration_s: float = 1.5,
    dt_s: float = 0.01,
) -> dict[str, Any]:
    """Integrate full 13-state 6-DoF rigid-body fixed-wing dynamics using RK4 and ISA atmosphere."""
    aero = aero or FixedWingAeroDerivatives(wing_area_m2=0.40, wingspan_m=1.8, mean_chord_m=0.22)
    body = RigidBody(mass_kg=mass_kg, inertia_about_cog=np.diag(inertia_diag_kg_m2))
    state = make_state(
        r_world=np.array([0.0, 0.0, initial_altitude_m], dtype=float),
        v_world=np.array([initial_airspeed_m_s, 0.0, 0.0], dtype=float),
        q_bw=np.array([1.0, 0.0, 0.0, 0.0], dtype=float),
        omega_body=np.zeros(3, dtype=float),
    )
    controls = {"elevator_rad": elevator_rad, "aileron_rad": aileron_rad, "rudder_rad": rudder_rad, "thrust_n": thrust_n}
    steps = max(1, math.ceil(duration_s / dt_s))
    states = [state.copy()]
    times = [0.0]

    for idx in range(steps):
        atm = isa_atmosphere_1976(float(state[2]))

        def _rhs(_t: float, x: np.ndarray) -> np.ndarray:
            _, v_w, q, om = unpack_state(x)
            v_b = rotate(conjugate(q), v_w)
            f_b, t_b, _ = compute_fixed_wing_wrench_body(aero, vel_body_m_s=v_b, omega_body_rad_s=om, rho_kg_m3=atm.density_kg_m3, controls=controls)
            return body.derivs(x, f_b, t_b, gravity=True)

        state = rk4_step(_rhs, idx * dt_s, state, dt_s)
        state[6:10] = normalize(state[6:10])
        times.append(round((idx + 1) * dt_s, 6))
        states.append(state.copy())

    arr = np.vstack(states)
    return {
        "schema_version": "1.0",
        "model": "6dof_jsbsim_stability_derivatives",
        "status": "completed",
        "final_position_m": arr[-1, 0:3].tolist(),
        "final_quaternion_wxyz": arr[-1, 6:10].tolist(),
        "final_velocity_m_s": arr[-1, 3:6].tolist(),
        "times_s": times,
        "physical_validation_status": "UNVALIDATED",
    }
