"""Scenario service: the canonical run_* functions shared by the CLI
(scripts/run_simulation.py) and the API simulation service.

Each function takes a validated design snapshot (+ parameters) and returns a
report dict with sections: scenario / design / results / trustworthiness —
plus a ``telemetry`` block (decimated time series) for plotting.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from aeroforge_schemas.design import DroneDesign
from physics import __version__ as physics_version
from physics.constants import STANDARD_GRAVITY
from physics.controller.attitude import ControlTargets, QuadcopterController
from physics.controller.mixer import Mixer
from physics.controller.simulation import Disturbance, run_controlled_simulation
from physics.dynamics.design_adapter import build_multirotor
from physics.dynamics.quaternion import rotation_matrix
from physics.dynamics.rigid_body import make_state, normalize_state, unpack_state
from physics.integration.rk4 import integrate_fixed
from physics.integration.scipy_solver import integrate_ivp
from physics.propulsion.battery import BatteryPack
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.esc import Esc
from physics.propulsion.loader import ComponentLibrary
from physics.propulsion.powertrain import StaticPowertrain
from physics.scenarios.runner import Scenario, run_scenario
from physics.validation.benchmarks import run_propulsion_benchmarks

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data"
MAX_TELEMETRY_POINTS = 400
IDEAL_RK45_MAX_STEP_S = 0.05


def _default_library(data_dir: Path | None) -> ComponentLibrary:
    return ComponentLibrary((data_dir or DEFAULT_DATA_DIR) / "components")


def _decimate(values: np.ndarray, max_points: int = MAX_TELEMETRY_POINTS) -> np.ndarray:
    n = len(values)
    if n <= max_points:
        return values
    idx = np.linspace(0, n - 1, max_points).astype(int)
    return values[idx]


def _states_telemetry(times, states, thrusts, currents=None, v_bus=None, soc=None,
                      alt_cmd=None) -> dict:
    idx = _decimate(np.arange(len(times)))
    t = np.asarray(times)[idx]
    s = np.asarray(states)[idx]
    out: dict = {
        "t": t.tolist(),
        "x": s[:, 0].tolist(),
        "y": s[:, 1].tolist(),
        "z": s[:, 2].tolist(),
        "q_wxyz": s[:, 6:10].tolist(),
        "vz": s[:, 5].tolist(),
        "motor_thrusts_n": np.asarray(thrusts)[idx].tolist(),
    }
    if currents is not None:
        out["motor_current_a"] = np.asarray(currents)[idx].tolist()
    if v_bus is not None:
        out["v_bus_v"] = np.asarray(v_bus)[idx].tolist()
    if soc is not None:
        out["soc_pct"] = np.asarray(soc)[idx].tolist()
    if alt_cmd is not None:
        out["altitude_accel_cmd_m_s2"] = np.asarray(alt_cmd)[idx].tolist()
    return out


# --------------------------------------------------------------- M1: ideal


def run_hover_ideal(
    design: DroneDesign, duration_s: float = 2.0, dt_s: float = 0.002, solver: str = "rk4",
    *, max_evaluations: int | None = None,
) -> dict:
    """M1 stationary-hover verification with ideal actuators."""
    plant, mass = build_multirotor(design)
    trim = plant.hover_trim()

    x0 = make_state(
        r_world=np.zeros(3),
        v_world=np.zeros(3),
        q_bw=np.array([1.0, 0.0, 0.0, 0.0]),
        omega_body=np.zeros(3),
    )
    f = lambda t, x: plant.derivs(x, trim)  # noqa: E731

    if solver == "rk4":
        times, states = integrate_fixed(f, x0, 0.0, duration_s, dt_s, post_step=normalize_state)
    elif solver == "ivp":
        times, states = integrate_ivp(
            f, x0, 0.0, duration_s, post_step=normalize_state, max_step=IDEAL_RK45_MAX_STEP_S,
            max_evaluations=max_evaluations,
        )
    else:
        raise ValueError(f"unknown solver {solver!r}")

    max_net_accel = max(float(np.linalg.norm(f(t, x)[3:6])) for t, x in zip(times, states))
    r_final, v_final, _, _ = unpack_state(states[-1])
    return {
        "scenario": "hover-ideal (M1 dynamics verification)",
        "physics_version": physics_version,
        "design": {
            "name": design.name,
            "mass_kg": mass.mass_kg,
            "cog_m": mass.cog_m.tolist(),
            "principal_moments_kg_m2": mass.principal_moments.tolist(),
            "n_rotors": len(design.rotors),
        },
        "trim": {
            "per_rotor_thrust_n": trim.tolist(),
            "total_thrust_n": float(np.sum(trim)),
            "weight_n": mass.mass_kg * STANDARD_GRAVITY,
        },
        "integration": {"duration_s": duration_s, "dt_s": dt_s, "solver": solver,
                        "gravity_m_s2": STANDARD_GRAVITY},
        "results": {
            "final_altitude_m": float(r_final[2]),
            "horizontal_drift_m": float(np.hypot(r_final[0], r_final[1])),
            "final_speed_m_s": float(np.linalg.norm(v_final)),
            "max_net_acceleration_m_s2": max_net_accel,
        },
        "telemetry": _states_telemetry(times, states, np.tile(trim, (len(times), 1))),
        "trustworthiness": {
            "dynamics_core": {"status": "verified",
                              "evidence": "unit tests vs analytical solutions — tests/physics/"},
            "mass_properties": {"status": "verified",
                                "evidence": "parallel-axis assembly tests vs known cases"},
            "actuator_model": {"status": "idealized placeholder",
                               "caveat": "commanded thrust == delivered thrust; no motor/prop/"
                               "ESC/battery dynamics. Run hover-static/flight for the "
                               "sourced powertrain analysis."},
            "verdict": "M1 dynamics verification only — not a flight-worthiness claim",
        },
    }


# ------------------------------------------------------------ M2: static


def run_hover_static(design: DroneDesign, max_duration_s: float = 7200.0, dt_s: float = 10.0,
                     data_dir: Path | None = None) -> dict:
    """M2 static hover on the sourced powertrain: throttle/current/endurance."""
    if design.powertrain is None:
        raise ValueError("design has no powertrain block — ideal-actuator scenarios only")
    library = _default_library(data_dir)
    motor = library.motor(design.powertrain.motor_id)
    prop = library.propeller(design.powertrain.propeller_id)
    battery_spec = library.battery(design.powertrain.battery_id)
    esc_spec = library.esc(design.powertrain.esc_id)

    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    battery = BatteryPack(battery_spec)
    powertrain = StaticPowertrain(dataset, Esc(esc_spec), battery, units=len(design.rotors))

    _, mass_props = build_multirotor(design)
    total_mass = mass_props.mass_kg

    battery_part = next((p for p in design.parts if "battery" in p.name.lower()), None)
    consistency = "ok"
    if battery_part is not None and battery_spec.mass_kg is not None:
        rel = abs(battery_part.mass_kg - battery_spec.mass_kg) / battery_spec.mass_kg
        if rel > 0.25:
            raise ValueError(
                f"design battery part mass {battery_part.mass_kg} kg differs from "
                f"component spec {battery_spec.mass_kg} kg by {rel * 100:.0f}% — "
                "fix the design or the component entry"
            )
        elif rel > 1e-9:
            consistency = f"within {rel * 100:.1f}% of component spec"

    hover = powertrain.static_hover(total_mass, max_duration_s=max_duration_s, dt_s=dt_s)
    benchmarks = run_propulsion_benchmarks(dataset)

    estimated_components = []
    for label, spec in (("motor", motor), ("propeller", prop),
                        ("battery", battery_spec), ("esc", esc_spec)):
        if spec.source.estimated:
            estimated_components.append(label)
    if prop.mass_kg is None:
        estimated_components.append("propeller mass (unknown — user must supply)")

    samples = hover.samples
    tel_t = np.array([s.t_s for s in samples])
    tel = {
        "t": _decimate(tel_t).tolist(),
        "soc_pct": _decimate(np.array([s.soc_pct for s in samples])).tolist(),
        "v_bus_v": _decimate(np.array([s.v_bus for s in samples])).tolist(),
        "total_power_w": _decimate(np.array([s.total_power_w for s in samples])).tolist(),
        "total_current_a": _decimate(np.array([s.total_current_a for s in samples])).tolist(),
        "cell_voltage_v": _decimate(np.array([s.cell_voltage_loaded_v for s in samples])).tolist(),
    }

    return {
        "scenario": "hover-static (M2 sourced powertrain)",
        "physics_version": physics_version,
        "design": {
            "name": design.name,
            "mass_kg": total_mass,
            "cog_m": mass_props.cog_m.tolist(),
            "n_rotors": len(design.rotors),
            "powertrain": design.powertrain.model_dump(),
            "battery_mass_consistency": consistency,
        },
        "benchmarks": [
            {"name": b.name, "status": b.status, "metrics": b.metrics,
             "tolerances": b.tolerances, "notes": b.notes}
            for b in benchmarks
        ],
        "hover_point": {
            "throttle": hover.hover_point.throttle,
            "v_bus_v": hover.hover_point.v_bus,
            "per_rotor": {
                "thrust_n": hover.hover_point.per_unit.thrust_n,
                "rpm": hover.hover_point.per_unit.rpm,
                "current_a": hover.hover_point.per_unit.current_a,
                "power_w": hover.hover_point.per_unit.power_w,
                "envelope_flags": hover.hover_point.per_unit.flags,
            },
            "total_current_a": hover.hover_point.total_current_a,
            "total_power_w": hover.hover_point.total_power_w,
            "hover_power_w_per_kg": hover.hover_point.total_power_w / total_mass,
        },
        "endurance": {
            "to_warning_s": hover.endurance_to_warning_s,
            "to_cutoff_s": hover.endurance_to_cutoff_s,
            "energy_used_wh_at_warning": hover.energy_used_wh,
            "min_cell_voltage_v": hover.min_cell_voltage_v,
        },
        "limits": {
            "verdict": "FAIL" if hover.limit_issues else "INCONCLUSIVE",
            "issues": hover.limit_issues,
        },
        "telemetry": tel,
        "trustworthiness": {
            "propulsion_data": {
                "status": "measured bench data (model of record)",
                "source": dataset.provenance,
                "envelope": dataset.envelope(),
            },
            "hover_envelope_flags": hover.envelope_flags,
            "estimated_components": estimated_components,
            "controller_limits": {
                "status": "declared continuous DC branch current and available bus voltage rating",
                "caveat": "Thermal damage and transient overload capacity require hardware measurements.",
            },
            "battery_model": {
                "status": "first-order OCV + R model",
                "caveat": battery_spec.source.notes or "",
            },
            "static_only": {
                "caveat": "no forward-flight advance ratio, no wind, no controller "
                "dynamics (M3/M4), no thermal integration; endurance carries the "
                "battery estimates' uncertainty"
            },
            "verdict": "M2 static analysis on sourced bench data — NOT a "
            "flight-worthiness claim",
        },
    }


# ------------------------------------------------------- M3: closed loop


def _euler_deg_from_state(s: np.ndarray) -> tuple[float, float, float]:
    R = rotation_matrix(s[6:10])
    return (
        float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))),
        float(np.degrees(np.arcsin(np.clip(-R[2, 0], -1, 1)))),
        float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))),
    )


def run_hover_hold(design: DroneDesign, duration_s: float = 10.0,
                   control_dt_s: float = 0.004, data_dir: Path | None = None) -> dict:
    """M3 closed-loop hover: position/altitude hold with scheduled torque and
    force disturbances; reports peak attitude, settling, oscillation metrics."""
    plant, mass_props = build_multirotor(design)
    controller = QuadcopterController(plant)

    mixer_limit = None
    if design.powertrain is not None:
        library = _default_library(data_dir)
        motor = library.motor(design.powertrain.motor_id)
        prop = library.propeller(design.powertrain.propeller_id)
        dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
        rpm_hi = dataset.envelope()["rpm_range_merged"][1]
        mixer_limit = float(dataset.thrust_n(rpm_hi).value)
        controller.mixer = Mixer(plant, max_thrust_per_rotor_n=mixer_limit)

    targets = ControlTargets(altitude_m=1.0, position_xy=(0.0, 0.0))
    disturbances = [
        Disturbance(t_start=duration_s * 0.4, t_end=duration_s * 0.4 + 0.2,
                    torque_body=np.array([0.05, 0.0, 0.0])),
        Disturbance(t_start=duration_s * 0.6, t_end=duration_s * 0.6 + 0.5,
                    force_world=np.array([2.0, 0.0, 0.0])),
    ]
    res = run_controlled_simulation(
        plant, controller, targets, duration_s=duration_s,
        control_dt_s=control_dt_s, disturbances=disturbances,
    )

    rolls, pitches, yaws = np.array([_euler_deg_from_state(s) for s in res.states]).T
    tail_mask = res.times >= res.times[-1] - 2.0
    z_tail = res.states[tail_mask, 2]
    x_tail = res.states[tail_mask, 0]
    y_tail = res.states[tail_mask, 1]

    return {
        "scenario": "hover-hold (M3 closed loop)",
        "physics_version": physics_version,
        "design": {
            "name": design.name,
            "mass_kg": mass_props.mass_kg,
            "cog_m": mass_props.cog_m.tolist(),
            "n_rotors": len(design.rotors),
            "mixer_thrust_limit_n_per_rotor": mixer_limit,
        },
        "disturbances": [
            {"t_s": [d.t_start, d.t_end],
             "force_world_n": None if d.force_world is None else d.force_world.tolist(),
             "torque_body_nm": None if d.torque_body is None else d.torque_body.tolist()}
            for d in disturbances
        ],
        "results": {
            "peak_abs_roll_deg": float(np.abs(rolls).max()),
            "peak_abs_pitch_deg": float(np.abs(pitches).max()),
            "tail_altitude_error_m": float(np.abs(z_tail - 1.0).max()),
            "tail_altitude_std_m": float(np.std(z_tail)),
            "tail_position_error_m": float(max(np.abs(x_tail).max(), np.abs(y_tail).max())),
            "max_motor_thrust_n": float(res.thrusts.max()),
            "oscillation": "persistent" if float(np.std(z_tail)) > 0.02 else "none detected",
        },
        "allocation_control_steps": controller.allocation_counts.copy(),
        "telemetry": _states_telemetry(res.times, res.states, res.thrusts,
                                       alt_cmd=res.alt_commands),
        "trustworthiness": {
            "controller": {
                "status": "deterministic closed loop, perfect state knowledge",
                "caveat": "no sensor noise/latency in this scenario; ideal "
                "actuators (thrust commands delivered instantly, bounded by the "
                "dataset max when a powertrain is attached)",
            },
            "gains": {
                "status": "derived from assembled mass/inertia",
                "evidence": "ControlGains.for_plant(); hover/disturbance acceptance "
                "tests in tests/physics/test_controller.py",
            },
            "verdict": "M3 stability verification only — not a flight-worthiness claim",
        },
    }


# ------------------------------------------------------ M4: flight scenario


def run_flight(design: DroneDesign, data_dir: Path | None = None) -> dict:
    """M4 full mission: takeoff -> climb to 5 m -> hold -> land, with the
    sourced powertrain in the loop."""
    if design.powertrain is None:
        raise ValueError("flight scenario needs a powertrain block (sourced powertrain)")
    library = _default_library(data_dir)

    scenario = Scenario(
        name="flight_takeoff_hover_land",
        duration_s=18.0,
        altitude_waypoints=[
            (0.0, 0.0), (1.5, 3.75), (2.5, 5.0),
            (10.0, 5.0),
            (15.0, 0.0), (18.0, 0.0),
        ],
        success_criteria=[
            ("reached_5m", lambda v: v.time_to_altitude_s is not None),
            ("gentle_landing", lambda v: abs(v.states[-1, 2]) < 0.10
             and abs(v.states[-1, 5]) < 1.0),
            ("no_critical_failure", lambda v: not any(e.critical for e in v.events)),
        ],
    )
    res = run_scenario(design, scenario, library)
    _, mass_props = build_multirotor(design)

    max_current = (float(np.nanmax(res.per_motor_current_a))
                   if res.per_motor_current_a is not None else None)
    min_soc = float(res.soc_pct.min()) if res.soc_pct is not None else None
    if res.structural_margin_min is None:
        structure = {"status": "INCONCLUSIVE", "caveat": "No frame bending margin is available for this run."}
    elif res.structural_margin_min < 1.0:
        structure = {"status": "FAIL", "caveat": "Rotor-arm bending stress exceeded the modeled material limit."}
    else:
        structure = {
            "status": "INCONCLUSIVE",
            "caveat": "Rotor-arm bending stayed within the modeled material limit. Axial compression, "
                      "buckling, joints, fatigue and installed-frame strength require separate evidence.",
        }
    return {
        "scenario": "flight (M4 takeoff-hover-land, powertrain in the loop)",
        "physics_version": physics_version,
        "design": {
            "name": design.name,
            "mass_kg": mass_props.mass_kg,
            "cog_m": mass_props.cog_m.tolist(),
            "n_rotors": len(design.rotors),
            "powertrain": design.powertrain.model_dump(),
            "frame": design.frame.model_dump() if design.frame else None,
        },
        "mission": {
            "profile": "takeoff -> 5 m hold -> land",
            "duration_s": float(res.times[-1]) if len(res.times) else 0.0,
            "aborted": res.aborted,
            "verdict": res.flight_verdict,
            "success_all": res.success_all,
            "abort_event": res.abort_event.message if res.abort_event else None,
        },
        "component_verdicts": res.component_verdicts,
        "results": {
            "time_to_5m_s": res.time_to_altitude_s,
            "max_altitude_m": res.max_altitude_m,
            "energy_used_wh": res.energy_wh,
            "max_motor_current_a": max_current,
            "final_soc_pct": min_soc,
            "final_altitude_m": float(res.states[-1, 2]),
            "final_vertical_speed_m_s": float(res.states[-1, 5]),
            "structural_margin_min": res.structural_margin_min,
        },
        "events": [
            {"t_s": e.t_s, "kind": e.kind, "critical": e.critical, "message": e.message}
            for e in res.events
        ],
        "success": res.success,
        "allocation_control_steps": res.allocation_counts,
        "model_notes": res.notes,
        "telemetry": _states_telemetry(
            res.times, res.states, res.thrusts,
            currents=res.per_motor_current_a, v_bus=res.v_bus, soc=res.soc_pct,
        ),
        "trustworthiness": {
            "structure": structure,
            "powertrain": {
                "status": "sourced bench data in the loop (model of record)",
                "caveat": "quasi-static branch voltage limits attainable static thrust. "
                "Thermal dwell uses the motor's declared current/duration rating. "
                "Below-table thrust points are declared extrapolations.",
            },
            "failure_policy": {
                "status": "declared in physics/scenarios/runner.py",
                "caveat": "Hard limits abort at their recorded tick or in-tick crossing. "
                "A supported cutout records branch FAIL and exercises the existing "
                "controller against the disabled actuator. Unsupported behavior "
                "terminates as INCONCLUSIVE. Healthy telemetry records "
                "NO_MODELED_LIMIT_BREACHED within the modeled scope.",
            },
            "controller": {
                "status": "deterministic closed loop, perfect state knowledge",
                "caveat": "sensor noise/latency available via SensorConfig but "
                "disabled in this run",
            },
            "verdict": "M4 mission simulation — NOT a flight-worthiness claim",
        },
    }


def design_preview(design: DroneDesign) -> dict:
    """Mass properties + principal axes + trim feasibility for the editor."""
    plant, mass = build_multirotor(design)
    try:
        trim = plant.hover_trim().tolist()
        trim_error = None
    except ValueError as exc:
        trim, trim_error = None, str(exc)
    return {
        "mass_kg": mass.mass_kg,
        "cog_m": mass.cog_m.tolist(),
        "inertia_kg_m2": mass.inertia_about_cog.tolist(),
        "principal_moments_kg_m2": mass.principal_moments.tolist(),
        "principal_axes": mass.principal_axes.tolist(),
        "hover_trim_thrusts_n": trim,
        "hover_trim_error": trim_error,
        "n_rotors": len(design.rotors),
    }
