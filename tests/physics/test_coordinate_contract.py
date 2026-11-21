"""Analytical verification of documented frame boundaries; no physics changes.

Godot tests here verify conversion mathematics, not a new rendered end-to-end claim.
The existing desktop smoke separately exercises the rendered application path.
"""
import numpy as np
import pytest

from physics.dynamics.quaternion import conjugate, multiply, normalize, rotate, rotation_matrix

NED_TO_ENU = np.array([[0., 1., 0.], [1., 0., 0.], [0., 0., -1.]])
FRD_TO_FLU = np.diag([1., -1., -1.])
ENGINEERING_TO_GODOT = np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])


@pytest.mark.parametrize("basis", [NED_TO_ENU, FRD_TO_FLU, ENGINEERING_TO_GODOT])
def test_frame_roundtrip_preserves_handedness_norm_and_cross_product(basis):
    a, b = np.array([2., -3., 5.]), np.array([-7., 11., 13.])
    np.testing.assert_allclose(basis.T @ basis, np.eye(3), atol=1e-14)
    assert np.linalg.det(basis) == pytest.approx(1.)
    np.testing.assert_allclose(basis.T @ (basis @ a), a, atol=1e-14)
    np.testing.assert_allclose(np.cross(basis @ a, basis @ b), basis @ np.cross(a, b))
    assert np.linalg.norm(basis @ a) == pytest.approx(np.linalg.norm(a))


def test_source_gravity_and_body_axis_signs():
    np.testing.assert_allclose(NED_TO_ENU @ [0., 0., 9.80665], [0., 0., -9.80665])
    np.testing.assert_allclose(FRD_TO_FLU @ [1., 2., 3.], [1., -2., -3.])
    np.testing.assert_allclose(ENGINEERING_TO_GODOT @ [1., 2., 3.], [1., 3., -2.])


def test_hamilton_godot_basis_conjugation_and_roundtrip():
    rng = np.random.default_rng(314159)
    s = ENGINEERING_TO_GODOT
    for _ in range(40):
        q = normalize(rng.normal(size=4))
        v = rng.normal(size=3)
        # Godot stores xyzw: (x,z,-y,w); convert back to Hamilton for verification.
        godot_xyzw = np.array([q[1], q[3], -q[2], q[0]])
        qg = godot_xyzw[[3, 0, 1, 2]]
        np.testing.assert_allclose(rotation_matrix(qg), s @ rotation_matrix(q) @ s.T, atol=1e-14)
        np.testing.assert_allclose(rotate(qg, s @ v), s @ rotate(q, v), atol=1e-14)
        restored = np.r_[qg[0], s.T @ qg[1:]]
        np.testing.assert_allclose(restored, q, atol=1e-14)
        np.testing.assert_allclose(rotate(conjugate(q), rotate(q, v)), v, atol=1e-14)


def test_ned_frd_orientation_requires_both_basis_changes():
    q = normalize([0.7, 0.2, -0.3, 0.6])
    body_frd = np.array([2., 3., -5.])
    r_new = NED_TO_ENU @ rotation_matrix(q) @ FRD_TO_FLU.T
    np.testing.assert_allclose(r_new @ (FRD_TO_FLU @ body_frd), NED_TO_ENU @ rotate(q, body_frd))
    p = normalize([0.4, -0.2, 0.8, 0.1])
    np.testing.assert_allclose(rotate(multiply(q, p), body_frd), rotate(q, rotate(p, body_frd)))
