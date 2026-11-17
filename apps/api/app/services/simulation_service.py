"""Run a design through the shared scenario service and capture its inputs."""

from __future__ import annotations

import json
import math

from physics import __version__ as physics_version
from physics.integration.runtime_limit import (
    SimulationTimeLimit, SimulationWorkLimit, check_time_limit, time_limit,
)
from physics.scenarios import service

SCENARIOS = ("hover-ideal", "hover-static", "hover-hold", "flight")
SIMULATION_STEP_LIMITS = {"hover-ideal": 20_000, "hover-static": 2_000, "hover-hold": 10_000}
SIMULATION_MAX_ADAPTIVE_EVALUATIONS = 120_000
SIMULATION_TIME_LIMIT_S = 45.0
SIMULATION_MAX_PARTS = 256
SIMULATION_MAX_ROTORS = 32


def _check_work(scenario: str, duration: float, step: float) -> None:
    if duration <= 0 or step <= 0:
        raise SimulationWorkLimit("The simulation duration and step must be positive.")
    limit = SIMULATION_STEP_LIMITS[scenario]
    # Static hover records the initial sample and includes its ending instant.
    estimated = duration / step if scenario != "hover-static" else (duration + 1e-9) / step + 1
    if not math.isfinite(estimated) or estimated > limit:
        raise SimulationWorkLimit(f"{scenario} exceeds its {limit:,}-step work limit.")
    if scenario == "hover-hold" and round(estimated) == 0:
        raise SimulationWorkLimit("Hover hold needs at least one control step.")


def _number(params: dict, key: str, default: float) -> float:
    try:
        value = float(params.get(key, default))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{key} must be a finite number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{key} must be a finite number")
    return value


def run_simulation(design_snapshot: dict, scenario: str, params: dict | None = None) -> tuple[dict, dict]:
    """Return the run report and the exact API inputs captured for it."""
    from aeroforge_schemas.design import DroneDesign

    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {SCENARIOS}")
    params = params or {}
    # Reject values that cannot be exported as standard JSON before execution.
    json.dumps(params, allow_nan=False)
    design = DroneDesign.model_validate(design_snapshot)
    inputs = {
        "schema_version": 1,
        "physics_version": physics_version,
        "design": design.model_dump(mode="json"),
        "scenario": scenario,
        "requested_parameters": params,
        "effective_parameters": None,
        "execution_limits": {
            "time_s": SIMULATION_TIME_LIMIT_S,
            "steps": SIMULATION_STEP_LIMITS.get(scenario),
            "parts": SIMULATION_MAX_PARTS,
            "rotors": SIMULATION_MAX_ROTORS,
        },
    }
    effective = None
    try:
        if len(design.parts) > SIMULATION_MAX_PARTS or len(design.rotors) > SIMULATION_MAX_ROTORS:
            raise SimulationWorkLimit(
                f"API simulations support up to {SIMULATION_MAX_PARTS} parts and {SIMULATION_MAX_ROTORS} rotors."
            )
        with time_limit(SIMULATION_TIME_LIMIT_S):
            if scenario == "hover-ideal":
                effective = {
                    "duration_s": _number(params, "duration_s", 2.0),
                    "dt_s": _number(params, "dt_s", 0.002),
                    "solver": str(params.get("solver", "rk4")),
                }
                step = effective["dt_s"]
                if effective["solver"] == "ivp":
                    step = service.IDEAL_RK45_MAX_STEP_S
                    effective["max_evaluations"] = SIMULATION_MAX_ADAPTIVE_EVALUATIONS
                _check_work(scenario, effective["duration_s"], step)
                report = service.run_hover_ideal(design, **effective)
            elif scenario == "hover-static":
                effective = {
                    "max_duration_s": _number(params, "max_duration_s", 7200.0),
                    "dt_s": _number(params, "dt_s", 10.0),
                }
                _check_work(scenario, effective["max_duration_s"], effective["dt_s"])
                report = service.run_hover_static(design, **effective)
            elif scenario == "hover-hold":
                effective = {
                    "duration_s": _number(params, "duration_s", 10.0),
                    "control_dt_s": _number(params, "control_dt_s", 0.004),
                }
                _check_work(scenario, effective["duration_s"], effective["control_dt_s"])
                report = service.run_hover_hold(design, **effective)
            else:  # flight uses its fixed built-in mission and controller period
                effective = {}
                report = service.run_flight(design)
            check_time_limit()
        report["status"] = "completed"
    except (ValueError, RuntimeError) as exc:
        # Physics refused the design/scenario (out of envelope, trim
        # impossible, battery mass mismatch...). The refusal is the result.
        report = {
            "scenario": scenario,
            "status": "failed",
            "error": str(exc),
            "trustworthiness": {
                "verdict": "RUN FAILED — see error; a refusal is a valid "
                "engineering outcome, not a silent pass"
            },
            "telemetry": None,
        }
        if isinstance(exc, (SimulationTimeLimit, SimulationWorkLimit)):
            report["error_code"] = (
                "simulation_time_limit" if isinstance(exc, SimulationTimeLimit) else "simulation_work_limit"
            )
            report["trustworthiness"]["verdict"] = "RUN STOPPED — API execution limit reached"
    inputs["effective_parameters"] = effective
    return report, inputs
