"""Run a design through the shared scenario service and capture its inputs."""

from __future__ import annotations

import json
import math

from physics import __version__ as physics_version
from physics.scenarios import service

SCENARIOS = ("hover-ideal", "hover-static", "hover-hold", "flight")


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
    }
    effective = None
    try:
        if scenario == "hover-ideal":
            effective = {
                "duration_s": _number(params, "duration_s", 2.0),
                "dt_s": _number(params, "dt_s", 0.002),
                "solver": str(params.get("solver", "rk4")),
            }
            report = service.run_hover_ideal(design, **effective)
        elif scenario == "hover-static":
            effective = {
                "max_duration_s": _number(params, "max_duration_s", 7200.0),
                "dt_s": _number(params, "dt_s", 10.0),
            }
            report = service.run_hover_static(design, **effective)
        elif scenario == "hover-hold":
            effective = {
                "duration_s": _number(params, "duration_s", 10.0),
                "control_dt_s": _number(params, "control_dt_s", 0.004),
            }
            report = service.run_hover_hold(design, **effective)
        else:  # flight
            effective = {}
            report = service.run_flight(design)
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
    inputs["effective_parameters"] = effective
    return report, inputs
