"""Quaternion utilities for 3D rotations.

Convention: quaternions are numpy arrays ``[w, x, y, z]`` with unit norm and
represent the rotation of body-frame vectors into the world frame (active
rotation): ``v_world = rotate(q_bw, v_body)``.

Verified against analytical cases in tests/physics/test_quaternion.py.
"""

from __future__ import annotations

import numpy as np

IDENTITY: np.ndarray = np.array([1.0, 0.0, 0.0, 0.0])


def normalize(q: np.ndarray) -> np.ndarray:
    """Normalize a quaternion with finite, nonzero norm."""
    q = np.asarray(q, dtype=float)
    n = float(np.linalg.norm(q))
    if n == 0.0:
        raise ValueError("cannot normalize zero quaternion")
    if not np.isfinite(n):
        raise ValueError("cannot normalize a non-finite quaternion norm")
    return q / n


def multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Hamilton product ``q1 ⊗ q2`` (apply q2 first, then q1)."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ]
    )


def conjugate(q: np.ndarray) -> np.ndarray:
    """Inverse rotation of a unit quaternion."""
    return np.array([q[0], -q[1], -q[2], -q[3]])


def rotate(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate vector ``v`` (body frame) into the world frame with unit ``q``."""
    qv = np.array([0.0, v[0], v[1], v[2]])
    return multiply(multiply(q, qv), conjugate(q))[1:]


def rotate_inverse(q: np.ndarray, v_world: np.ndarray) -> np.ndarray:
    """Rotate a world-frame vector into the body frame (inverse of rotate)."""
    return rotate(conjugate(q), v_world)


def from_axis_angle(axis: np.ndarray, angle: float) -> np.ndarray:
    """Unit quaternion for a rotation of ``angle`` rad about ``axis``."""
    axis = np.asarray(axis, dtype=float)
    n = float(np.linalg.norm(axis))
    if n == 0.0:
        raise ValueError("axis must be a non-zero vector")
    axis = axis / n
    half = angle / 2.0
    return np.array([np.cos(half), *(axis * np.sin(half))])


def rotation_matrix(q: np.ndarray) -> np.ndarray:
    """3x3 rotation matrix (body -> world) corresponding to unit quaternion ``q``."""
    w, x, y, z = normalize(q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def kinematics_derivative(q: np.ndarray, omega_body: np.ndarray) -> np.ndarray:
    """Quaternion kinematics: dq/dt = 0.5 * q ⊗ (0, ω_body).

    Valid for unit ``q`` with angular velocity expressed in the body frame.
    """
    omega_quat = np.array([0.0, omega_body[0], omega_body[1], omega_body[2]])
    return 0.5 * multiply(q, omega_quat)
