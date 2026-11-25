"""P0A-015 code/solution verification on the authoritative multirotor runner."""

from dataclasses import asdict, fields, replace
from hashlib import sha256
import json
from math import fsum, pi
from pathlib import Path
import re

import numpy as np
import pytest
from pydantic import ValidationError
from scipy.spatial.transform import Rotation

from aeroforge_schemas.design import DroneDesign
from aeroforge_schemas.project import AssemblyNode
from physics.aerodynamics.axial_prop import AxialEnvelope, AxialPropellerModel, PlaneKnots
from physics.constants import STANDARD_GRAVITY
from physics.controller.sensors import SensorConfig
from physics.controller.simulation import Disturbance
from physics.dynamics.design_adapter import build_multirotor
from physics.dynamics.quaternion import from_axis_angle, normalize, rotate, rotate_inverse, rotation_matrix
from physics.dynamics.rigid_body import RigidBody, make_state, normalize_state
from physics.integration.rk4 import integrate_fixed
from physics.propulsion.battery import BatteryPack
from physics.propulsion.branches import BranchFailure, BranchLimits
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.loader import ComponentLibrary
from physics.scenarios.runner import Scenario, run_scenario

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SEED = 20261125
DT = 0.004
FORCE_N = 2e-12
MOMENT_NM = 2e-12
MECHANICAL_POWER_W = 2e-12
ANALYTIC_STATE = 2e-12
FRAME = 2e-14
CHARGE_C = 1e-8
ENERGY_ROUNDOFF_J = 1e-10
BUS_RESIDUAL_V = 1e-4
WIRE_RESIDUAL_V = 1e-8
FINE_LIMITS = np.array([1.0e-3, 3.5e-4, 0.08, 0.006])


def max_error(a, b):
    return float(np.max(np.abs(np.asarray(a) - b)))


@pytest.fixture
def hardware():
    design = DroneDesign.model_validate_json((DATA / "designs/quad_mn3508_6s.json").read_bytes())
    return design, ComponentLibrary(DATA / "components")


def hover(duration=DT, **kwargs):
    return Scenario("hover", duration, [(0.0, 2.0)], initial_altitude_m=2.0, **kwargs)


def maneuver(**kwargs):
    return Scenario(
        "step-climb-turn", 0.96, [(0.0, 2.0), (0.16, 4.0), (0.56, 3.0)],
        position_waypoints=[(0.0, (0.0, 0.0)), (0.16, (0.3, -0.1)), (0.64, (0.6, -0.2))],
        initial_altitude_m=2.0,
        disturbances=[Disturbance(0.32, 0.48, force_world=np.array([2.0, -1.0, -1.5]))],
        **kwargs,
    )


def powertrain_parts(hardware):
    design, library = hardware
    config = design.powertrain
    spec = library.battery(config.battery_id)
    prop = library.propeller(config.propeller_id)
    dataset = PowertrainDataset(library.motor(config.motor_id), prop.motor_test_data_key or prop.id)
    return spec, dataset


def take_flight(hardware, scenario, **kwargs):
    design, library = hardware
    return run_scenario(design, scenario, library, **kwargs)


def test_rotor_wrench_rigid_balance_and_power_identities(hardware):
    plant, _ = build_multirotor(hardware[0])
    state = make_state([0, 0, 0], [0, 0, 0], [1, 0, 0, 0], [0.3, -0.2, 0.4])
    force_residual = moment_residual = 0.0
    for thrusts in (np.array([7., 9., 11., 13.]), np.array([7., 0., 11., 13.])):
        force, torque = plant.net_force_torque(state, thrusts)
        positions = np.array([r.position_m for r in plant.rotors])
        spins = np.array([r.spin_direction for r in plant.rotors])
        expected_f = [0., 0., fsum(thrusts)]
        expected_m = np.array([
            positions[:, 1] @ thrusts, -positions[:, 0] @ thrusts,
            -plant.rotor_torque_per_thrust * (spins @ thrusts),
        ])
        force_residual = max(force_residual, max_error(force, expected_f))
        moment_residual = max(moment_residual, max_error(torque, expected_m))

    inertia = np.array([[2.1, 0.1, -0.2], [0.1, 2.4, 0.05], [-0.2, 0.05, 3.2]])
    body = RigidBody(4.3, inertia)
    force_body = np.array([4.0, -2.0, 7.0])
    torque_body = np.array([0.7, -0.4, 0.2])
    omega = np.array([0.7, -0.5, 1.2])
    velocity = np.array([2.0, 3.0, -0.5])
    state = make_state([0, 0, 0], velocity, [2**-0.5, 0, 0, 2**-0.5], omega)
    derivative = body.derivs(state, force_body, torque_body)
    # Independent signed permutation for the exact +90 degree z rotation.
    applied_world = np.array([2.0, 4.0, 7.0 - 4.3 * STANDARD_GRAVITY])
    force_residual = max(force_residual, max_error(4.3 * derivative[3:6], applied_world))
    moment_residual = max(moment_residual, max_error(
        inertia @ derivative[10:13] + np.cross(omega, inertia @ omega), torque_body,
    ))
    power_residual = abs(
        4.3 * (velocity @ derivative[3:6]) + omega @ inertia @ derivative[10:13]
        - (velocity @ applied_world + omega @ torque_body)
    )

    # Synthetic positive/negative CT knots, including a signed shaft-power case.
    knots = PlaneKnots(((0.3, 0.08, 0.05), (0.7, -0.02, -0.01)))
    axial = AxialPropellerModel(((4800.0, knots), (7200.0, knots)), 0.25,
                                AxialEnvelope(4800, 7200, 0.3, 0.7, "analytic fixture"))
    max_shaft_w = max_axial_n = 0.0
    for j, ct, cp in ((0.3, 0.08, 0.05), (0.7, -0.02, -0.01)):
        load = axial.evaluate(6000, j * 25, 1.2)
        expected_axial_force = 46.875 * ct
        expected_shaft_power = 1171.875 * cp
        max_axial_n = max(max_axial_n, abs(load.thrust_n - expected_axial_force))
        max_shaft_w = max(max_shaft_w, abs(load.power_w - expected_shaft_power),
                          abs(load.power_w - load.torque_n_m * (6000 * pi / 30)))
    _, dataset = powertrain_parts(hardware)
    voltage = 22.2
    rpm = 4800.0
    bus_power_residual = abs(dataset.power_w(rpm, voltage).value - voltage * dataset.current_a(rpm, voltage).value)
    print("wrench N/Nm, rigid W, axial N/shaft W, branch VI W:",
          force_residual, moment_residual, power_residual, max_axial_n, max_shaft_w, bus_power_residual)
    assert max(force_residual, max_axial_n) <= FORCE_N
    assert moment_residual <= MOMENT_NM
    assert max(power_residual, max_shaft_w, bus_power_residual) <= MECHANICAL_POWER_W


def test_analytic_hover_and_drag_free_ballistic_trajectory(hardware):
    plant, _ = build_multirotor(hardware[0])
    plant.drag = None
    state = make_state([0.0, 0.0, 2.0], [0., 0., 0.], [1., 0., 0., 0.], [0., 0., 0.])
    trim = plant.hover_trim()
    _, hovering = integrate_fixed(
        lambda t, x: plant.derivs(x, trim), state, 0, 0.5, 1/256, normalize_state,
    )
    time, falling = integrate_fixed(
        lambda t, x: plant.derivs(x, np.zeros_like(trim)), state, 0, 0.5, 1/256, normalize_state,
    )
    expected = np.tile(state, (len(time), 1))
    expected[:, 2] -= STANDARD_GRAVITY * time**2 / 2
    expected[:, 5] -= STANDARD_GRAVITY * time
    errors = max_error(hovering, state), max_error(falling, expected)
    print("analytic hover/fall state residual (SI by channel):", errors)
    assert max(errors) <= ANALYTIC_STATE


@pytest.mark.parametrize("case", ["maneuver", "thermal-stop"])
def test_charge_and_energy_integrate_only_the_electrical_interval(hardware, case):
    spec, _ = powertrain_parts(hardware)
    extra = {1: BranchLimits(series_resistance_ohm=0.03)}
    if case == "thermal-stop":
        extra[1] = replace(extra[1], thermal_current_a=1.0, thermal_duration_s=0.006)
    scenario = maneuver(branch_limits=extra) if case == "maneuver" else hover(0.012, branch_limits=extra)
    result = take_flight(hardware, scenario)
    hours = (result.clock.electrical_time_s - result.times) / 3600
    seconds = hours * 3600
    if case == "thermal-stop":
        assert result.abort_event.kind == "branch_thermal_limit"
        assert result.clock.electrical_time_s[-1] == 0.006
        np.testing.assert_array_equal(seconds, [0.004, 0.002])
        assert result.clock.state_time_s[-1] == 0.004
    else:
        assert result.clock.integrated.all()

    i_branch = result.per_motor_current_a
    amps = np.sum(i_branch, axis=1)
    charge = np.cumsum(amps * seconds)
    soc_charge = (100.0 - result.soc_pct) * (spec.capacity_ah * 36)
    charge_residual = max_error(charge, soc_charge)
    assert charge_residual <= CHARGE_C

    battery = BatteryPack(spec)
    ocv = np.array([battery.ocv_pack(s) for s in np.r_[100., result.soc_pct[:-1]]])
    v_drop = amps * spec.internal_resistance_ohm
    bus_kvl = max_error(ocv - v_drop, result.v_bus)
    assert bus_kvl <= BUS_RESIDUAL_V
    stored_j = fsum(ocv * amps * seconds)
    loss_j = fsum(v_drop * amps * seconds)
    exact_bus_j = fsum((ocv - v_drop) * amps * seconds)
    exact_residual_j = abs(stored_j - loss_j - exact_bus_j)
    reported_bus_j = result.energy_wh * 3600
    integration_residual_j = abs(reported_bus_j - fsum(result.v_bus * amps * seconds))
    solver_residual_j = abs(stored_j - loss_j - reported_bus_j)
    solver_budget_j = BUS_RESIDUAL_V * charge[-1] + ENERGY_ROUNDOFF_J
    r_branch = np.array([0.0, 0.03, 0.0, 0.0])
    wire_kvl = max_error(result.v_bus[:, None] - i_branch * r_branch, result.branch_voltage_v)
    branch_j = fsum(np.sum(i_branch * (result.branch_voltage_v + i_branch * r_branch), axis=1) * seconds)
    wire_residual_j = abs(branch_j - reported_bus_j)
    assert wire_kvl <= WIRE_RESIDUAL_V
    assert wire_residual_j <= WIRE_RESIDUAL_V * charge[-1] + ENERGY_ROUNDOFF_J
    assert max(exact_residual_j, integration_residual_j) <= ENERGY_ROUNDOFF_J
    assert solver_residual_j <= solver_budget_j
    print(case, "charge/resid C:", charge[-1], charge_residual,
          "OCV/bus/loss J:", stored_j, reported_bus_j, loss_j,
          "exact/integrated/solver/budget/wire residual J:", exact_residual_j,
          integration_residual_j, solver_residual_j, solver_budget_j, wire_residual_j,
          "max bus/wire KVL V:", bus_kvl, wire_kvl)


def godot_quaternion_adapter():
    scene = (ROOT / "apps/desktop/main.gd").read_text(encoding="utf-8")
    constructors = re.findall(r"Quaternion\(([^\n]+)\)", scene)
    terms = []
    for constructor in constructors:
        columns = re.findall(r"(-?)float\(q\d*\[(\d)\]\)", constructor)
        if columns:
            assert len(columns) == 4
            terms.append(tuple((-1 if sign else 1, int(i)) for sign, i in columns))
    assert len(terms) == 3 and len(set(terms)) == 1
    return terms[0]


def test_randomized_hamilton_frames_and_actual_godot_adapter_mapping():
    rng = np.random.default_rng(SEED)
    godot = np.array([[1., 0., 0.], [0., 0., 1.], [0., -1., 0.]])
    ned_enu = np.array([[0., 1., 0.], [1., 0., 0.], [0., 0., -1.]])
    frd_flu = np.diag([1., -1., -1.])
    adapter = godot_quaternion_adapter()
    axes = np.eye(3)
    quats = [normalize(q) for q in rng.normal(size=(1024, 4))]
    quats += [np.array([1., 0., 0., 0.]), *(from_axis_angle(b, pi) for b in axes),
              *(from_axis_angle(axes[1], sign * (pi/2 - 1e-12)) for sign in (-1, 1))]
    frame_error = 0.0
    for q in quats:
        v = rng.normal(size=3)
        r = rotation_matrix(q)
        # SciPy is an independent implementation of active rotations.
        world_reference = Rotation.from_quat(q[[1, 2, 3, 0]]).apply(v)
        projected = rotate(q, v)
        xyzw = np.array([sign * q[i] for sign, i in adapter])
        qg = xyzw[[3, 0, 1, 2]]
        q_back = np.r_[qg[0], godot.T @ qg[1:]]
        frame_error = max(
            frame_error, max_error(projected, world_reference), max_error(rotate_inverse(q, projected), v),
            max_error(rotate(-q, v), projected), max_error(rotation_matrix(-q), r),
            max_error(r.T @ r, np.eye(3)), abs(np.linalg.det(r) - 1.0),
            max_error(rotation_matrix(qg), godot @ r @ godot.T),
            max_error(rotate(qg, godot @ v), godot @ projected), max_error(q_back, q),
            max_error((ned_enu @ r @ frd_flu.T) @ (frd_flu @ v), ned_enu @ projected),
        )
    print("quaternion seed/cases/worst component residual:", SEED, len(quats), frame_error)
    assert frame_error <= FRAME


@pytest.mark.parametrize("q", [
    (2., 0., 0., 0.), (0., 0., 0., 0.), (0.9999, 0., 0., 0.),
    (float("nan"), 0., 0., 1.), (0., float("inf"), 0., 1.), (0., 0., float("-inf"), 1.),
])
def test_external_quaternion_boundary_rejects_nonunit_and_nonfinite(q):
    with pytest.raises(ValidationError):
        AssemblyNode(id="node", name="body", orientation_wxyz=q)
    if not np.all(np.isfinite(q)):
        with pytest.raises(ValueError, match="non-finite quaternion"):
            make_state([0., 0., 0.], [0., 0., 0.], q, [0., 0., 0.])
        with pytest.raises(ValueError, match="non-finite quaternion"):
            rotation_matrix(q)


def total_charge(result, capacity_ah):
    return (100. - result.soc_pct[-1]) * capacity_ah * 36


def test_three_level_coupled_convergence_against_finer_reference(hardware, monkeypatch):
    _, library = hardware
    spec, _ = powertrain_parts(hardware)
    spec = spec.model_copy(update={"internal_resistance_ohm": 0.08})
    monkeypatch.setattr(library, "battery", lambda _: spec)
    schedule = maneuver()
    periods = (0.016, 0.008, 0.004)
    reference = take_flight(hardware, schedule, control_dt_s=0.002)
    assert not reference.aborted
    errors = []
    for dt in periods:
        run = take_flight(hardware, schedule, control_dt_s=dt)
        assert not run.aborted
        stride = round(dt / 0.002)
        np.testing.assert_array_equal(run.clock.state_time_s, reference.clock.state_time_s[stride-1::stride])
        rs = reference.states[stride-1::stride]
        position = np.linalg.norm(run.states[:, :3] - rs[:, :3], axis=1).max()
        q, qr = run.states[:, 6:10], rs[:, 6:10]
        chord = np.minimum(np.linalg.norm(q - qr, axis=1), np.linalg.norm(q + qr, axis=1))
        attitude = (4 * np.arcsin(np.clip(chord / 2, 0, 1))).max()
        energy = abs(run.energy_wh - reference.energy_wh) * 3600
        charge = abs(total_charge(run, spec.capacity_ah) - total_charge(reference, spec.capacity_ah))
        errors.append([position, attitude, energy, charge])
        print("convergence dt, pos m, attitude rad, energy J, charge C:", dt, *errors[-1])
    errors = np.array(errors)
    assert np.all(np.diff(errors, axis=0) < 0)
    assert np.all(errors[-1] <= FINE_LIMITS)


def run_digest(run):
    digest = sha256()
    names = ("times", "states", "thrusts", "per_motor_current_a", "v_bus", "soc_pct",
             "attainable_thrust_n", "branch_voltage_v", "per_motor_rpm", "wrench_residual")
    for array in [*(getattr(run, name) for name in names),
                  *(getattr(run.clock, f.name) for f in fields(run.clock))]:
        digest.update(array.tobytes())
    digest.update(json.dumps({
        "events": [asdict(event) for event in run.events],
        "energy_hex": run.energy_wh.hex(), "flight_verdict": run.flight_verdict,
        "verdicts": run.component_verdicts, "allocation": run.allocation_counts,
        "success_all": run.success_all,
    }, sort_keys=True, allow_nan=False).encode())
    return digest.hexdigest()


def test_seeded_healthy_and_failed_runs_repeat_bit_for_bit(hardware):
    sensor = SensorConfig(seed=SEED, latency_s=0.008, sigma_rate_deg_s=0.12,
                          sigma_attitude_deg=0.05, sigma_position_m=0.001)
    base = maneuver(sensor_config=sensor)
    for scenario, verdict in (
        (base, "NO_MODELED_LIMIT_BREACHED"),
        (replace(base, branch_failure=BranchFailure(2, 0.32, "esc_cutout")), "FAIL"),
    ):
        a, b = (take_flight(hardware, scenario) for _ in range(2))
        assert a.flight_verdict == b.flight_verdict == verdict
        assert a.energy_wh.hex() == b.energy_wh.hex()
        assert run_digest(a) == run_digest(b)
        assert run_digest(a) != run_digest(take_flight(
            hardware, replace(scenario, sensor_config=replace(sensor, seed=SEED + 1)),
        ))
        print("repeatability:", verdict, run_digest(a), a.energy_wh.hex())


@pytest.mark.parametrize(("limit", "trace", "component", "event", "minimum"), [
    ("max_current_a", "per_motor_current_a", "esc", "branch_current", False),
    ("min_voltage_v", "branch_voltage_v", "esc", "branch_undervoltage", True),
    ("max_voltage_v", "branch_voltage_v", "esc", "branch_overvoltage", False),
    ("max_rpm", "per_motor_rpm", "motor", "rotor_rpm", False),
    ("max_thrust_n", "thrusts", "actuator", "actuator_thrust", False),
])
def test_branch_strict_limits_at_adjacent_floats(hardware, limit, trace, component, event, minimum):
    branch = 1
    base = take_flight(hardware, hover())
    observed = float(getattr(base, trace)[0, branch])
    for side in (-1, 0, 1):
        threshold = observed if side == 0 else np.nextafter(observed, side * np.inf)
        result = take_flight(hardware, hover(branch_limits={branch: BranchLimits(**{limit: threshold})}))
        expect_failure = side == (1 if minimum else -1)
        assert result.aborted is expect_failure
        if expect_failure:
            finding, = result.component_verdicts[f"{component}:1"]["findings"]
            assert result.flight_verdict == "FAIL" and result.abort_event.kind == event
            assert (finding["branch_id"], finding["limit"], finding["t_s"],
                    finding["observed"], finding["threshold"]) == (branch, event, 0.0, observed, threshold)
            assert not result.clock.integrated.any()


def test_thermal_pickup_and_dwell_at_adjacent_floats(hardware):
    branch = 1
    observed = float(take_flight(hardware, hover()).per_motor_current_a[0, branch])
    for side in (-1, 0, 1):
        threshold = observed if side == 0 else np.nextafter(observed, side * np.inf)
        result = take_flight(hardware, hover(
            branch_limits={branch: BranchLimits(thermal_current_a=threshold, thermal_duration_s=DT)}
        ))
        assert result.aborted is (side < 0)
        if result.aborted:
            assert result.abort_event.t_s == DT

    # The old repeated dt addition drifted even across representable neighbors
    # of the 19th authoritative tick and incorrectly failed the above case.
    end = 19 * DT
    for side in (-1, 0, 1):
        deadline = end if side == 0 else np.nextafter(end, side * np.inf)
        result = take_flight(hardware, hover(
            end, branch_limits={branch: BranchLimits(thermal_current_a=1.0, thermal_duration_s=deadline)},
        ))
        assert result.aborted is (side <= 0)
        if result.aborted:
            assert result.flight_verdict == "FAIL" and result.abort_event.kind == "branch_thermal_limit"
            finding, = result.component_verdicts["esc:1"]["findings"]
            assert finding["t_s"] == result.abort_event.t_s == deadline


@pytest.mark.parametrize("kind", ["winding_short_drag", "blade_breakup", "fault_tolerant_reallocation"])
def test_unknown_fault_resume_guard_at_exact_tick(hardware, kind):
    for side in (-1, 0, 1):
        request = DT if side == 0 else np.nextafter(DT, side * np.inf)
        result = take_flight(hardware, hover(3 * DT, branch_failure=BranchFailure(1, request, kind)))
        assert result.flight_verdict == "INCONCLUSIVE" and result.success_all is False
        finding, = result.component_verdicts["actuator:1"]["findings"]
        expected = DT if side <= 0 else 2 * DT
        assert result.abort_event.t_s == finding["t_s"] == expected
        assert result.clock.state_time_s[-1] == expected
        assert len(result.clock.command_wrench) == (1 if side <= 0 else 2)
