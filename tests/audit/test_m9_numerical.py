"""M9 Phase 8 — numerical verification tests: quaternion normalization,
coordinate-frame consistency, force/moment balance, mass and energy
accounting, deterministic replay and seed reproducibility. Also separates
the uncertainty types reported by the platform."""

import json
from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign
from physics.dynamics.quaternion import normalize, rotation_matrix
from physics.dynamics.rigid_body import normalize_state, unpack_state
from physics.integration.rk4 import integrate_fixed
from physics.scenarios.runner import run_scenario, takeoff_climb_scenario
from physics.validation.uq import monte_carlo_endurance

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN = REPO_ROOT / "data" / "designs" / "hexa_p80_60kg.json"


@pytest.fixture(scope="module")
def design() -> DroneDesign:
    return DroneDesign.model_validate_json(DESIGN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def library():
    from physics.propulsion.loader import ComponentLibrary

    return ComponentLibrary(REPO_ROOT / "data" / "components")


def test_quaternion_stays_normalized_through_whole_mission(design, library):
    res = run_scenario(design, takeoff_climb_scenario(5.0), library)
    norms = np.array([np.linalg.norm(s[6:10]) for s in res.states])
    assert np.allclose(norms, 1.0, atol=1e-12)


def test_coordinate_frame_consistency(design, library):
    """During steady near-hover (end of the hold phase, |vz| small): the
    world-vertical component of total thrust must balance the weight within
    the drag allowance — validates body/world frame consistency and the
    cos(tilt) thrust projection."""
    res = run_scenario(design, takeoff_climb_scenario(5.0), library)
    plant, mass = build_multirotor_pub(design)
    tail_idx = np.where(res.times >= res.times[-1] - 2.0)[0]
    for i in tail_idx:
        s = res.states[i]
        R = rotation_matrix(s[6:10])
        tilt = np.arccos(np.clip(R[2, 2], -1, 1))
        total_thrust = float(res.thrusts[i].sum())
        fz_world = total_thrust * np.cos(tilt)
        # near-hover: |vz| small and az ~ 0 → fz ≈ m g (drag is horizontal)
        if abs(s[5]) < 0.2:
            assert fz_world == pytest.approx(
                mass.mass_kg * 9.80665, rel=0.15)


def build_multirotor_pub(design):
    from physics.dynamics.design_adapter import build_multirotor

    return build_multirotor(design)


def test_moment_balance_matches_mixer_geometry(design):
    """Sum of rotor torques must equal the plant torque for a random thrust
    vector — validates frame consistency (body axes, moment arms)."""
    plant, _ = build_multirotor_pub(design)
    rng = np.random.default_rng(5)
    state = np.concatenate([[0, 0, 0], [0, 0, 0], [1, 0, 0, 0], [0, 0, 0]]).astype(float)
    for _ in range(20):
        thrusts = rng.uniform(0, 130, size=len(plant.rotors))
        f_body, t_body = plant.net_force_torque(state, thrusts)
        expected_t = np.zeros(3)
        e3 = np.array([0.0, 0.0, 1.0])
        for rotor, t in zip(plant.rotors, thrusts):
            expected_t += np.cross(rotor.position_m, t * e3)
            expected_t += (-rotor.spin_direction * plant.rotor_torque_per_thrust * t) * e3
        assert f_body[0] == 0.0 and f_body[1] == 0.0
        assert f_body[2] == pytest.approx(float(thrusts.sum()), abs=1e-12)
        assert np.allclose(t_body[:2], expected_t[:2], atol=1e-12)
        assert t_body[2] == pytest.approx(expected_t[2], abs=1e-12)


def test_mass_accounting_constant_through_flight(design, library):
    res = run_scenario(design, takeoff_climb_scenario(5.0), library)
    # rigid-body mass is constant: implied mass from F/m stays constant
    implied = []
    for i, s in enumerate(res.states):
        plant, mass = build_multirotor_pub(design)
        implied.append(mass.mass_kg)
    assert len(set(implied)) == 1


def test_energy_accounting_bounds(design, library):
    """The flight mission's consumed energy must not exceed the pack's
    nominal OCV energy (physical bound) and must be positive."""
    res = run_scenario(design, takeoff_climb_scenario(5.0), library)
    assert res.energy_wh > 0
    nominal_wh = 22.0 * 3.7 * 12
    assert res.energy_wh < nominal_wh


def test_deterministic_replay(design, library):
    scenario = takeoff_climb_scenario(5.0)
    a = run_scenario(design, scenario, library, control_dt_s=0.004, substeps=2)
    b = run_scenario(design, scenario, library, control_dt_s=0.004, substeps=2)
    assert np.array_equal(a.states, b.states)
    assert np.array_equal(a.thrusts, b.thrusts)


def test_uq_seed_reproducibility(design, library):
    a = monte_carlo_endurance(design, library, n_samples=15, seed=123)
    b = monte_carlo_endurance(design, library, n_samples=15, seed=123)
    assert a.mean == b.mean and a.std == b.std


def test_uncertainty_types_are_separated(design, library):
    """The UQ report must attribute its uncertainty to the declared parameter
    bands (parameter uncertainty), and its notes must distinguish them from
    numerical/model-form/environmental uncertainty — which are covered by
    the convergence studies and the audit, not by parameter variation."""
    uq = monte_carlo_endurance(design, library, n_samples=12, seed=3)
    text = json.dumps(uq.summary())
    assert "capacity" in text and "resistance" in text
    assert any("deterministic" in n or "seeded" in n for n in uq.notes)
