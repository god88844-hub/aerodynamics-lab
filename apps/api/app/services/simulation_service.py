"""Simulation service: runs a stored design snapshot through the shared
scenario service and shapes the result for the API/UI (telemetry decimated,
report verbatim). Every run stores its result verbatim — traceability."""

from __future__ import annotations

from physics.scenarios import service

SCENARIOS = ("hover-ideal", "hover-static", "hover-hold", "flight")


def run_simulation(design_snapshot: dict, scenario: str, params: dict | None = None) -> dict:
    """Run one scenario on the given snapshot. Raises ValueError on invalid
    scenario/design; physics-level failures are returned as
    status='failed' results (they ARE valid engineering outputs)."""
    from aeroforge_schemas.design import DroneDesign

    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {SCENARIOS}")
    params = params or {}
    design = DroneDesign.model_validate(design_snapshot)

    error: str | None = None
    try:
        if scenario == "hover-ideal":
            report = service.run_hover_ideal(
                design,
                duration_s=float(params.get("duration_s", 2.0)),
                dt_s=float(params.get("dt_s", 0.002)),
                solver=str(params.get("solver", "rk4")),
            )
            status = "completed"
        elif scenario == "hover-static":
            report = service.run_hover_static(
                design,
                max_duration_s=float(params.get("max_duration_s", 7200.0)),
                dt_s=float(params.get("dt_s", 10.0)),
            )
            status = "completed"
        elif scenario == "hover-hold":
            report = service.run_hover_hold(
                design,
                duration_s=float(params.get("duration_s", 10.0)),
                control_dt_s=float(params.get("control_dt_s", 0.004)),
            )
            status = "completed"
        else:  # flight
            report = service.run_flight(design)
            status = "completed"
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
        status = "failed"

    report["status"] = status
    if error is not None:  # pragma: no cover
        report["error"] = error
    return report
