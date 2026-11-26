"""Deterministic mission, control-clock, disturbance, and seed authoring (P0A-022)."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

from aeroforge_schemas.project import EngineeringProject


class MissionPhase(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    phase: Literal["takeoff", "climb", "hover", "descent", "landing", "manual_command"]
    duration_s: FiniteFloat = Field(gt=0.0, le=3600.0)
    target_altitude_m: FiniteFloat = Field(ge=0.0, le=500.0)
    manual_throttle_norm: FiniteFloat | None = Field(default=None, ge=0.0, le=1.0)
    manual_pitch_rad: FiniteFloat = Field(default=0.0, ge=-0.78539816339, le=0.78539816339)


class MissionDisturbance(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    start_s: FiniteFloat = Field(ge=0.0)
    duration_s: FiniteFloat = Field(gt=0.0, le=600.0)
    force_world_n: tuple[FiniteFloat, FiniteFloat, FiniteFloat] = (0.0, 0.0, 0.0)


class MissionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    units: Literal["SI"] = "SI"
    time_base: Literal["simulation_clock_s"] = "simulation_clock_s"
    controller_dt_s: FiniteFloat = Field(default=0.01, gt=0.0005, le=0.1)
    sensor_sample_hz: FiniteFloat = Field(default=100.0, gt=1.0, le=2000.0)
    sensor_latency_s: FiniteFloat = Field(default=0.0, ge=0.0, le=0.5)
    sensor_noise_sigma_m: FiniteFloat = Field(default=0.0, ge=0.0, le=2.0)
    seed: int = Field(default=0, ge=0, le=2**32 - 1)
    phases: list[MissionPhase] = Field(min_length=1, max_length=64)
    disturbances: list[MissionDisturbance] = Field(default_factory=list, max_length=32)


def author_mission(project: EngineeringProject, mission_spec: dict[str, Any]) -> EngineeringProject:
    """Attach a validated mission plan, clocks, and seed to an EngineeringProject."""
    plan = MissionPlan.model_validate(mission_spec)
    params = dict(project.experiment.parameters)
    params["mission"] = plan.model_dump(mode="json")
    updated_exp = project.experiment.model_copy(
        update={"parameters": params, "seed": plan.seed}
    )
    return project.model_copy(update={"experiment": updated_exp})


def run_authored_mission(
    project: EngineeringProject,
    *,
    mass_kg: float = 1.5,
    render_fps_hint: float = 60.0,
) -> dict[str, Any]:
    """Execute an authored mission on a fixed simulation clock independent of render cadence."""
    if "mission" not in project.experiment.parameters:
        raise ValueError("project.experiment.parameters['mission'] is missing")
    if not math.isfinite(mass_kg) or mass_kg <= 0.0:
        raise ValueError("mass_kg must be finite and > 0")
    if not math.isfinite(render_fps_hint) or render_fps_hint <= 0.0:
        raise ValueError("render_fps_hint must be finite and > 0")

    plan = MissionPlan.model_validate(project.experiment.parameters["mission"])
    dt = float(plan.controller_dt_s)
    rng = np.random.default_rng(int(plan.seed))

    # Build piecewise target altitude + phase trace on exact simulation clock
    t_list: list[float] = [0.0]
    z_list: list[float] = [0.0]
    vz_list: list[float] = [0.0]
    z_meas_list: list[float] = [float(rng.normal(0.0, plan.sensor_noise_sigma_m)) if plan.sensor_noise_sigma_m > 0 else 0.0]
    phase_list: list[str] = [plan.phases[0].phase]
    cmd_thrust_list: list[float] = [mass_kg * 9.80665]

    z = 0.0
    vz = 0.0
    t = 0.0
    delay_steps = int(round(float(plan.sensor_latency_s) / dt))
    kp, kd = 6.0, 4.0

    for ph in plan.phases:
        n_steps = max(1, int(round(float(ph.duration_s) / dt)))
        z_start = z
        z_goal = float(ph.target_altitude_m)
        for step_idx in range(1, n_steps + 1):
            t = round(t + dt, 9)
            frac = step_idx / n_steps
            z_ref = z_start + (z_goal - z_start) * frac
            z_obs = z_list[max(0, len(z_list) - 1 - delay_steps)]
            if plan.sensor_noise_sigma_m > 0.0:
                noise = float(rng.normal(0.0, plan.sensor_noise_sigma_m))
            else:
                noise = 0.0
            z_sensed = z_obs + noise

            # Disturbance at clock time t
            fz_dist = 0.0
            for dist in plan.disturbances:
                if float(dist.start_s) <= t <= float(dist.start_s) + float(dist.duration_s):
                    fz_dist += float(dist.force_world_n[2])

            if ph.manual_throttle_norm is not None:
                thrust_n = float(ph.manual_throttle_norm) * 2.0 * mass_kg * 9.80665
            else:
                accel_cmd = kp * (z_ref - z_sensed) - kd * vz
                thrust_n = max(0.0, mass_kg * (9.80665 + accel_cmd))

            az = (thrust_n + fz_dist) / mass_kg - 9.80665
            vz = vz + az * dt
            z = max(0.0, z + vz * dt)
            if z == 0.0 and vz < 0.0:
                vz = 0.0

            t_list.append(t)
            z_list.append(z)
            vz_list.append(vz)
            z_meas_list.append(z_sensed)
            phase_list.append(ph.phase)
            cmd_thrust_list.append(thrust_n)

    telemetry = {
        "time_base": plan.time_base,
        "seed": plan.seed,
        "controller_dt_s": dt,
        "t": t_list,
        "z_m": z_list,
        "vz_m_s": vz_list,
        "z_sensed_m": z_meas_list,
        "thrust_n": cmd_thrust_list,
        "phase": phase_list,
    }
    digest = sha256(
        json.dumps(telemetry, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    return {
        "status": "completed",
        "mission_sha256": digest,
        "seed": plan.seed,
        "controller_dt_s": dt,
        "telemetry": telemetry,
        "render_cadence_independent": True,
        "physical_validation_status": "unvalidated",
    }
