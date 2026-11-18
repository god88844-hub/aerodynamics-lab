"""M4 acceptance tests: flight scenarios complete with metrics; induced
failures abort the run with named causes (spec Milestone 4 / Prompt 6)."""

from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign, FrameSpec
from physics.controller.sensors import SensorConfig
from physics.propulsion.battery import BatteryPack
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.esc import Esc
from physics.propulsion.loader import ComponentLibrary
from physics.scenarios.runner import (
    LoopPowertrain,
    landing_scenario,
    motor_failure_scenario,
    run_scenario,
    takeoff_climb_scenario,
)
from physics.structures.beam import bending_stress_pa, tube_second_moment
from physics.structures.materials import load_materials

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_MN = REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json"
DESIGN_2KG = REPO_ROOT / "data" / "designs" / "quad_example_2kg.json"


@pytest.fixture(scope="module")
def library() -> ComponentLibrary:
    return ComponentLibrary(REPO_ROOT / "data" / "components")


@pytest.fixture(scope="module")
def design_mn() -> DroneDesign:
    return DroneDesign.model_validate_json(DESIGN_MN.read_text(encoding="utf-8"))


# ------------------------------------------------------------ happy paths


def test_takeoff_climb_completes_with_metrics(design_mn, library):
    res = run_scenario(design_mn, takeoff_climb_scenario(5.0), library)
    assert not res.aborted, res.abort_event.message if res.abort_event else None
    assert res.time_to_altitude_s is not None
    assert 1.0 <= res.time_to_altitude_s <= 8.0     # 2 m/s schedule + settle
    assert res.max_altitude_m == pytest.approx(5.0, abs=0.5)
    assert res.energy_wh > 0
    assert res.success_all is True
    # Sourced powertrain telemetry present.
    assert res.per_motor_current_a is not None and res.v_bus is not None
    assert res.structural_margin_min is not None and res.structural_margin_min > 1.0


def test_landing_completes_gently(design_mn, library):
    res = run_scenario(design_mn, landing_scenario(4.0, duration_s=14.0), library)
    assert not res.aborted, res.abort_event.message if res.abort_event else None
    assert abs(res.states[-1, 2]) < 0.05
    assert abs(res.states[-1, 5]) < 1.5
    assert res.success_all is True


def test_forward_flight_arrives(design_mn, library):
    from physics.scenarios.runner import forward_flight_scenario

    res = run_scenario(design_mn, forward_flight_scenario(5.0, 2.0), library)
    assert not res.aborted, res.abort_event.message if res.abort_event else None
    assert res.success_all is True


# ------------------------------------------------------------- failures


def test_motor_failure_aborts_with_named_cause(design_mn, library):
    """Spec Prompt 6: a killed motor must NOT let the sim run to completion
    silently — the run aborts with an informative unrecoverable-state event."""
    res = run_scenario(design_mn, motor_failure_scenario(2.0, failure_at_s=4.0), library)
    assert res.aborted
    assert res.abort_event is not None
    assert res.abort_event.kind in ("attitude_loss", "ground_crash")
    assert "unrecoverable" in res.abort_event.message or "impact" in res.abort_event.message


def test_battery_depleted_aborts(design_mn, library):
    """Starting at 0 % SOC: cell voltage below cutoff -> immediate abort."""
    motor = library.motor(design_mn.powertrain.motor_id)
    prop = library.propeller(design_mn.powertrain.propeller_id)
    battery_spec = library.battery(design_mn.powertrain.battery_id)
    esc_spec = library.esc(design_mn.powertrain.esc_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    pt = LoopPowertrain(dataset, Esc(esc_spec), BatteryPack(battery_spec), soc_start_pct=0.0)
    thrusts = np.array([9.1, 9.1, 9.1, 9.1])
    aux = pt.step(thrusts, 0.004)
    kinds = [e["kind"] for e in aux.events]
    assert "battery_cutoff" in kinds


def test_local_esc_overload_survives_averaging_and_aborts(design_mn, library, monkeypatch):
    powertrain = design_mn.powertrain
    motor = library.motor(powertrain.motor_id)
    prop = library.propeller(powertrain.propeller_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    battery = BatteryPack(library.battery(powertrain.battery_id))
    spec = library.esc(powertrain.esc_id).model_copy(update={"max_continuous_current_a": 6.0})
    loop = LoopPowertrain(dataset, Esc(spec), battery)
    thrusts = np.array([6.0, 15.0, 6.0, 6.0])
    aux = loop.step(thrusts, 0.004)
    assert np.mean(aux.per_motor_current_a) < 6.0 < aux.per_motor_current_a[1]
    events = [event for event in aux.events if event["kind"] == "esc_overcurrent"]
    assert len(events) == 1 and events[0]["critical"]
    assert "rotor 1" in events[0]["message"]

    monkeypatch.setattr(library, "esc", lambda key: spec)
    monkeypatch.setattr("physics.scenarios.runner.QuadcopterController.step",
                        lambda *args: thrusts.copy())
    mission = run_scenario(design_mn, takeoff_climb_scenario(2.0), library)
    assert mission.aborted and mission.abort_event.kind == "esc_overcurrent"
    assert mission.abort_event.t_s == 0 and mission.success_all is False

    low_voltage = spec.model_copy(update={"max_voltage_v": 20.0})
    aux = LoopPowertrain(dataset, Esc(low_voltage), battery).step(thrusts, 0.004)
    voltage_events = [event for event in aux.events if event["kind"] == "esc_overvoltage"]
    assert len(voltage_events) == 1 and voltage_events[0]["critical"]


def test_over_max_thrust_detected(design_mn, library):
    """Forcing thrust above the measured static maximum (motor over-speed
    equivalent) must be reported as a critical failure, not silently accepted."""
    motor = library.motor(design_mn.powertrain.motor_id)
    prop = library.propeller(design_mn.powertrain.propeller_id)
    battery_spec = library.battery(design_mn.powertrain.battery_id)
    esc_spec = library.esc(design_mn.powertrain.esc_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    pt = LoopPowertrain(dataset, Esc(esc_spec), BatteryPack(battery_spec), soc_start_pct=100.0)
    aux = pt.step(np.array([25.0, 25.0, 25.0, 25.0]), 0.004)  # >> 18.4 N max
    kinds = [e["kind"] for e in aux.events]
    assert "over_max_thrust" in kinds
    assert any(e["critical"] for e in aux.events if e["kind"] == "over_max_thrust")


def test_structure_yield_aborts(library):
    """A design with absurdly thin arms must fail closed under flight loads."""
    design = DroneDesign.model_validate_json(DESIGN_MN.read_text(encoding="utf-8"))
    thin = design.model_copy(deep=True)
    thin.frame = FrameSpec(arm_length_m=0.25, tube_od_m=0.005, tube_id_m=0.0045,
                           material_id="cfrp_quasi_iso")
    res = run_scenario(thin, takeoff_climb_scenario(2.0, duration_s=10.0), library)
    assert res.aborted
    assert res.abort_event.kind == "structure_yield"
    assert res.abort_event.message.startswith("STRUCTURAL FAILURE")


def test_frame_material_unknown_fails_closed(design_mn, library):
    bad = design_mn.model_copy(deep=True)
    bad.frame = FrameSpec(arm_length_m=0.25, tube_od_m=0.012, tube_id_m=0.010,
                          material_id="unobtainium")
    with pytest.raises(ValueError, match="not in materials"):
        run_scenario(bad, takeoff_climb_scenario(2.0), library=library)


# ------------------------------------------------------------- sensors


def test_hover_robust_to_sensor_noise_and_latency(design_mn, library):
    """Declared noise/latency (GNSS-grade position, gyro-grade rate, 20 ms
    latency): hover must remain stable — a robustness smoke gate."""
    scenario = takeoff_climb_scenario(1.0, duration_s=12.0)
    scenario.sensor_config = SensorConfig(
        seed=42, sigma_position_m=0.02, sigma_velocity_m_s=0.05,
        sigma_attitude_deg=0.5, sigma_rate_deg_s=1.0, latency_s=0.02,
    )
    res = run_scenario(design_mn, scenario, library)
    assert not res.aborted, res.abort_event.message if res.abort_event else None
    tail = res.states[res.times >= res.times[-1] - 2.0]
    assert np.abs(tail[:, 2] - 1.0).max() < 0.15
    assert res.success_all is True


# ------------------------------------------------------------- structures


def test_tube_bending_stress_hand_calculation():
    """12x10 mm tube, 9.09 N at 0.25 m: I = 5.27e-10, sigma = 25.8 MPa."""
    inertia = tube_second_moment(0.012, 0.010)
    assert inertia == pytest.approx(5.27e-10, rel=0.01)
    stress = bending_stress_pa(9.09, 0.25, 0.012, 0.010)
    assert stress == pytest.approx(25.8e6, rel=0.02)


def test_materials_db_load():
    mats = load_materials(REPO_ROOT / "data" / "components" / "materials.json")
    assert "cfrp_quasi_iso" in mats
    assert mats["cfrp_quasi_iso"].yield_strength_pa == pytest.approx(500e6)
