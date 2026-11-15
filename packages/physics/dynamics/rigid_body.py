"""6-DOF rigid-body dynamics under gravity with body-frame force/torque input.

State layout (13): ``[r_w(3), v_w(3), q_bw(4), omega_b(3)]``
- World frame W: +z points UP (ENU-style); gravity acts along -z.
- ``q_bw`` rotates body-frame vectors into the world frame.
- ``omega_b`` is the angular velocity, expressed in the body frame.

Assumptions (recorded per docs/validation_strategy.md):
- Flat, non-rotating Earth; constant standard gravity (no altitude variation).
- Mass properties constant during flight (no fuel/consumable burn).
- Rigid body: no structural flexure.

Verified in tests/physics/test_rigid_body.py: free fall at g, spin-up on a
principal axis, torque-free conservation of energy and world-frame angular
momentum, and RK4 step-halving convergence order.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from physics.constants import STANDARD_GRAVITY
from physics.dynamics.quaternion import kinematics_derivative, normalize, rotate

STATE_SIZE = 13


@dataclass(frozen=True)
class RigidBody:
    """Constant-mass rigid body with body-frame inertia about its CoG."""

    mass_kg: float
    inertia_about_cog: np.ndarray  # (3,3), body frame at CoG

    def __post_init__(self) -> None:
        inertia = np.asarray(self.inertia_about_cog, dtype=float)
        object.__setattr__(self, "inertia_about_cog", inertia)
        if not np.isfinite(self.mass_kg) or self.mass_kg <= 0.0:
            raise ValueError("mass must be finite and > 0")
        if inertia.shape != (3, 3) or not np.all(np.isfinite(inertia)):
            raise ValueError("inertia must be a finite 3x3 matrix")
        if not np.allclose(inertia, inertia.T):
            raise ValueError("inertia tensor must be symmetric")
        if np.any(np.linalg.eigvalsh(inertia) <= 0.0):
            raise ValueError("inertia tensor must be positive definite")

    def derivs(
        self,
        state: np.ndarray,
        force_body: np.ndarray,
        torque_body: np.ndarray,
        gravity: bool = True,
    ) -> np.ndarray:
        """Time derivative of the 13-state vector.

        ``force_body`` and ``torque_body`` are the *applied* (non-gravitational)
        resultant in the body frame; gravity is added internally when enabled.
        """
        r, v, q, w = unpack_state(state)
        f_world = rotate(q, np.asarray(force_body, dtype=float))
        if gravity:
            f_world = f_world + self.mass_kg * STANDARD_GRAVITY * np.array([0.0, 0.0, -1.0])
        dv = f_world / self.mass_kg
        dq = kinematics_derivative(q, w)
        iw = self.inertia_about_cog @ w
        dw = np.linalg.solve(self.inertia_about_cog, np.asarray(torque_body, dtype=float) - np.cross(w, iw))
        return np.concatenate([v, dv, dq, dw])


def unpack_state(state: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split the 13-state into (r_world, v_world, q_bw, omega_body)."""
    x = np.asarray(state, dtype=float)
    if x.shape != (STATE_SIZE,):
        raise ValueError(f"state must have shape ({STATE_SIZE},), got {x.shape}")
    return x[0:3], x[3:6], x[6:10], x[10:13]


def make_state(
    r_world: np.ndarray,
    v_world: np.ndarray,
    q_bw: np.ndarray,
    omega_body: np.ndarray,
) -> np.ndarray:
    """Build a 13-state from components; quaternion is normalized."""
    q = normalize(np.asarray(q_bw, dtype=float))
    return np.concatenate(
        [
            np.asarray(r_world, dtype=float),
            np.asarray(v_world, dtype=float),
            q,
            np.asarray(omega_body, dtype=float),
        ]
    )


def normalize_state(state: np.ndarray) -> np.ndarray:
    """Renormalize the quaternion component (call after each integration step)."""
    r, v, q, w = unpack_state(state)
    return make_state(r, v, q, w)
