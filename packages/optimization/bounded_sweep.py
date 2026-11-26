"""P0A-035: Deterministic bounded parameter sweeps preserving constraints, seeds, and infeasible candidates."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from aeroforge_schemas.design import DroneDesign
from optimization.batch import CandidateResult, pareto_front, run_grid
from physics.propulsion.loader import ComponentLibrary
from physics.structures.materials import MaterialProps

PARETO_CAVEATS = [
    "Pareto frontier ranks modeled candidates over (mass_kg down, endurance_s up) only.",
    "Optimization over modeled equations retains all failed/infeasible candidates and does NOT validate physical flightworthiness.",
]


def _canon_hash(data: Any) -> str:
    return sha256(json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def run_bounded_sweep(
    design: DroneDesign,
    library: ComponentLibrary,
    grid_spec: dict[str, list[Any]],
    *,
    material: MaterialProps | None = None,
    constraints: dict[str, float] | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """Run an exhaustive bounded grid sweep retaining all feasible and failed candidates."""
    for key in ("battery_capacity_ah", "rotor_count", "arm_length_m", "payload_kg"):
        vals = grid_spec.get(key)
        if not vals:
            raise ValueError(f"Sweep grid missing non-empty axis {key!r}")
    constraints = dict(constraints or {})
    max_mass_kg = constraints.get("max_mass_kg")
    min_margin = constraints.get("min_structural_margin")
    min_endurance_s = constraints.get("min_endurance_s")

    raw_results = run_grid(design, library, grid_spec, material=material)
    enriched: list[CandidateResult] = []
    for cand in raw_results:
        extra_flags = list(cand.flags)
        feasible = cand.feasible
        if max_mass_kg is not None and cand.mass_kg > float(max_mass_kg):
            feasible = False
            extra_flags.append(f"constraint_mass_exceeded: {cand.mass_kg:.3f} > {float(max_mass_kg):.3f} kg")
        if min_margin is not None and (cand.structural_margin is None or cand.structural_margin < float(min_margin)):
            feasible = False
            extra_flags.append("constraint_structural_margin_below_min")
        if min_endurance_s is not None and (
            cand.endurance_to_warning_s is None or cand.endurance_to_warning_s < float(min_endurance_s)
        ):
            feasible = False
            extra_flags.append("constraint_endurance_below_min")
        enriched.append(
            CandidateResult(
                params=dict(cand.params),
                mass_kg=cand.mass_kg,
                hover_thrust_per_rotor_n=cand.hover_thrust_per_rotor_n,
                hover_current_total_a=cand.hover_current_total_a,
                hover_power_w=cand.hover_power_w,
                v_bus_v=cand.v_bus_v,
                endurance_to_warning_s=cand.endurance_to_warning_s,
                structural_margin=cand.structural_margin,
                feasible=feasible,
                flags=extra_flags,
            )
        )

    front = pareto_front(enriched)
    rows = [c.as_row() for c in enriched]
    front_rows = [c.as_row() for c in front]
    infeasible_rows = [r for r in rows if not r["feasible"]]

    summary = {
        "schema_version": "1.0",
        "seed": int(seed),
        "constraints": constraints,
        "grid_spec": grid_spec,
        "total_candidates": len(rows),
        "feasible_count": len(rows) - len(infeasible_rows),
        "infeasible_count": len(infeasible_rows),
        "candidates": rows,
        "pareto_frontier": front_rows,
        "caveats": PARETO_CAVEATS,
        "physical_validation_status": "UNVALIDATED",
    }
    summary["candidates_sha256"] = _canon_hash({"rows": rows, "front": front_rows, "seed": int(seed), "constraints": constraints})
    return summary
