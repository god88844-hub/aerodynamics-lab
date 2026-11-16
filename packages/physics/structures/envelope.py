"""M10.7 deterministic structural load-case evaluation.

Analytic STATIC cantilever bending verification only. Load cases must be
declared, never inferred to be real measured flight envelopes. This does not
model fastening, torsion, laminate direction, fatigue, dynamics or FEA.
"""
from __future__ import annotations

import math
from typing import Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.beam import (
    bending_stress_pa, effective_arm_spans_m,
)
from physics.structures.materials import MaterialProps


def evaluate_load_envelope(
    design: DroneDesign,
    cases: Sequence[tuple[str, Sequence[float]]],
    materials: dict[str, MaterialProps],
) -> dict:
    """Return auditable case/rotor bending stresses with non-certifying verdicts.

    The aircraft frame root is assumed at the body origin. The effective span
    is max(declared frame span, horizontal rotor radius). A zero-thrust case
    has undefined (not infinite JSON) margin and cannot prove strength.
    """
    if design.frame is None:
        raise ValueError("frame geometry is required; do not assume a structural pass")
    frame = design.frame
    material = materials.get(frame.material_id)
    if material is None:
        raise ValueError(f"unknown structural material {frame.material_id!r}")
    if not math.isfinite(material.yield_strength_pa) or material.yield_strength_pa <= 0:
        raise ValueError("structural material allowable must be finite and positive")
    if not 1 <= len(cases) <= 32:
        raise ValueError("provide between 1 and 32 explicit structural load cases")
    spans = effective_arm_spans_m(
        frame.arm_length_m, [r.position_m for r in design.rotors]
    )
    seen: set[str] = set()
    case_reports: list[dict] = []
    governing: dict | None = None

    for name, thrusts in cases:
        if not isinstance(name, str) or not name.strip() or len(name) > 80 or name in seen:
            raise ValueError("load-case names must be unique, nonempty and <=80 characters")
        seen.add(name)
        if len(thrusts) != len(spans) or not all(
            isinstance(t, (int, float)) and math.isfinite(t) and t >= 0
            for t in thrusts
        ):
            raise ValueError(f"case {name!r}: thrusts must match rotor count and be finite >=0 N")
        arms: list[dict] = []
        for i, (thrust, span) in enumerate(zip(thrusts, spans)):
            moment = float(thrust) * span
            stress = bending_stress_pa(float(thrust), span, frame.tube_od_m, frame.tube_id_m)
            margin = material.yield_strength_pa / stress if stress > 0 else None
            arm = {
                "rotor_index": i,
                "thrust_n": float(thrust),
                "span_m": span,
                "root_bending_moment_n_m": moment,
                "bending_stress_pa": stress,
                "allowable_pa": material.yield_strength_pa,
                "margin": margin,
                "below_allowable": (stress < material.yield_strength_pa) if stress > 0 else None,
            }
            arms.append(arm)
            if stress > 0 and (governing is None or stress > governing["bending_stress_pa"]):
                governing = {"case": name, **arm}
        case_reports.append({
            "name": name,
            "rotors": arms,
            "has_applied_load": any(a["thrust_n"] > 0 for a in arms),
            "minimum_nonzero_margin": min(
                (a["margin"] for a in arms if a["margin"] is not None), default=None,
            ),
        })

    all_below = governing is not None and all(
        arm["bending_stress_pa"] < material.yield_strength_pa
        for case in case_reports for arm in case["rotors"]
    )
    return {
        "design_name": design.name,
        "material_id": frame.material_id,
        "material_source": material.source,
        "material_uncertainty_pct": material.uncertainty_pct,
        "assumed_root": "body_origin",
        "failure_threshold": "static_fiber_stress_below_declared_allowable",
        "cases": case_reports,
        "governing": governing,
        "all_declared_cases_below_allowable": all_below,
        "verdict": (
            "NO_APPLIED_LOAD" if governing is None else
            "EXCEEDS_DECLARED_ALLOWABLE" if not all_below else
            "ANALYTICAL_STATIC_SCREEN_ONLY"
        ),
        "limitations": [
            "Analytical static bending only, not independent physical validation",
            "Body-origin clamped-root assumption and independent per-rotor cantilevers",
            "No torsion, buckling, joints, fatigue, vibration, composite anisotropy or load sharing",
            "Provided load cases are not proof of exhaustive real-world flight loading",
            "Material uncertainty is reported, not statistically propagated into a failure probability",
        ],
    }
