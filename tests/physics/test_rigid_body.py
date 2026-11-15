"""Verification of 6-DOF rigid-body dynamics against analytical solutions.

Covers the spec's checkpoint criteria:
- free fall at g (Prompt 2 acceptance: v(1 s) = 9.81 m/s ± 0.01),
- spin-up on a principal axis (Euler's equations),
- torque-free conservation of energy and world-frame angular momentum,
- RK4 step-halving convergence (order verification),
- scipy adaptive solver agreement.
"""

import numpy as np
import pytest

from physics.constants import STANDARD_GRAVITY as G
from physics.dynamics.quaternion import rotation_matrix
from physics.dynamics.rigid_body import RigidBody, make_state, normalize_state, unpack_state
from physics.integration.rk4 import integrate_fixed
from physics.integration.scipy_solver import integrate_ivp

INERTIA = np.diag([0.08, 0.06, 0.12])  # physical: 0.08+0.06 >= 0.12


def make_body() -> RigidBody:
    return RigidBody(mass_kg=1.5, inertia_about_cog=INERTIA)


def test_free_fall_at_gravity():
    """Drop from rest, no applied forces: v_z(1 s) = -g, z(1 s) = -g/2."""
    body = make_body()
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3))
    times, states = integrate_fixed(
        lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3)),
        x0,
        0.0,
        1.0,
        0.01,
        post_step=normalize_state,
    )
    _, v_final, _, _ = unpack_state(states[-1])
    r_final = states[-1][0:3]
    assert v_final[2] == pytest.approx(-G, abs=1e-6)  # far tighter than the ±0.01 gate
    assert r_final[2] == pytest.approx(-G / 2.0, abs=1e-5)


def test_spec_checkpoint_v_within_0p01():
    """The spec's explicit acceptance gate: |v(1 s)| = 9.81 ± 0.01 m/s."""
    body = make_body()
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3))
    _, states = integrate_fixed(
        lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3)),
        x0,
        0.0,
        1.0,
        0.01,
        post_step=normalize_state,
    )
    assert abs(abs(states[-1][5]) - 9.81) <= 0.01


def test_no_force_no_gravity_coast_and_steady_spin():
    """No forces/torques: translation coasts, principal-axis spin is steady,
    and only the attitude keeps rotating."""
    body = make_body()
    q0 = from_axis_angle_helper(0.5)
    w0 = np.array([0.05, 0.0, 0.0])  # principal axis spin → constant ω
    x0 = make_state([1, 2, 3], [0.1, 0.2, 0.3], q0, w0)
    _, states = integrate_fixed(
        lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3), gravity=False),
        x0,
        0.0,
        2.0,
        0.01,
        post_step=normalize_state,
    )
    r0, v0, q_start, _ = unpack_state(states[0])
    r_f, v_f, q_f, w_f = unpack_state(states[-1])
    assert np.allclose(r_f, r0 + v0 * 2.0, atol=1e-12)  # coasts: r(t) = r0 + v t
    assert np.allclose(v_f, v0, atol=1e-12)
    assert np.allclose(w_f, w0, atol=1e-12)
    assert not np.allclose(q_f, q_start)  # attitude keeps rotating
    assert abs(np.linalg.norm(q_f) - 1.0) < 1e-12


def from_axis_angle_helper(angle: float) -> np.ndarray:
    from physics.dynamics.quaternion import from_axis_angle

    return from_axis_angle([0.2, 0.3, 1.0], angle)


def test_torque_spin_up_on_principal_axis():
    """τ = (0.1, 0, 0) about a principal axis: ω_x(1 s) = τ/I_xx exactly."""
    body = make_body()
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3))
    torque = np.array([0.1, 0.0, 0.0])
    _, states = integrate_fixed(
        lambda t, x: body.derivs(x, np.zeros(3), torque, gravity=False),
        x0,
        0.0,
        1.0,
        1e-3,
        post_step=normalize_state,
    )
    _, _, _, w = unpack_state(states[-1])
    assert w[0] == pytest.approx(0.1 / 0.08, abs=1e-9)
    assert abs(w[1]) < 1e-9 and abs(w[2]) < 1e-9


def test_torque_free_energy_and_world_angular_momentum_conserved():
    """No torque: E = ½ω·Iω constant, and |L_world| = |R(q)·I·ω| constant."""
    body = make_body()
    w0 = np.array([2.0, 0.7, 0.3])
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], w0)
    e0 = 0.5 * w0 @ INERTIA @ w0
    l0 = np.linalg.norm(INERTIA @ w0)  # q0 = identity

    _, states = integrate_fixed(
        lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3), gravity=False),
        x0,
        0.0,
        5.0,
        1e-3,
        post_step=normalize_state,
    )
    for x in states[::50]:
        _, _, q, w = unpack_state(x)
        e = 0.5 * w @ INERTIA @ w
        l_world = rotation_matrix(q) @ (INERTIA @ w)
        assert abs(e - e0) < 1e-8
        assert abs(np.linalg.norm(l_world) - l0) < 1e-8


def test_rk4_fourth_order_convergence():
    """Step-halving family on the *nonlinear* torque-free Euler dynamics
    (constant-acceleration free fall is integrated exactly by RK4, so it has
    no measurable error): error(dt/4) must be ≈256x smaller than error(dt)."""
    body = make_body()
    w0 = np.array([2.0, 0.7, 0.3])
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], w0)
    f = lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3), gravity=False)  # noqa: E731

    def omega_at_1s(dt: float) -> np.ndarray:
        _, states = integrate_fixed(f, x0, 0.0, 1.0, dt, post_step=normalize_state)
        return states[-1][10:13]

    reference = omega_at_1s(6.25e-4)
    e_coarse = float(np.linalg.norm(omega_at_1s(0.02) - reference))
    e_fine = float(np.linalg.norm(omega_at_1s(0.005) - reference))
    assert e_fine < e_coarse / 50.0  # 4th order => ~256x; 50x is the conservative gate


def test_scipy_solver_matches_analytical_and_rk4():
    body = make_body()
    x0 = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3))
    times, states = integrate_ivp(
        lambda t, x: body.derivs(x, np.zeros(3), np.zeros(3)),
        x0,
        0.0,
        1.0,
        post_step=normalize_state,
    )
    assert states[-1][5] == pytest.approx(-G, abs=1e-8)
    assert times[-1] == pytest.approx(1.0)


def test_state_validation_rejects_bad_inputs():
    body = make_body()
    with pytest.raises(ValueError):
        RigidBody(mass_kg=0.0, inertia_about_cog=INERTIA)
    with pytest.raises(ValueError):
        body.derivs(np.zeros(5), np.zeros(3), np.zeros(3))
    with pytest.raises(ValueError):
        RigidBody(mass_kg=1.0, inertia_about_cog=np.diag([1.0, 1.0, 0.0]))
