"""M1 acceptance tests: hover equilibrium, trim vs mass, free fall through the
full multirotor plant, and fail-closed trim checks.

Spec acceptance (Milestone 1): "A Python simulation script can load a simple
drone config (4 identical motors, given thrust curve), simulate hover, and
output net force ≈ 0. Adding or removing mass changes required thrust
correctly." (The sourced thrust curve arrives in M2; here actuators are ideal
and that caveat is asserted as part of the contract.)
"""

from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign, PartInstance
from physics.constants import STANDARD_GRAVITY as G
from physics.dynamics.design_adapter import build_multirotor
from physics.dynamics.rigid_body import make_state, normalize_state, unpack_state
from physics.integration.rk4 import integrate_fixed

DESIGN_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "designs" / "quad_example_2kg.json"
)


@pytest.fixture(scope="module")
def design() -> DroneDesign:
    return DroneDesign.model_validate_json(DESIGN_PATH.read_text(encoding="utf-8"))


def simulate_hover(plant, thrusts, duration_s=2.0, dt_s=0.002):
    x0 = make_state(
        r_world=np.zeros(3),
        v_world=np.zeros(3),
        q_bw=np.array([1.0, 0.0, 0.0, 0.0]),
        omega_body=np.zeros(3),
    )
    return integrate_fixed(
        lambda t, x: plant.derivs(x, thrusts), x0, 0.0, duration_s, dt_s,
        post_step=normalize_state,
    )


def test_design_validates_and_masses_sum(design):
    assert design.name == "example_quad_2kg"
    assert len(design.rotors) == 4
    assert sum(p.mass_kg for p in design.parts) == pytest.approx(2.0, abs=1e-12)


def test_hover_trim_equals_weight_per_rotor(design):
    plant, mass = build_multirotor(design)
    trim = plant.hover_trim()
    expected = mass.mass_kg * G / len(design.rotors)
    assert np.allclose(trim, expected, rtol=1e-12)
    assert np.sum(trim) == pytest.approx(mass.mass_kg * G, rel=1e-12)


def test_hover_simulation_stationary_net_force_zero(design):
    """M1 acceptance: net force ≈ 0 — the vehicle stays put at trim thrusts."""
    plant, mass = build_multirotor(design)
    trim = plant.hover_trim()
    times, states = simulate_hover(plant, trim, duration_s=2.0)

    r_final, v_final, q_final, _ = unpack_state(states[-1])
    assert np.linalg.norm(r_final) < 1e-6            # meters of drift over 2 s
    assert np.linalg.norm(v_final) < 1e-6            # m/s residual velocity
    assert np.allclose(q_final, [1, 0, 0, 0], atol=1e-9)  # stays level

    # Max |net acceleration| along the trajectory (world frame, incl. gravity).
    max_accel = max(
        float(np.linalg.norm(plant.derivs(x, trim)[3:6])) for x in states
    )
    assert max_accel < 1e-9                          # m/s² — net force ≈ 0


def test_added_mass_changes_required_thrust_correctly(design):
    """+0.3 kg payload must raise total trim thrust to (2.3 kg)·g exactly."""
    heavier = design.model_copy(deep=True)
    heavier.parts = heavier.parts + [
        PartInstance(name="payload", mass_kg=0.3, position_m=(0.0, 0.0, 0.0))
    ]
    plant, mass = build_multirotor(heavier)
    trim = plant.hover_trim()
    assert mass.mass_kg == pytest.approx(2.3, abs=1e-12)
    assert np.sum(trim) == pytest.approx(2.3 * G, rel=1e-12)
    assert np.allclose(trim, 2.3 * G / 4.0, rtol=1e-12)

    # And the heavier drone still hovers stationary at the new trim.
    _, states = simulate_hover(plant, trim, duration_s=2.0)
    assert np.linalg.norm(states[-1][0:3]) < 1e-6


def test_removed_mass_changes_required_thrust_correctly(design):
    lighter = design.model_copy(deep=True)
    lighter.parts = [p for p in lighter.parts if p.name != "battery"]
    plant, mass = build_multirotor(lighter)
    trim = plant.hover_trim()
    assert mass.mass_kg == pytest.approx(1.6, abs=1e-12)
    assert np.sum(trim) == pytest.approx(1.6 * G, rel=1e-12)


def test_cog_offset_trim_and_hover(design):
    """Battery moved to x=+0.06 m: CoG shifts, trim thrusts become unequal, and
    the analytic trim still produces a perfectly stationary hover."""
    shifted = design.model_copy(deep=True)
    for p in shifted.parts:
        if p.name == "battery":
            p.position_m = (0.06, 0.0, -0.02)
    plant, mass = build_multirotor(shifted)
    cog_x = mass.cog_m[0]
    assert cog_x == pytest.approx(0.4 * 0.06 / 2.0, rel=1e-9)  # 0.012 m

    trim = plant.hover_trim()
    assert np.sum(trim) == pytest.approx(mass.mass_kg * G, rel=1e-12)
    assert not np.allclose(trim, trim[0], rtol=1e-3)  # unequal per rotor

    _, states = simulate_hover(plant, trim, duration_s=2.0)
    r_final, v_final, q_final, w_final = unpack_state(states[-1])
    assert np.linalg.norm(r_final) < 1e-6
    assert np.linalg.norm(v_final) < 1e-6
    assert np.allclose(q_final, [1, 0, 0, 0], atol=1e-9)
    assert np.linalg.norm(w_final) < 1e-9


def test_free_fall_through_plant_matches_g(design):
    """Zero thrust (no drag model) through the full plant: falls exactly at g."""
    no_drag = design.model_copy(deep=True)
    no_drag.drag_cd_a_m2 = None
    plant, _ = build_multirotor(no_drag)
    _, states = simulate_hover(plant, np.zeros(4), duration_s=1.0, dt_s=0.01)
    assert states[-1][5] == pytest.approx(-G, abs=1e-6)


def test_reaction_torque_and_fail_closed_trim(design):
    """Rotor reaction torque enters τ_z; an all-same-spin quad cannot be
    yaw-trimmed and must fail closed."""
    k = 0.05  # N·m per N
    plant, _ = build_multirotor(design)
    plant.rotor_torque_per_thrust = k

    # Equal thrusts, all rotors counted: Σ(-spin_i·k·t) = 0 for alternating spins.
    _, t_body = plant.net_force_torque(
        make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3)),
        np.full(4, 1.0),
    )
    spins = [-1, 1, -1, 1]
    assert t_body[2] == pytest.approx(-k * sum(spins) * 1.0, abs=1e-12)  # == 0

    # All props spinning the same direction: yaw torque unavoidable -> no trim.
    same_spin = design.model_copy(deep=True)
    for r in same_spin.rotors:
        r.spin_direction = 1
    plant_same, _ = build_multirotor(same_spin)
    plant_same.rotor_torque_per_thrust = k
    with pytest.raises(ValueError, match="trim"):
        plant_same.hover_trim()


def test_thrust_validation_fail_closed(design):
    plant, _ = build_multirotor(design)
    state = make_state(np.zeros(3), np.zeros(3), [1, 0, 0, 0], np.zeros(3))
    with pytest.raises(ValueError, match=">= 0"):
        plant.net_force_torque(state, np.array([1.0, -1.0, 1.0, 1.0]))
    with pytest.raises(ValueError, match="thrust values"):
        plant.net_force_torque(state, np.array([1.0, 1.0, 1.0]))
