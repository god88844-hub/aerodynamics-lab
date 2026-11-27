"""P0A-023 & P0A-025: Single double-precision authoritative desktop simulation runner with recorded fidelity and budgets."""

from __future__ import annotations

from hashlib import sha256
import math
import time
from typing import Any

import numpy as np

from aeroforge_schemas.project import EngineeringProject, LegacyMultirotorVehicle
from app.services.run_provenance import capture_provenance
from desktop_worker.environment_authoring import TestGroundSpec, validate_supported_environment
from desktop_worker.twin_comparison import compute_dual_digital_twin_metrics
from physics.aerodynamics.drag import AirframeDrag
from physics.constants import GF_TO_N, SEA_LEVEL_AIR_DENSITY, STANDARD_GRAVITY
from physics.dynamics.design_adapter import build_multirotor
from physics.dynamics.quaternion import normalize
from physics.dynamics.quadrotor import MultirotorPlant, Rotor
from physics.dynamics.rigid_body import RigidBody, make_state, normalize_state
from physics.environment.adverse_weather import (
    evaluate_icing_and_shedding,
    evaluate_rain_wet_effects,
    evaluate_spatial_turbulence,
)
from physics.integration.rk4 import rk4_step
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.loader import ComponentLibrary

R_SPECIFIC_DRY_AIR = 287.058
COMPONENTS_DIR = __import__("pathlib").Path(__file__).resolve().parents[3] / "data" / "components"


def _resolve_max_total_thrust_n(motor_id: str | None, prop_id: str | None, n_rotors: int) -> float:
    if motor_id and prop_id and COMPONENTS_DIR.is_dir():
        lib = ComponentLibrary(COMPONENTS_DIR)
        motor = lib.motor(motor_id)
        prop = lib.propeller(prop_id)
        ds = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
        per_rotor_max = float(max(float(np.max(p.thrust_gf)) * GF_TO_N for p in ds.planes))
        return per_rotor_max * max(1, n_rotors)
    return max(4.0, n_rotors * 14.0)


def _extract_plant_and_limits(project: EngineeringProject) -> tuple[MultirotorPlant, dict[str, Any], list[str]]:
    params = dict(project.experiment.parameters or {})
    unverified: list[str] = []

    tg_raw = params.get("test_ground")
    if isinstance(tg_raw, dict):
        tg = TestGroundSpec.model_validate(tg_raw)
        validate_supported_environment(tg)
        wind = np.array(tg.wind_world_m_s, dtype=float)
        rho = float(tg.pressure_pa) / (R_SPECIFIC_DRY_AIR * float(tg.temperature_k))
    else:
        wind = np.array(project.environment.wind_world_m_s, dtype=float)
        rho = float(project.environment.pressure_pa) / (R_SPECIFIC_DRY_AIR * float(project.environment.temperature_k))

    layout_bom = params.get("layout_bom")
    if isinstance(layout_bom, dict) and layout_bom.get("mass_properties") and layout_bom.get("rotors"):
        mp = layout_bom["mass_properties"]
        body = RigidBody(
            mass_kg=float(mp["mass_kg"]),
            inertia_about_cog=np.array(mp["inertia_about_cog_kg_m2"], dtype=float),
        )
        cog = np.array(mp["cog_m"], dtype=float)
        rotors = [
            Rotor(position_m=np.array(r["position_m"], dtype=float) - cog, spin_direction=int(r.get("spin_direction", 1)))
            for r in layout_bom["rotors"]
        ]
        pt = layout_bom.get("powertrain") or {}
        max_thrust_total = _resolve_max_total_thrust_n(pt.get("motor_id"), pt.get("propeller_id"), len(rotors))
        if layout_bom.get("unverified_bom_items"):
            unverified.extend(str(item) for item in layout_bom["unverified_bom_items"])
        plant = MultirotorPlant(
            body=body,
            rotors=rotors,
            drag=AirframeDrag(cd_a_m2=0.06, rho_kg_m3=rho),
            rotor_torque_per_thrust=0.015,
            wind_world=wind,
        )
        limits = {"max_total_thrust_n": max_thrust_total, "min_bus_voltage_v": 19.2, "structural_margin_min": 2.0}
        return plant, limits, unverified

    if isinstance(project.vehicle, LegacyMultirotorVehicle):
        design = project.vehicle.snapshot
        base_plant, _ = build_multirotor(design)
        cd_a = float(base_plant.drag.cd_a_m2) if base_plant.drag is not None else 0.05
        max_total_thrust_n = _resolve_max_total_thrust_n(
            design.powertrain.motor_id if design.powertrain else None,
            design.powertrain.propeller_id if design.powertrain else None,
            len(base_plant.rotors),
        )
        plant = MultirotorPlant(
            body=base_plant.body,
            rotors=base_plant.rotors,
            drag=AirframeDrag(cd_a_m2=cd_a, rho_kg_m3=rho),
            rotor_torque_per_thrust=base_plant.rotor_torque_per_thrust,
            wind_world=wind,
        )
        limits = {"max_total_thrust_n": max_total_thrust_n, "min_bus_voltage_v": 19.2, "structural_margin_min": 2.0}
        return plant, limits, unverified

    raise ValueError("Unsupported vehicle for simulation: attach layout_bom or use a multirotor design")


def _mission_altitude_target(t_s: float, phases: list[dict[str, Any]], initial_z: float) -> float:
    if not phases:
        return initial_z
    elapsed = 0.0
    prev_z = initial_z
    for phase in phases:
        dur = float(phase.get("duration_s", 1.0))
        target = float(phase.get("target_altitude_m", prev_z))
        if t_s <= elapsed + dur:
            frac = max(0.0, min(1.0, (t_s - elapsed) / dur)) if dur > 0 else 1.0
            return prev_z + frac * (target - prev_z)
        elapsed += dur
        prev_z = target
    return prev_z


def run_authoritative_desktop_simulation(
    project_or_dict: EngineeringProject | dict[str, Any],
    *,
    dt_s: float | None = None,
    wall_budget_s: float = 30.0,
    step_budget: int = 20_000,
) -> dict[str, Any]:
    """Run one double-precision RK4 integrator driving all desktop & offline telemetry."""
    started_perf = time.perf_counter()
    if wall_budget_s <= 0 or not math.isfinite(wall_budget_s):
        raise ValueError("wall_budget_s must be finite and > 0")
    if step_budget < 1:
        raise ValueError("step_budget must be >= 1")

    project = (
        EngineeringProject.model_validate_json(project_or_dict.canonical_bytes())
        if isinstance(project_or_dict, EngineeringProject)
        else EngineeringProject.model_validate(project_or_dict)
    )
    provenance = capture_provenance()
    params = dict(project.experiment.parameters or {})
    mission = params.get("mission") if isinstance(params.get("mission"), dict) else None

    requested_dt_s = float(dt_s if dt_s is not None else (mission.get("controller_dt_s", 0.004) if mission else 0.004))
    if requested_dt_s <= 0 or not math.isfinite(requested_dt_s):
        raise ValueError("dt_s must be finite and > 0")

    phases = list(mission.get("phases", [])) if mission else []
    duration_s = float(sum(float(p.get("duration_s", 0.0)) for p in phases)) if phases else float(params.get("duration_s", 1.0))
    if duration_s <= 0 or not math.isfinite(duration_s):
        raise ValueError("Simulation duration must be > 0")

    steps = max(1, math.ceil(duration_s / requested_dt_s - 1e-12))
    if steps > step_budget:
        raise ValueError(f"step_budget_exceeded: requested {steps} steps > step_budget {step_budget}")

    plant, limits, unverified = _extract_plant_and_limits(project)
    base_wind = plant.wind_world.copy()
    wx_spec = params.get("adverse_weather") if isinstance(params.get("adverse_weather"), dict) else None
    wx_gusts = None
    wx_mass_penalty_kg = 0.0
    wx_drag_mult = 1.0
    wx_thrust_cap_scale = 1.0
    wx_summary: dict[str, Any] | None = None
    if wx_spec is not None:
        turb = evaluate_spatial_turbulence(
            altitude_m=10.0,
            mean_wind_10m_m_s=(float(base_wind[0]), float(base_wind[1]), float(base_wind[2])),
            turbulence_intensity=float(wx_spec.get("turbulence_intensity", 0.15)),
            seed=int(params.get("seed", project.experiment.seed)),
            n_samples=64,
        )
        rain = evaluate_rain_wet_effects(rain_mm_h=float(wx_spec.get("rain_mm_h", 0.0)))
        icing = evaluate_icing_and_shedding(
            oat_c=float(wx_spec.get("oat_c", 15.0)),
            lwc_g_m3=float(wx_spec.get("lwc_g_m3", 0.0)),
            exposure_s=float(wx_spec.get("icing_exposure_s", 0.0)),
        )
        wx_gusts = np.array(turb["gust_samples_m_s"], dtype=float)
        wx_mass_penalty_kg = float(icing["accreted_mass_kg"])
        wx_drag_mult = float(icing["drag_multiplier"]) * (1.0 + 2.5 * (rain["wet_cd0"] - 0.025))
        wx_thrust_cap_scale = max(0.65, rain["wet_cl_max"] / 1.45)
        if plant.drag is not None:
            plant.drag = AirframeDrag(cd_a_m2=plant.drag.cd_a_m2 * wx_drag_mult, rho_kg_m3=plant.drag.rho_kg_m3)
        plant.body = RigidBody(mass_kg=plant.body.mass_kg + wx_mass_penalty_kg, inertia_about_cog=plant.body.inertia_about_cog)
        wx_summary = {"rain": rain, "icing": icing, "turbulence_seed": turb["seed"], "caveat_status": "SUPPORTED_WITH_CAVEATS"}
        if icing.get("verdict") == "FAIL":
            unverified.append("SEVERE_ICE_ACCRETION_LIMIT")

    rho_scale = (plant.drag.rho_kg_m3 / SEA_LEVEL_AIR_DENSITY) if plant.drag is not None else 1.0
    seed = int(mission.get("seed", project.experiment.seed) if mission else project.experiment.seed)
    noise_std = float(mission.get("sensor_noise_z_std_m", 0.0) if mission else 0.0)
    rng = np.random.default_rng(np.random.PCG64(seed))

    n_rotors = len(plant.rotors)
    hover_trim = plant.hover_trim(STANDARD_GRAVITY)
    max_per_rotor_n = (limits["max_total_thrust_n"] / max(1, n_rotors)) * rho_scale * wx_thrust_cap_scale
    initial_z = 2.0 if not phases else (float(phases[0].get("target_altitude_m", 2.0)) if phases[0].get("phase") == "hover" else 0.0)
    state = make_state(
        r_world=np.array([0.0, 0.0, initial_z], dtype=float),
        v_world=np.zeros(3, dtype=float),
        q_bw=np.array([1.0, 0.0, 0.0, 0.0], dtype=float),
        omega_body=np.zeros(3, dtype=float),
    )

    times = [0.0]
    states = [state.copy()]
    thrust_history = [hover_trim.copy()]
    voltage_history = [25.2]
    verdicts: dict[str, str] = {"propulsion": "NO_MODELED_LIMIT_BREACHED", "battery": "NO_MODELED_LIMIT_BREACHED"}
    abort_reason: str | None = None
    max_quat_drift = 0.0
    t = 0.0
    effective_dt = duration_s / steps
    kp_z = 3.5 * plant.body.mass_kg
    kd_z = 4.0 * plant.body.mass_kg

    for step_idx in range(steps):
        if time.perf_counter() - started_perf > wall_budget_s:
            abort_reason = f"wall_budget_exceeded: elapsed > {wall_budget_s}s"
            break
        if wx_gusts is not None:
            plant.wind_world = wx_gusts[step_idx % len(wx_gusts)]
        h = min(requested_dt_s, duration_s - t)
        effective_dt = h
        target_z = _mission_altitude_target(t, phases, initial_z)
        z_meas = float(state[2]) + (float(rng.normal(0.0, noise_std)) if noise_std > 0 else 0.0)
        vz = float(state[5])
        total_thrust_cmd = max(0.0, plant.body.mass_kg * STANDARD_GRAVITY + kp_z * (target_z - z_meas) - kd_z * vz)

        # Equal fraction scaled over nominal hover trim so lateral/vertical geometry stays consistent.
        scale = total_thrust_cmd / max(1e-9, float(np.sum(hover_trim)))
        thrust_cmd = np.clip(hover_trim * scale, 0.0, max_per_rotor_n * 2.0)

        if float(np.max(thrust_cmd)) > max_per_rotor_n:
            verdicts["propulsion"] = "FAIL"
            abort_reason = f"Propulsion thrust demand {float(np.max(thrust_cmd)):.2f} N exceeds density-scaled max {max_per_rotor_n:.2f} N"
            break

        # Simple causal pack sag proportional to total electrical current estimate.
        est_current_a = float(np.sum(thrust_cmd)) * 1.4
        v_bus = max(0.0, 25.2 - 0.05 * est_current_a - 0.015 * step_idx * h)
        if v_bus < limits["min_bus_voltage_v"]:
            verdicts["battery"] = "FAIL"
            abort_reason = f"Battery loaded bus voltage {v_bus:.2f} V dropped below cutoff {limits['min_bus_voltage_v']:.2f} V"
            break

        raw_next = rk4_step(lambda _t, x: plant.derivs(x, thrust_cmd, gravity=True), t, state, h)
        q_raw = raw_next[6:10]
        max_quat_drift = max(max_quat_drift, abs(float(np.linalg.norm(q_raw)) - 1.0))
        state = normalize_state(raw_next)
        state[6:10] = normalize(state[6:10])
        t = (step_idx + 1) * h if abs((step_idx + 1) * h - duration_s) > 1e-12 else duration_s
        times.append(t)
        states.append(state.copy())
        thrust_history.append(thrust_cmd.copy())
        voltage_history.append(v_bus)

    wall_elapsed_s = time.perf_counter() - started_perf
    states_arr = np.vstack(states)
    thrust_arr = np.vstack(thrust_history)

    # One single-step RK4 Richardson error proxy against half-step on last state/thrust.
    half = effective_dt * 0.5
    s_half = rk4_step(lambda _t, x: plant.derivs(x, thrust_arr[-1], gravity=True), t, state, half)
    s_half = rk4_step(lambda _t, x: plant.derivs(x, thrust_arr[-1], gravity=True), t + half, s_half, half)
    s_full = rk4_step(lambda _t, x: plant.derivs(x, thrust_arr[-1], gravity=True), t, state, effective_dt)
    num_err_est = float(np.linalg.norm(s_half[:6] - s_full[:6]) / 15.0)

    status = "failed" if abort_reason else ("inconclusive" if unverified else "completed")
    telemetry = {
        "t": [round(float(v), 9) for v in times],
        "x": states_arr[:, 0].tolist(),
        "y": states_arr[:, 1].tolist(),
        "z": states_arr[:, 2].tolist(),
        "vx": states_arr[:, 3].tolist(),
        "vy": states_arr[:, 4].tolist(),
        "vz": states_arr[:, 5].tolist(),
        "q_wxyz": states_arr[:, 6:10].tolist(),
        "omega_body_rad_s": states_arr[:, 10:13].tolist(),
        "motor_thrusts_n": thrust_arr.tolist(),
        "v_bus_v": voltage_history,
        "channel_provenance": {k: "calculated" for k in ("t", "x", "y", "z", "vx", "vy", "vz", "q_wxyz", "motor_thrusts_n", "v_bus_v")},
    }
    execution_fidelity = {
        "backend_id": "authoritative_rk4_double_precision",
        "integrator": "rk4_float64",
        "requested_dt_s": requested_dt_s,
        "effective_dt_s": effective_dt,
        "step_count": len(times) - 1,
        "step_budget": step_budget,
        "solver_rate_hz": round(1.0 / effective_dt, 3),
        "quaternion_max_norm_drift": max_quat_drift,
        "numerical_error_estimate": num_err_est,
        "wall_elapsed_s": round(wall_elapsed_s, 6),
        "wall_budget_s": wall_budget_s,
        "budget_within_limit": wall_elapsed_s <= wall_budget_s and (len(times) - 1) <= step_budget,
    }
    output = {
        "document_version": "1.0",
        "experiment_kind": "authoritative_desktop_simulation_1",
        "project": project.model_dump(mode="json"),
        "project_sha256": sha256(project.canonical_bytes()).hexdigest(),
        "model_environment": provenance,
        "physical_validation_status": "unvalidated",
        "adverse_weather_summary": wx_summary,
        "component_verdicts": verdicts,
        "unverified_parameters": unverified,
        "execution_fidelity": execution_fidelity,
        "result": {
            "status": status,
            "aborted": abort_reason is not None,
            "abort_reason": abort_reason,
            "final_position_m": states_arr[-1, 0:3].tolist(),
            "max_altitude_m": float(np.max(states_arr[:, 2])),
            "min_bus_voltage_v": float(min(voltage_history)),
            "telemetry": telemetry,
        },
    }
    output["dual_digital_twin"] = compute_dual_digital_twin_metrics(output)
    return output
