"""P0A-012 verification through the authoritative closed-loop scenario runner."""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign
from physics.controller.sensors import SensorConfig
from physics.dynamics.quaternion import rotation_matrix
from physics.propulsion.branches import BranchFailure, BranchLimits
from physics.propulsion.loader import ComponentLibrary
from physics.scenarios.runner import (
    BUS_SOLVE_TOLERANCE_V, Scenario, motor_failure_scenario, run_scenario,
)

DATA = Path(__file__).resolve().parents[2] / "data"
DT = 0.004


def design_named(name):
    return DroneDesign.model_validate_json(
        (DATA / "designs" / f"{name}.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def plant():
    return design_named("quad_mn3508_6s"), ComponentLibrary(DATA / "components")


def mission(**kwargs):
    return Scenario(
        "p0a012", 0.8, [(0.0, 2.0), (0.35, 4.0), (0.8, 4.0)],
        reference_mode="planned",
        position_waypoints=[(0.0, (0.0, 0.0)), (0.5, (1.5, 0.0))],
        initial_altitude_m=2.0,
        success_criteria=[("climbed", lambda v: v.states[-1, 2] > 2.7)],
        **kwargs,
    )


@pytest.mark.parametrize(("limits", "component", "limit", "t_s"), [
    (BranchLimits(max_current_a=1.0), "esc", "branch_current", 0.0),
    (BranchLimits(series_resistance_ohm=0.2, min_voltage_v=25.0),
     "esc", "branch_undervoltage", 0.0),
    (BranchLimits(max_voltage_v=23.0), "esc", "branch_overvoltage", 0.0),
    (BranchLimits(max_rpm=1000.0), "motor", "rotor_rpm", 0.0),
    (BranchLimits(thermal_current_a=1.0, thermal_duration_s=0.006),
     "esc", "thermal_current_duration", 0.006),
    (BranchLimits(max_thrust_n=1.0), "actuator", "actuator_thrust", 0.0),
])
def test_branch_excursion_names_only_affected_component(plant, limits, component, limit, t_s):
    design, library = plant
    res = run_scenario(design, mission(branch_limits={2: limits}), library)
    assert res.aborted and res.flight_verdict == "FAIL" and res.success_all is False
    assert res.abort_event.t_s == pytest.approx(t_s, abs=1e-14)
    details = {k: v for k, v in res.component_verdicts.items() if isinstance(v, dict)}
    assert list(details) == [f"{component}:2"]
    branch = details[f"{component}:2"]
    assert branch["status"] == "FAIL" and branch["branch_id"] == 2
    assert res.component_verdicts[component] == "FAIL"
    finding, = branch["findings"]
    assert finding["limit"] == limit and finding["t_s"] == res.abort_event.t_s
    if limits.series_resistance_ohm:
        voltages = res.branch_voltage_v[0]
        assert voltages[0] == res.v_bus[0]
        assert voltages[2] < voltages[0]
        assert voltages[2] == pytest.approx(
            res.v_bus[0] - limits.series_resistance_ohm * res.per_motor_current_a[0, 2],
            abs=1e-7,
        )


def tilt_deg(states):
    return np.degrees(np.arccos(np.clip(
        [rotation_matrix(q)[2, 2] for q in states[:, 6:10]], -1.0, 1.0
    )))


def test_sag_limits_same_tick_force_and_changes_closed_loop_tracking(plant, monkeypatch):
    design, library = plant
    scenario = replace(
        mission(), altitude_waypoints=[(0.0, 2.0), (0.35, 8.0), (0.8, 8.0)],
        success_criteria=[("climbed_above_3_7m", lambda v: v.states[-1, 2] > 3.7)],
    )
    original = library.battery(design.powertrain.battery_id)
    nominal = run_scenario(design, scenario, library)
    sag_pack = original.model_copy(update={"internal_resistance_ohm": 0.115})
    monkeypatch.setattr(library, "battery", lambda _: sag_pack)
    sagged = run_scenario(design, scenario, library)

    from physics.propulsion.battery import BatteryPack

    pre_soc = np.r_[100.0, sagged.soc_pct[:-1]]
    pack = BatteryPack(sag_pack)
    expected_bus = [pack.voltage_under_load(soc, sum(i))
                    for soc, i in zip(pre_soc, sagged.per_motor_current_a)]
    np.testing.assert_allclose(sagged.v_bus, expected_bus, atol=BUS_SOLVE_TOLERANCE_V, rtol=0)
    assert not nominal.aborted and not sagged.aborted
    assert nominal.flight_verdict == sagged.flight_verdict == "NO_MODELED_LIMIT_BREACHED"
    assert nominal.success_all is True and sagged.success_all is False
    assert sagged.per_motor_rpm.max() < nominal.per_motor_rpm.max() - 200.0
    assert sagged.thrusts.sum(axis=1).max() < nominal.thrusts.sum(axis=1).max() - 5.0
    assert np.all(sagged.thrusts <= sagged.attainable_thrust_n + 1e-12)
    assert np.min(sagged.v_bus) < np.min(nominal.v_bus) - 1.5
    assert np.min(sagged.attainable_thrust_n.sum(axis=1)) < (
        np.min(nominal.attainable_thrust_n.sum(axis=1)) - 5.0
    )
    assert np.min(sagged.wrench_residual[:, 0]) < -1.0
    assert sagged.allocation_counts["saturated_max"] > nominal.allocation_counts["saturated_max"]
    assert sagged.states[-1, 2] < nominal.states[-1, 2] - 0.05
    assert np.max(abs(tilt_deg(sagged.states) - tilt_deg(nominal.states))) > 0.5
    print("sag/nominal:", [(float(r.v_bus.min()), float(r.attainable_thrust_n.sum(axis=1).min()),
                            float(r.thrusts.sum(axis=1).max()),
                            float(r.wrench_residual[:, 0].min()), float(r.states[-1, 2]),
                            float(np.linalg.norm(r.wrench_residual[:, 1:], axis=1).max()),
                            r.allocation_counts, r.flight_verdict, r.success_all)
                           for r in (sagged, nominal)],
          "max tilt delta deg:", max(abs(tilt_deg(sagged.states) - tilt_deg(nominal.states))))


@pytest.mark.parametrize("kind", ["esc_cutout", "motor_cutout"])
def test_cutout_changes_actual_attitude_and_altitude_and_cannot_pass(plant, kind):
    design, library = plant
    scenario = mission()
    healthy = run_scenario(design, scenario, library)
    loss = run_scenario(design, replace(scenario, branch_failure=BranchFailure(1, 0.081, kind)),
                        library)
    k = np.searchsorted(loss.times, 0.084)
    assert loss.times[k] == 0.084
    assert loss.flight_verdict == "FAIL" and loss.success_all is False
    finding, = loss.component_verdicts[f"{kind.split('_')[0]}:1"]["findings"]
    assert finding["limit"] == "branch_availability" and finding["t_s"] == loss.times[k]
    for data in (loss.thrusts, loss.per_motor_current_a, loss.branch_voltage_v,
                 loss.per_motor_rpm, loss.attainable_thrust_n):
        assert np.all(data[k:, 1] == 0)
    np.testing.assert_array_equal(loss.thrusts[k, [0, 2, 3]], healthy.thrusts[k, [0, 2, 3]])
    assert loss.wrench_residual[k, 0] < -5.0
    assert np.linalg.norm(loss.wrench_residual[k, 1:]) > 1.0
    assert loss.allocation_counts["torque_residual"] > 0
    end = len(loss.times) - 1
    assert tilt_deg(loss.states)[-1] > tilt_deg(healthy.states)[end] + 10
    assert loss.states[-1, 2] < healthy.states[end, 2] - 0.05
    print(kind, "first-tick healthy/loss realized thrust",
          healthy.thrusts[k].sum(), loss.thrusts[k].sum(),
          "capability", healthy.attainable_thrust_n[k].sum(), loss.attainable_thrust_n[k].sum(),
          "loss residual", loss.wrench_residual[k], "last tick", loss.times[-1],
          "healthy/loss altitude", healthy.states[end, 2], loss.states[-1, 2],
          "healthy/loss tilt", tilt_deg(healthy.states)[end], tilt_deg(loss.states)[-1],
          "abort", loss.abort_event)


@pytest.mark.parametrize("kind", ["blade_breakup", "winding_short_drag", "fault_tolerant_reallocation"])
@pytest.mark.parametrize("at_s", [0.0, 0.081])
def test_unsupported_mechanism_stops_before_any_post_failure_step(plant, kind, at_s):
    design, library = plant
    scenario = mission()
    healthy = run_scenario(design, scenario, library)
    refused = run_scenario(
        design, replace(scenario, branch_failure=BranchFailure(3, at_s, kind)), library
    )
    assert refused.aborted and refused.flight_verdict == "INCONCLUSIVE"
    assert refused.success_all is False
    assert refused.abort_event.kind == "unsupported_branch_failure"
    finding, = refused.component_verdicts["actuator:3"]["findings"]
    assert finding["status"] == "INCONCLUSIVE" and finding["limit"] == kind
    assert finding["t_s"] == (0.084 if at_s else 0.0)
    before = healthy.times < finding["t_s"]
    np.testing.assert_array_equal(refused.states, healthy.states[before])
    np.testing.assert_array_equal(refused.thrusts, healthy.thrusts[before])
    assert len(refused.times) == before.sum()


def test_seeded_branch_loss_is_bit_identical_and_future_fault_is_causal(plant):
    design, library = plant
    scenario = mission(branch_failure=BranchFailure(2, 0.2, "esc_cutout"),
                       sensor_config=SensorConfig(seed=12, sigma_rate_deg_s=0.5))
    a = run_scenario(design, scenario, library)
    b = run_scenario(design, scenario, library)
    delayed = run_scenario(
        design, replace(scenario, branch_failure=BranchFailure(2, 0.5, "esc_cutout")), library
    )
    before = a.times < 0.2
    for field in ("times", "states", "thrusts", "v_bus", "soc_pct", "wrench_residual",
                  "per_motor_current_a", "per_motor_rpm", "branch_voltage_v", "attainable_thrust_n"):
        trace = getattr(a, field)
        assert trace.tobytes() == getattr(b, field).tobytes()
        assert trace[before].tobytes() == getattr(delayed, field)[:before.sum()].tobytes()
    assert a.events == b.events
    assert a.component_verdicts == b.component_verdicts
    assert a.allocation_counts == b.allocation_counts
    assert a.energy_wh.hex() == b.energy_wh.hex()
    assert a.thrusts[before.sum(), 2] == 0 < delayed.thrusts[before.sum(), 2]


def test_reference_hexa_motor_loss_still_aborts(plant):
    _, library = plant
    res = run_scenario(design_named("hexa_p80_60kg"), motor_failure_scenario(5.0, 6.0), library)
    assert res.aborted and res.abort_event.kind in {"attitude_loss", "ground_crash"}
    assert res.flight_verdict == "FAIL" and res.success_all is False
    event, = res.component_verdicts["motor:0"]["findings"]
    assert event["t_s"] == 6.0 and event["limit"] == "branch_availability"
    print("hexa end:", res.abort_event)
