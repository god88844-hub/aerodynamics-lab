"""P0A-014: causal control, delivered motion, and typed limit refusals."""

from dataclasses import fields, replace
from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign
from physics.controller.attitude import QuadcopterController
from physics.controller.sensors import SensorConfig
from physics.controller.simulation import Disturbance
from physics.dynamics.quaternion import rotation_matrix
from physics.propulsion.battery import BatteryPack
from physics.propulsion.branches import BranchFailure, BranchLimits
from physics.propulsion.loader import ComponentLibrary
from physics.scenarios.runner import Scenario, run_scenario

DATA = Path(__file__).resolve().parents[2] / "data"
DT = 0.004


@pytest.fixture
def plant():
    return (
        DroneDesign.model_validate_json((DATA / "designs/quad_mn3508_6s.json").read_bytes()),
        ComponentLibrary(DATA / "components"),
    )


def hover(**kwargs):
    return Scenario("hover", 0.04, [(0.0, 2.0)], initial_altitude_m=2.0, **kwargs)


def held_battery(plant, monkeypatch, **changes):
    design, library = plant
    spec = library.battery(design.powertrain.battery_id).model_copy(update=changes)
    monkeypatch.setattr(library, "battery", lambda _: spec)
    return spec


def assert_same_prefix(a, b, n):
    for field in ("times", "states", "thrusts", "wrench_residual", "v_bus",
                  "soc_pct", "branch_voltage_v", "per_motor_current_a",
                  "per_motor_rpm", "attainable_thrust_n"):
        assert getattr(a, field)[:n].tobytes() == getattr(b, field)[:n].tobytes(), field
    for field in fields(a.clock):
        assert (getattr(a.clock, field.name)[:n].tobytes()
                == getattr(b.clock, field.name)[:n].tobytes()), field.name


@pytest.mark.parametrize("future", ["references", "disturbance"])
def test_future_updates_cannot_change_commands_or_states_at_prefix(plant, future):
    design, library = plant
    scenario = Scenario(
        "stream", 0.22, [(0.0, 2.0), (0.101, 3.0), (0.185, 3.5)],
        position_waypoints=[(0.0, (0.0, 0.0)), (0.101, (0.2, 0.0))],
        initial_altitude_m=2.0,
        sensor_config=SensorConfig(seed=641, sigma_rate_deg_s=0.05),
    )
    if future == "references":
        changed = replace(
            scenario, altitude_waypoints=[(0.185, 1.0), (0.101, 1.5), (0.0, 2.0)],
            position_waypoints=[(0.101, (-0.5, 0.3)), (0.0, (0.0, 0.0))],
        )
    else:
        # 0.101 falls inside the [0.100, 0.104] RK4 interval. Only the
        # 0.104 control tick can first observe this held disturbance.
        changed = replace(scenario, disturbances=[
            Disturbance(t_start=0.101, t_end=0.17, force_world=np.array([4.0, 0.0, -2.0]))
        ])
    a = run_scenario(design, scenario, library)
    b = run_scenario(design, changed, library)
    n = int(np.count_nonzero(a.times <= 0.100))
    assert n == 26
    assert a.clock.state_time_s[n - 1] == n * DT
    assert_same_prefix(a, b, n)
    assert a.clock.command_wrench[n + 2:].tobytes() != b.clock.command_wrench[n + 2:].tobytes()
    assert a.states[n:].tobytes() != b.states[n:].tobytes()
    if future == "disturbance":
        assert a.clock.command_wrench[n].tobytes() == b.clock.command_wrench[n].tobytes()
        assert a.states[n].tobytes() != b.states[n].tobytes()
    print(f"{future}: {n} identical tick rows through {a.times[n - 1]:.3f} s")


def tilt_deg(states):
    return np.degrees(np.arccos(np.clip(
        [rotation_matrix(q)[2, 2] for q in states[:, 6:10]], -1, 1
    )))


def test_sag_changes_delivered_motion_and_feedback_on_same_clock(plant, monkeypatch):
    design, library = plant
    scenario = Scenario(
        "climb-turn", 0.8, [(0.0, 2.0), (0.35, 8.0), (0.8, 8.0)],
        position_waypoints=[(0.0, (0.0, 0.0)), (0.5, (1.5, 0.0))],
        initial_altitude_m=2.0, reference_mode="planned",
    )
    nominal = run_scenario(design, scenario, library)
    pack = BatteryPack(held_battery(plant, monkeypatch, internal_resistance_ohm=0.115))
    sagged = run_scenario(design, scenario, library)
    repeat = run_scenario(design, scenario, library)
    for result in (nominal, sagged):
        assert not result.aborted
        clock = result.clock
        assert clock.integrated.all()
        np.testing.assert_array_equal(clock.state_time_s, (np.arange(len(result.times)) + 1) * DT)
        np.testing.assert_array_equal(clock.state_time_s, clock.electrical_time_s)
        np.testing.assert_array_equal(clock.state_start[1:], result.states[:-1])
        np.testing.assert_array_equal(clock.previous_wrench_residual[1:], result.wrench_residual[:-1])
        np.testing.assert_allclose(clock.applied_rotor_wrench - clock.command_wrench,
                                   result.wrench_residual, rtol=0, atol=1e-12)
        np.testing.assert_allclose(clock.applied_rotor_wrench[:, 0], result.thrusts.sum(axis=1),
                                   rtol=0, atol=1e-12)
    assert_same_prefix(sagged, repeat, len(sagged.times))
    assert sagged.events == repeat.events and sagged.energy_wh.hex() == repeat.energy_wh.hex()
    assert sagged.component_verdicts == repeat.component_verdicts
    soc_start = np.r_[100.0, sagged.soc_pct[:-1]]
    expected_v = [pack.voltage_under_load(soc, float(current.sum()))
                  for soc, current in zip(soc_start, sagged.per_motor_current_a)]
    np.testing.assert_allclose(sagged.v_bus, expected_v, atol=1e-4, rtol=0)
    assert sagged.v_bus.min() < nominal.v_bus.min() - 3
    assert sagged.thrusts.sum(axis=1).max() < nominal.thrusts.sum(axis=1).max() - 5
    assert np.max(sagged.thrusts - sagged.attainable_thrust_n) <= 1e-12
    assert sagged.allocation_counts["saturated_max"] > nominal.allocation_counts["saturated_max"]
    assert sagged.states[-1, 2] < nominal.states[-1, 2] - 0.1
    tilt_delta = float(np.max(abs(tilt_deg(sagged.states) - tilt_deg(nominal.states))))
    assert tilt_delta > 1
    print("nominal/sagged (minimum V, minimum collective ceiling, peak applied N,",
          "saturated ticks, last altitude):",
          [(r.v_bus.min(), r.attainable_thrust_n.sum(axis=1).min(), r.thrusts.sum(axis=1).max(),
            r.allocation_counts["saturated_max"], r.states[-1, 2]) for r in (nominal, sagged)],
          "max tilt delta:", tilt_delta)

    # Run a counterfactual with only the integral guard disabled. The same
    # authority and motion loop generates distinct commands once limited.
    monkeypatch.setattr(QuadcopterController, "_can_integrate", lambda *_: True)
    no_guard = run_scenario(design, scenario, library)
    saturation = np.flatnonzero(np.any(sagged.clock.nominal_thrust_n > sagged.thrusts + 1e-9, axis=1))
    start = saturation[0] + 1
    assert start < len(sagged.times)
    assert_same_prefix(sagged, no_guard, start)
    assert np.max(abs(sagged.clock.command_wrench[start:] - no_guard.clock.command_wrench[start:])) > 1e-6


def test_cutoff_boundary_and_branch_limits_retain_structured_fail(plant, monkeypatch):
    design, library = plant
    baseline_spec = library.battery(design.powertrain.battery_id)
    healthy = run_scenario(design, hover(), library)
    loaded_cell_v = BatteryPack(baseline_spec).voltage_under_load(
        100, float(healthy.per_motor_current_a[0].sum())
    ) / baseline_spec.cells_series
    for offset in (-0.001, 0.0, 0.001):
        spec = baseline_spec.model_copy(update={
            "cutoff_cell_voltage_v": loaded_cell_v + offset,
            "warning_cell_voltage_v": loaded_cell_v + 0.01,
        })
        monkeypatch.setattr(library, "battery", lambda _: spec)
        result = run_scenario(design, hover(), library)
        if offset < 0:
            assert not result.aborted
            continue
        assert result.flight_verdict == result.component_verdicts["battery"] == "FAIL"
        assert result.abort_event.kind == "battery_cutoff"
        assert result.abort_event.t_s == 0.0
        finding, = result.component_verdicts["battery:pack"]["findings"]
        assert finding["limit"] == "loaded_cell_cutoff" and finding["t_s"] == 0.0
        assert finding["threshold"] == loaded_cell_v + offset
        assert finding["observed"] <= finding["threshold"]
        assert not result.clock.integrated.any() and not result.clock.applied_rotor_wrench.any()
        assert result.energy_wh == 0.0
    print("cutoff threshold bracket around", loaded_cell_v, "V/cell")

    monkeypatch.setattr(library, "battery", lambda _: baseline_spec)
    result = run_scenario(design, hover(branch_limits={1: BranchLimits(max_current_a=1.0)}), library)
    assert result.flight_verdict == "FAIL"
    verdict = result.component_verdicts["esc:1"]
    finding, = verdict["findings"]
    assert verdict["status"] == "FAIL"
    assert (finding["branch_id"], finding["limit"], finding["t_s"]) == (1, "branch_current", 0.0)
    assert not result.clock.integrated.any()


@pytest.mark.parametrize(("resistance", "status", "event"), [
    (0.64, "FAIL", "battery_voltage_collapse"),
    (0.50, "INCONCLUSIVE", "bus_operating_point_unsupported"),
])
def test_known_power_boundary_is_distinct_from_unsupported_bus(plant, monkeypatch,
                                                               resistance, status, event):
    design, library = plant
    held_battery(plant, monkeypatch, internal_resistance_ohm=resistance)
    result = run_scenario(design, hover(), library)
    assert result.aborted and result.abort_event.kind == event
    assert result.flight_verdict == result.component_verdicts["battery"] == status
    assert result.success_all is False and not result.clock.integrated.any()
    assert result.energy_wh == 0.0 and result.v_bus is None
    np.testing.assert_array_equal(result.states, result.clock.state_start)
    if status == "FAIL":
        finding, = result.component_verdicts["battery:pack"]["findings"]
        assert finding["limit"] == "constant_power_demand"
        assert finding["observed"] > finding["threshold"]
        print("known request/limit in W:", finding["observed"], finding["threshold"])
    else:
        assert "battery:pack" not in result.component_verdicts


def test_unknown_post_fault_stops_before_issuing_a_command(plant):
    design, library = plant
    result = run_scenario(design, hover(branch_failure=BranchFailure(2, 0.009, "winding_short_drag")),
                          library)
    assert result.flight_verdict == "INCONCLUSIVE" and result.success_all is False
    assert result.abort_event.t_s == 0.012
    assert result.component_verdicts["actuator:2"]["status"] == "INCONCLUSIVE"
    assert list(result.times) == [0.0, 0.004, 0.008]
    assert result.clock.state_time_s[-1] == result.abort_event.t_s
