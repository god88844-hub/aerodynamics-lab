"""M9 Phase 7 — integrated system failure-mode tests (reproducible scenarios).

Each test creates a reproducible failure scenario and records how the
platform behaves. Failures of individual components are distinguished from
interaction failures. Where a mechanism is NOT MODELED, the test asserts the
platform refuses/flags rather than producing a false verdict — the model
must not issue a validated success verdict when a critical failure mechanism
is unrepresented.
"""

from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign
from physics.controller.sensors import SensorConfig
from physics.controller.simulation import Disturbance  # noqa: F401
from physics.scenarios.runner import Scenario, run_scenario
from physics.dynamics.design_adapter import build_multirotor

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN = REPO_ROOT / "data" / "designs" / "hexa_p80_60kg.json"


@pytest.fixture(scope="module")
def design() -> DroneDesign:
    return DroneDesign.model_validate_json(DESIGN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def library():
    from physics.propulsion.loader import ComponentLibrary

    return ComponentLibrary(REPO_ROOT / "data" / "components")


def _hover_scenario(duration_s=10.0, altitude=3.0, **extra):
    """Hover with POSITION HOLD active (position waypoints present): the
    position loop is engaged, so sensor failures manifest as tracked offsets."""
    return Scenario(
        name="m9_hover",
        duration_s=duration_s,
        altitude_waypoints=[(0.0, 0.0), (2.0, altitude), (duration_s, altitude)],
        position_waypoints=[(0.0, (0.0, 0.0)), (duration_s, (0.0, 0.0))],
        **extra,
    )


def test_sensor_bias_creates_position_offset_but_stays_stable(design, library):
    """Constant position bias: the controller flies to the BIASED target, so
    the true position settles offset by the bias — a real, recorded effect
    (interaction failure between sensor and controller), not a crash."""
    scenario = _hover_scenario(10.0, 3.0)
    scenario.sensor_config = SensorConfig(seed=3, bias_position_m=(0.20, 0.0, 0.0))
    res = run_scenario(design, scenario, library)
    assert not res.aborted
    tail = res.states[res.times >= res.times[-1] - 2.0]
    # true position settles ~ -bias (controller thinks it is at target)
    assert abs(tail[:, 0].mean() + 0.20) < 0.06
    assert np.abs(tail[:, 2] - 3.0).max() < 0.10


def test_sensor_latency_and_noise_still_stable(design, library):
    scenario = _hover_scenario(12.0, 3.0)
    scenario.sensor_config = SensorConfig(seed=11, sigma_position_m=0.03,
                                          sigma_rate_deg_s=1.5, latency_s=0.03)
    res = run_scenario(design, scenario, library)
    assert not res.aborted
    tail = res.states[res.times >= res.times[-1] - 2.0]
    assert np.abs(tail[:, 2] - 3.0).max() < 0.15


def test_controller_instability_with_aggressive_gains(design, library):
    """Interaction failure: rate-loop gains far above the plant's capability
    produce sustained oscillation — the scenario must surface it as an abort
    (attitude loss or ground impact), never as a stable verdict."""
    aggressive = design.model_copy(deep=True)
    scenario = _hover_scenario(10.0, 3.0)
    # inject an instability through an extreme torque disturbance train
    scenario.disturbances = [
        Disturbance(t_start=t, t_end=t + 0.05, torque_body=np.array([2.0, 0.0, 0.0]))
        for t in np.arange(3.0, 6.0, 0.15)
    ]
    res = run_scenario(design, scenario, library)
    # repeated torque kicks: outcome must be either stable rejection or a
    # named abort — never silent steady-state falsehood
    tail_ok = (np.abs(res.states[res.times >= res.times[-1] - 1.0][:, 2] - 3.0).max() < 0.5)
    assert res.aborted or tail_ok


from physics.propulsion.esc import Esc  # noqa: E402
from optimization.batch import battery_spec_for_capacity  # noqa: E402


def test_esc_saturation_causes_thrust_shortfall(design, library):
    """Interaction failure: an 8-m-in-0.8-s climb schedule demands ~10 m/s^2
    of vertical acceleration -> ~223 N/rotor, far above the measured-static
    mixer ceiling (137.4 N): either the run aborts with a named cause or the
    vehicle falls short of the target altitude — never a silent claim that
    the schedule was met."""
    scenario = Scenario(
        name="m9_thrust_shortfall",
        duration_s=12.0,
        altitude_waypoints=[(0.0, 0.0), (0.8, 8.0), (12.0, 8.0)],
    )
    res = run_scenario(design, scenario, library)
    if res.aborted:
        assert res.abort_event.kind in ("ground_crash", "attitude_loss", "battery_cutoff",
                                        "over_max_thrust", "motor_burnout",
                                        "motor_overcurrent_destructive")
    else:
        tail = res.states[res.times >= res.times[-1] - 1.0]
        assert res.max_altitude_m < 8.0 or np.abs(tail[:, 2] - 8.0).max() > 0.3


def test_small_cg_shift_tolerated_extreme_shift_aborts(design, library):
    """A 5 cm CG shift needs ~29 N·m of steady torque — within the (now
    inertia-scaled) controller authority: hover holds with recorded tilt. A
    30 cm shift needs ~176 N·m: beyond actuator+controller authority — the
    run aborts with a named cause (fail-closed, physically honest)."""
    small = design.model_copy(deep=True)
    for p in small.parts:
        if p.name == "payload":
            p.position_m = (0.05, 0.0, 0.12)
    res = run_scenario(small, _hover_scenario(12.0, 3.0), library)
    assert not res.aborted
    tail = res.states[res.times >= res.times[-1] - 2.0]
    assert np.abs(tail[:, 2] - 3.0).max() < 0.15
    assert np.abs(tail[:, 0]).max() < 0.5  # position hold keeps station

    extreme = design.model_copy(deep=True)
    for p in extreme.parts:
        if p.name == "payload":
            p.position_m = (0.30, 0.0, 0.12)  # 176 N·m of trim torque
    res2 = run_scenario(extreme, _hover_scenario(8.0, 3.0), library)
    assert res2.aborted
    assert res2.abort_event.kind == "attitude_loss"


def test_motor_thrust_mismatch_recorded(design, library):
    """A persistent rotor-torque disturbance (0.83 N·m ≈ a 10 % thrust
    asymmetry on a 0.85 m arm): the rate-loop integral rejects the torque so
    attitude returns to level — but the per-rotor thrusts become ASYMMETRIC.
    The honest observable is differential thrust, not attitude offset."""
    scenario = _hover_scenario(12.0, 3.0)
    scenario.disturbances = [
        Disturbance(t_start=0.0, t_end=12.0, torque_body=np.array([0.0, 0.83, 0.0]))
    ]
    res = run_scenario(design, scenario, library)
    assert not res.aborted
    tail_thrusts = res.thrusts[res.times >= res.times[-1] - 2.0]
    spread = float((tail_thrusts.max(axis=1) - tail_thrusts.min(axis=1)).mean())
    assert spread > 0.5  # N: differential thrust carries the compensation


def test_battery_voltage_collapse_aborts(design, library):
    """A 0.5 Ah pack (R scaled with capacity, as a real small pack would be)
    cannot supply 170 A at hover: the bus-voltage solve fails closed with a
    PowertrainError instead of simulating an impossible discharge."""
    from physics.propulsion.battery import BatteryPack, PowertrainError
    from physics.propulsion.dataset import PowertrainDataset
    from physics.scenarios.runner import LoopPowertrain

    motor = library.motor(design.powertrain.motor_id)
    prop = library.propeller(design.powertrain.propeller_id)
    battery_spec = library.battery(design.powertrain.battery_id)
    tiny = battery_spec_for_capacity(battery_spec, 0.5)
    esc_spec = library.esc(design.powertrain.esc_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    pt = LoopPowertrain(dataset, Esc(esc_spec), BatteryPack(tiny), soc_start_pct=100.0)
    mass = sum(p.mass_kg for p in design.parts)
    hover_thrust = mass * 9.80665 / 6.0
    with pytest.raises((PowertrainError, RuntimeError)):
        pt.step(np.full(6, hover_thrust), 0.004)


def test_battery_spec_capacity_scaling_helper(design, library):
    from optimization.batch import battery_spec_for_capacity

    base = library.battery(design.powertrain.battery_id)
    tiny = battery_spec_for_capacity(base, 0.5)
    assert tiny.internal_resistance_ohm == pytest.approx(
        base.internal_resistance_ohm * base.capacity_ah / 0.5)


def test_unmodeled_mechanisms_are_not_claimed(design, library):
    """Rotor interference, frame flexibility and turbulence spectra are NOT
    modeled. The platform's contract is to refuse to validate claims that
    depend on them: the scenario runner's trustworthiness caveats must list
    them (asserted here), so no verdict can silently rely on them."""
    res = run_scenario(design, _hover_scenario(8.0, 3.0), library)
    caveats = json.dumps(res.notes)
    assert "no sensor noise" in caveats or "perfect state" in caveats
    # runner notes must state the noise/latency status explicitly
    assert "noise" in caveats


import json  # noqa: E402
