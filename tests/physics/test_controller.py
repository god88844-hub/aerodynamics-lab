"""M3 acceptance tests: cascaded controller stability, hover hold, disturbance
rejection, and the spec's checkpoint (5° roll command held within ±0.1°).

Spec acceptance (Milestone 3): "The quadcopter can hold a stable hover.
Introducing a small disturbance (force or torque) results in controller
corrections that restore stability. Log any oscillations — if persistent,
refine control gains."
"""

from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign
from physics.controller.attitude import ControlGains, ControlTargets, QuadcopterController
from physics.controller.mixer import Mixer
from physics.controller.simulation import Disturbance, run_controlled_simulation
from physics.dynamics.design_adapter import build_multirotor
from physics.dynamics.quaternion import from_axis_angle, rotation_matrix

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_2KG = REPO_ROOT / "data" / "designs" / "quad_example_2kg.json"
DESIGN_MN = REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def euler_deg(state) -> tuple[float, float, float]:
    R = rotation_matrix(state[6:10])
    roll = np.degrees(np.arctan2(R[2, 1], R[2, 2]))
    pitch = np.degrees(np.arcsin(np.clip(-R[2, 0], -1, 1)))
    yaw = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    return roll, pitch, yaw


@pytest.fixture(scope="module")
def quad_2kg():
    design = DroneDesign.model_validate_json(DESIGN_2KG.read_text(encoding="utf-8"))
    plant, _ = build_multirotor(design)
    return plant, QuadcopterController(plant)


@pytest.fixture(scope="module")
def quad_mn():
    design = DroneDesign.model_validate_json(DESIGN_MN.read_text(encoding="utf-8"))
    plant, _ = build_multirotor(design)
    return plant, QuadcopterController(plant)


def tail(res, seconds=2.0):
    """States over the last `seconds` of telemetry."""
    t0 = res.times[-1] - seconds
    mask = res.times >= t0
    return res.states[mask]


# ------------------------------------------------------------------ hover


def test_hover_hold_stable_no_persistent_oscillation(quad_2kg):
    plant, ctrl = quad_2kg
    res = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=1.0, position_xy=(0.0, 0.0)),
        duration_s=8.0,
    )
    tail_states = tail(res, 2.0)
    z = tail_states[:, 2]
    roll, pitch, _ = np.array([euler_deg(s) for s in tail_states]).T
    assert np.abs(z - 1.0).max() < 0.05          # holds 1 m
    assert float(np.std(z)) < 0.01               # no persistent oscillation
    assert np.abs(roll).max() < 1.0 and np.abs(pitch).max() < 1.0
    assert np.abs(tail_states[:, 0]).max() < 0.05
    assert np.abs(tail_states[:, 1]).max() < 0.05


def test_altitude_step_reaches_target(quad_2kg):
    plant, ctrl = quad_2kg
    res = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=2.0, position_xy=(0.0, 0.0)),
        duration_s=10.0,
    )
    tail_states = tail(res, 1.5)
    assert np.abs(tail_states[:, 2] - 2.0).max() < 0.05


# ---------------------------------------------------------- disturbances


def test_torque_disturbance_rejected(quad_2kg):
    plant, ctrl = quad_2kg
    res = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=1.0, position_xy=(0.0, 0.0)),
        duration_s=10.0,
        disturbances=[Disturbance(t_start=2.0, t_end=2.2, torque_body=np.array([0.05, 0.0, 0.0]))],
    )
    rolls = np.array([euler_deg(s)[0] for s in res.states])
    during = rolls[(res.times >= 2.0) & (res.times <= 2.6)]
    after = rolls[res.times >= 5.0]
    assert np.abs(during).max() > 0.2            # it visibly responds
    assert np.abs(after).max() < 0.5             # and returns to level
    z_after = res.states[res.times >= 6.0][:, 2]
    assert np.abs(z_after - 1.0).max() < 0.05    # altitude hold maintained


def test_force_disturbance_position_recovery(quad_2kg):
    plant, ctrl = quad_2kg
    res = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=1.0, position_xy=(0.0, 0.0)),
        duration_s=10.0,
        disturbances=[Disturbance(t_start=2.0, t_end=2.5, force_world=np.array([2.0, 0.0, 0.0]))],
    )
    x = res.states[:, 0]
    moved = np.abs(x[(res.times >= 2.0) & (res.times <= 4.0)]).max()
    final = np.abs(x[res.times >= 8.0]).max()
    vx_final = np.abs(res.states[res.times >= 8.0][:, 3]).max()
    assert moved > 0.02                          # it was pushed
    assert final < 0.05                          # position hold recovers
    assert vx_final < 0.05


# ------------------------------------------------- checkpoint: 5° roll


def test_roll_command_5deg_held_within_0p1deg(quad_2kg):
    """Spec checkpoint (Prompt 5): 5° roll command achieved and held within
    ±0.1° after the transient, returning to level when released."""
    plant, ctrl = quad_2kg
    res = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=1.0, roll_deg=5.0),
        duration_s=6.0,
    )
    rolls = np.array([euler_deg(s)[0] for s in res.states])
    hold = rolls[res.times >= 4.0]
    assert abs(float(np.mean(hold)) - 5.0) < 0.1
    assert float(np.std(hold)) < 0.05            # held, not oscillating

    res2 = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=1.0, roll_deg=0.0),
        duration_s=6.0,
    )
    rolls2 = np.array([euler_deg(s)[0] for s in res2.states])
    assert np.abs(rolls2[res2.times >= 4.0]).max() < 0.1


def test_pitch_command_held(quad_2kg):
    plant, ctrl = quad_2kg
    res = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=1.0, pitch_deg=-4.0),
        duration_s=6.0,
    )
    pitches = np.array([euler_deg(s)[1] for s in res.states])
    hold = pitches[res.times >= 4.0]
    assert abs(float(np.mean(hold)) - (-4.0)) < 0.1


def test_yaw_command_30deg(quad_mn):
    """Yaw authority requires rotor reaction torque (k>0) — validated on the
    MN3508 design whose k is derived from bench data (flagged estimate)."""
    plant, ctrl = quad_mn
    res = run_controlled_simulation(
        plant, ctrl, ControlTargets(altitude_m=1.0, yaw_deg=30.0, position_xy=(0.0, 0.0)),
        duration_s=10.0,
    )
    yaws = np.array([euler_deg(s)[2] for s in res.states])
    hold = yaws[res.times >= 8.0]
    assert abs(float(np.mean(hold)) - 30.0) < 1.0


# ------------------------------------------------------------------ mixer


def test_mixer_reconstructs_wrench(quad_mn):
    """Full wrench reconstruction needs yaw authority (k>0) — MN3508 design."""
    plant, _ = quad_mn
    mixer = Mixer(plant)
    thrusts, status = mixer.mix(10.0, np.array([0.2, -0.1, 0.05]))
    assert not any(status.values())
    state = np.array([0, 0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0])
    f_body, t_body = plant.net_force_torque(state, thrusts)
    assert f_body[2] == pytest.approx(10.0, abs=1e-9)
    assert t_body[0] == pytest.approx(0.2, abs=1e-6)
    assert t_body[1] == pytest.approx(-0.1, abs=1e-6)
    assert t_body[2] == pytest.approx(0.05, abs=1e-6)


def test_mixer_clips_negative_demands(quad_2kg):
    plant, _ = quad_2kg
    mixer = Mixer(plant)
    # Tiny total thrust with a large torque demand forces negative solutions.
    thrusts, status = mixer.mix(0.1, np.array([5.0, 0.0, 0.0]))
    assert status["clipped_negative"]
    assert np.all(thrusts >= 0.0)


def test_mixer_reports_saturation():
    design = DroneDesign.model_validate_json(DESIGN_2KG.read_text(encoding="utf-8"))
    plant, _ = build_multirotor(design)
    mixer = Mixer(plant, max_thrust_per_rotor_n=5.0)
    thrusts, status = mixer.mix(30.0, np.zeros(3))
    assert status["saturated_max"]
    assert status["collective_residual"]
    assert np.all(thrusts <= 5.0 + 1e-9)


def test_mixer_includes_capped_rotors_in_the_wrench_fit(quad_2kg):
    plant, _ = quad_2kg
    mixer = Mixer(plant, max_thrust_per_rotor_n=5.0)
    arm_y = float(mixer.matrix[1, 0])
    assert arm_y > 0
    total_thrust, roll_torque = 15.0, 2.0
    thrusts, status = mixer.mix(total_thrust, np.array([roll_torque, 0.0, 0.0]))
    # The positive-Y pair reaches the ceiling. The negative-Y pair solves
    # the remaining collective and roll errors in one scalar objective.
    remaining = (total_thrust - 10.0 + arm_y * (arm_y * 10.0 - roll_torque)) / (1 + arm_y**2)
    assert thrusts[mixer.matrix[1] > 0] == pytest.approx([5.0, 5.0])
    assert thrusts[mixer.matrix[1] < 0] == pytest.approx([remaining / 2, remaining / 2])
    assert status["saturated_max"] and status["torque_residual"]


def test_controller_allocation_counts_reset_for_a_new_run(quad_2kg):
    plant, _ = quad_2kg
    controller = QuadcopterController(plant, mixer=Mixer(plant, max_thrust_per_rotor_n=5.0))
    for _ in range(2):
        result = run_controlled_simulation(plant, controller, ControlTargets(altitude_m=1.0), duration_s=0.04)
        assert float(result.thrusts.max()) <= 5.0
        assert controller.allocation_counts["saturated_max"] == len(result.times)
        assert controller.allocation_counts["collective_residual"] == len(result.times)


def test_controller_gains_derived_from_plant(quad_2kg, quad_mn):
    """Rate gains must scale with the assembled inertia (2 kg vs 3.7 kg quads)."""
    plant_2kg, ctrl_2kg = quad_2kg
    plant_mn, ctrl_mn = quad_mn
    assert ctrl_mn.gains.kp_rate_roll == pytest.approx(
        plant_mn.body.inertia_about_cog[0, 0] / 0.05, rel=1e-9
    )
    assert ctrl_mn.gains.kp_rate_roll > ctrl_2kg.gains.kp_rate_roll


def test_euler_extraction_matches_axis_angle(quad_2kg):
    from physics.dynamics.quaternion import from_axis_angle

    q = from_axis_angle([1.0, 0.0, 0.0], np.radians(30.0))
    R = rotation_matrix(q)
    ctrl = quad_2kg[1]
    roll, pitch, yaw = ctrl._euler_zyx(R)
    assert np.degrees(roll) == pytest.approx(30.0, abs=1e-9)
    assert abs(np.degrees(pitch)) < 1e-9
    assert abs(np.degrees(yaw)) < 1e-9
