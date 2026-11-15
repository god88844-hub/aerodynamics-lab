"""Verification of mass-property assembly against known parallel-axis cases."""

import numpy as np
import pytest

from geometry.primitives import box_inertia
from physics.dynamics.mass_properties import Part, assemble_mass_properties


def test_two_point_masses_cog_and_inertia():
    """Two 1 kg masses at x = ±0.5 m: CoG at origin, Iyy = Izz = 0.5 kg·m²,
    Ixx = 0 (idealized dumbbell — rotation about the rod axis is free)."""
    parts = [
        Part(name="m1", mass_kg=1.0, position_m=[0.5, 0, 0]),
        Part(name="m2", mass_kg=1.0, position_m=[-0.5, 0, 0]),
    ]
    props = assemble_mass_properties(parts)
    assert props.mass_kg == 2.0
    assert np.allclose(props.cog_m, 0.0)
    assert np.allclose(props.inertia_about_cog, np.diag([0.0, 0.5, 0.5]), atol=1e-12)


def test_box_inertia_known_value():
    inertia = box_inertia(1.2, 0.4, 0.4, 0.05)
    expected_xx = 1.2 / 12.0 * (0.4**2 + 0.05**2)  # 0.01625
    expected_zz = 1.2 / 12.0 * (0.4**2 + 0.4**2)  # 0.032
    assert np.allclose(inertia, np.diag([expected_xx, expected_xx, expected_zz]))


def test_single_part_inertia_at_own_cog():
    """When the assembly CoG coincides with the part CoG, no transfer term applies."""
    own = box_inertia(2.0, 0.3, 0.3, 0.3)
    props = assemble_mass_properties(
        [Part(name="b", mass_kg=2.0, position_m=[0.1, 0.2, 0.3], inertia_about_own_cog=own)]
    )
    assert np.allclose(props.inertia_about_cog, own, atol=1e-14)
    assert np.allclose(props.cog_m, [0.1, 0.2, 0.3])


def test_parallel_axis_transfer_in_multi_part_assembly():
    """A point mass + displaced box: hand-computed parallel-axis terms must match."""
    mass_box, side = 2.0, 0.3
    m_point = 3.0
    d_box = np.array([0.3, -0.2, 0.1])
    own = box_inertia(mass_box, side, side, side)
    parts = [
        Part(name="point", mass_kg=m_point, position_m=[0, 0, 0]),
        Part(name="box", mass_kg=mass_box, position_m=d_box, inertia_about_own_cog=own),
    ]
    props = assemble_mass_properties(parts)

    total = mass_box + m_point
    cog = mass_box * d_box / total
    assert np.allclose(props.cog_m, cog, atol=1e-14)

    d_box_cg = d_box - cog
    expected = (
        own
        + mass_box * (np.dot(d_box_cg, d_box_cg) * np.eye(3) - np.outer(d_box_cg, d_box_cg))
        + m_point * (np.dot(cog, cog) * np.eye(3) - np.outer(cog, cog))
    )
    assert np.allclose(props.inertia_about_cog, expected, atol=1e-12)


def test_example_quad_inertia_zz_matches_hand_calculation():
    """Example 2 kg quad: Izz = frame 0.032 + 4 motors 0.1 kg at 0.25√2 arm
    (0.05) + battery on-axis (0) = 0.082 kg·m²."""
    from aeroforge_schemas.design import DroneDesign
    from physics.dynamics.design_adapter import build_multirotor
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "designs"
        / "quad_example_2kg.json"
    )
    design = DroneDesign.model_validate_json(path.read_text(encoding="utf-8"))
    _, props = build_multirotor(design)
    assert props.mass_kg == pytest.approx(2.0, abs=1e-12)
    assert np.allclose(props.cog_m, 0.0, atol=1e-12)
    assert props.inertia_about_cog[2, 2] == pytest.approx(0.082, rel=1e-9)


def test_triangle_inequality_violation_raises():
    """A part with impossible principal moments (0.5, 0.5, 5) must fail closed."""
    parts = [
        Part(
            name="impossible",
            mass_kg=1.0,
            position_m=[0, 0, 0],
            inertia_about_own_cog=np.diag([0.5, 0.5, 5.0]),
        )
    ]
    with pytest.raises(ValueError, match="triangle"):
        assemble_mass_properties(parts)


def test_negative_inertia_eigenvalue_raises():
    parts = [
        Part(
            name="negative",
            mass_kg=1.0,
            position_m=[0, 0, 0],
            inertia_about_own_cog=np.diag([0.1, 0.1, -0.1]),
        )
    ]
    with pytest.raises(ValueError, match="non-physical"):
        assemble_mass_properties(parts)


def test_zero_total_mass_raises():
    with pytest.raises(ValueError):
        assemble_mass_properties(
            [Part(name="a", mass_kg=0.0, position_m=[0, 0, 0])]
        )


def test_asymmetric_inertia_tensor_raises():
    with pytest.raises(ValueError, match="symmetric"):
        Part(
            name="skew",
            mass_kg=1.0,
            position_m=[0, 0, 0],
            inertia_about_own_cog=np.array([[0.1, 0.01, 0], [0, 0.1, 0], [0, 0, 0.1]]),
        )
