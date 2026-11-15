"""Verification of quaternion utilities against analytical rotation cases."""

import numpy as np
import pytest

from physics.dynamics.quaternion import (
    conjugate,
    from_axis_angle,
    kinematics_derivative,
    multiply,
    normalize,
    rotation_matrix,
    rotate,
)
from physics.integration.rk4 import integrate_fixed

X_HAT = np.array([1.0, 0.0, 0.0])
Y_HAT = np.array([0.0, 1.0, 0.0])


def test_rotate_x_by_90deg_about_z_gives_y():
    q = from_axis_angle([0, 0, 1], np.pi / 2)
    assert np.allclose(rotate(q, X_HAT), Y_HAT, atol=1e-12)


def test_rotation_composition_90z_twice_is_180z():
    q90 = from_axis_angle([0, 0, 1], np.pi / 2)
    q180 = multiply(q90, q90)
    assert np.allclose(rotate(q180, X_HAT), -X_HAT, atol=1e-12)


def test_axis_angle_of_normalized_axis_matches():
    # Unnormalized axis input must give the same result as the unit axis.
    q1 = from_axis_angle([0, 0, 2.0], 0.7)
    q2 = from_axis_angle([0, 0, 1.0], 0.7)
    assert np.allclose(q1, q2, atol=1e-15)


def test_rotate_then_inverse_is_identity():
    q = from_axis_angle([0.3, -0.5, 1.1], 1.234)
    v = np.array([0.2, -0.7, 3.1])
    assert np.allclose(rotate(conjugate(q), rotate(q, v)), v, atol=1e-12)


def test_rotation_matrix_matches_quaternion_rotation():
    q = from_axis_angle([0.2, 0.9, -0.4], 0.8)
    v = np.array([1.0, -2.0, 0.5])
    assert np.allclose(rotation_matrix(q) @ v, rotate(q, v), atol=1e-12)


def test_kinematics_constant_spin_integrates_to_expected_angle():
    """Integrating dq/dt = 0.5 q⊗(0,ω) with ω=(0,0,π/2) for 1 s must rotate
    x-hat onto y-hat (90° about z)."""
    omega = np.array([0.0, 0.0, np.pi / 2])
    q0 = normalize(np.array([1.0, 0.0, 0.0, 0.0]))
    times, states = integrate_fixed(
        lambda t, q: kinematics_derivative(q, omega),
        q0,
        0.0,
        1.0,
        1e-4,
        post_step=normalize,
    )
    q_final = states[-1]
    assert np.allclose(rotate(q_final, X_HAT), Y_HAT, atol=1e-8)
    assert abs(np.linalg.norm(q_final) - 1.0) < 1e-12


def test_normalize_zero_quaternion_raises():
    with pytest.raises(ValueError):
        normalize(np.zeros(4))


def test_axis_angle_zero_axis_raises():
    with pytest.raises(ValueError):
        from_axis_angle([0, 0, 0], 1.0)
