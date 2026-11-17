"""M25.1 conservative analytic combined bending/torsion *screen* for ductile metal tubes.

ONLY isotropic Aluminum 6061-T6 is eligible. Composite, laminate,
3D-printed or otherwise anisotropic materials are explicitly unsupported.
This is not a fatigue, joint, buckling, impact, aeroelastic, FEM, flight
safety or independently physically validated strength model.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.advanced import evaluate_advanced_envelope
from physics.structures.materials import MaterialProps


def von_mises_bending_torsion_pa(
    outer_fiber_normal_stress_pa: float,
    outer_fiber_torsional_shear_pa: float,
) -> float:
    """sqrt(sigma^2 + 3*tau^2) at the outer bending extreme for a circular tube."""
    if (not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) for v in
                (outer_fiber_normal_stress_pa, outer_fiber_torsional_shear_pa))):
        raise ValueError("combined stress inputs must be finite numeric values")
    if outer_fiber_normal_stress_pa < 0:
        raise ValueError("bending stress magnitude must be nonnegative")
    v = math.hypot(
        float(outer_fiber_normal_stress_pa),
        math.sqrt(3.) * abs(float(outer_fiber_torsional_shear_pa)),
    )
    if not math.isfinite(v):
        raise ValueError("combined von Mises stress overflowed")
    return v


def evaluate_combined_metal_screen(
    design: DroneDesign,
    cases: Sequence[tuple[str, Sequence[float], Sequence[float]]],
    materials: dict[str, MaterialProps],
    *,
    safety_factor: float,
    load_case_source: str,
) -> dict:
    """Check static circular-tube root stresses, never certify aircraft strength.

    The declared material, load cases, root fixity and safety factor are
    operator-supplied, not independent physical evidence.
    """
    if not math.isfinite(safety_factor) or safety_factor < 1 or safety_factor > 10:
        raise ValueError("safety_factor must be finite within [1,10]")
    if not isinstance(load_case_source, str) or not 1 <= len(load_case_source.strip()) <= 500:
        raise ValueError("load_case_source must cite nonempty load provenance")
    if design.frame is None:
        raise ValueError("real frame geometry is required for combined stress")
    material = materials.get(design.frame.material_id)
    if material is None:
        raise ValueError("unknown structural material")
    # The existing database contains aluminum, composite and printed polymers.
    # Using metal von Mises on CFRP would produce a scientifically false pass.
    if material.id != "alu_6061_t6":
        return {
            "status": "UNSUPPORTED_MATERIAL_FAILURE_MODEL",
            "material_id": material.id,
            "screen_passed": False,
            "independent_structural_validation_established": False,
            "flightworthiness_established": False,
            "cases": [],
            "blockers": [
                "Von Mises ductile-metal yield is not an applicable universal composite/polymer criterion",
                "Independent material allowables, laminate layup, orientation, fatigue and joint data required",
            ],
        }
    if not material.source.strip() or not math.isfinite(material.yield_strength_pa) or material.yield_strength_pa <= 0:
        raise ValueError("material yield strength/source must be known and finite")
    if not math.isfinite(material.uncertainty_pct) or material.uncertainty_pct < 0:
        raise ValueError("material uncertainty must be finite and nonnegative")
    if not 1 <= len(cases) <= 32:
        raise ValueError("provide 1–32 explicit load cases")
    for name, loads, torques in cases:
        if torques is None:
            raise ValueError(f"case {name!r} requires explicit torque, not assumed zero")
        if len(loads) != len(torques):
            raise ValueError("thrust and axial torque vectors must match")
    old = evaluate_advanced_envelope(design, cases, materials)
    allowable = material.yield_strength_pa / safety_factor
    if allowable <= 0 or not math.isfinite(allowable):
        raise ValueError("combined static allowable invalid")
    out_cases = []
    all_screened = True
    any_failure = False
    any_nonzero = False
    worst = None
    for case in old["cases"]:
        items = []
        for rotor in case["rotors"]:
            normal = rotor["bending_stress_pa"]
            tau = rotor["tube_peak_shear_stress_pa"]
            if tau is None:
                raise ValueError("unmeasured or omitted arm torque cannot be screened")
            vm = von_mises_bending_torsion_pa(normal, tau)
            has_load = vm > 0
            any_nonzero = any_nonzero or has_load
            margin = allowable / vm if has_load else None
            # Strictly less avoids claiming a safety margin at equality.
            below = vm < allowable if has_load else None
            if has_load and not below:
                any_failure = True
            if not has_load:
                all_screened = False
            item = {
                "rotor_index": rotor["rotor_index"],
                "bending_normal_pa": normal,
                "torsional_shear_pa": tau,
                "von_mises_pa": vm,
                "factor_of_safety_requested": safety_factor,
                "factor_adjusted_allowable_pa": allowable,
                "static_margin_over_required_allowable": margin,
                "below_declared_combined_allowable": below,
            }
            if worst is None or vm > worst["von_mises_pa"]:
                worst = {"case": case["name"], **item}
            items.append(item)
        out_cases.append({"name": case["name"], "rotors": items})
    verdict = (
        "EXCEEDS_DECLARED_COMBINED_STATIC_ALLOWABLE" if any_failure else
        "NO_NONZERO_DECLARED_LOAD" if not any_nonzero else
        "INCOMPLETE_ZERO_LOAD_CASES" if not all_screened else
        "ANALYTICAL_ISOTROPIC_STATIC_SCREEN_ONLY"
    )
    return {
        "status": verdict,
        "material_id": material.id,
        "material_name": material.name,
        "material_source": material.source,
        "material_nominal_yield_pa": material.yield_strength_pa,
        "material_tabulated_uncertainty_pct_not_propagated": material.uncertainty_pct,
        "load_case_source_operator_declared": load_case_source.strip(),
        "safety_factor_requested": safety_factor,
        "allowable_pa": allowable,
        "cases": out_cases,
        "governing": worst,
        "screen_passed": bool(not any_failure and any_nonzero and all_screened),
        "independent_structural_validation_established": False,
        "flightworthiness_established": False,
        "limitations": [
            "Static first-order Euler-Bernoulli bending plus Saint-Venant torsion at an assumed fixed circular tube root",
            "Assumes uniform isotropic ductile metal, linear elasticity, no shear flow/joint concentration correction",
            "No verified manufacturing quality, metallurgical lot properties, material anisotropy or actual test-load envelope",
            "No joint, fastener, clamp, weld, frame load sharing, fatigue, buckling, vibration, impact or composite failure modeling",
            "Nominal published yield and requested safety factor are not independent physical validation",
            "No actual aircraft safety or service-life claim follows from a positive analytical screen",
        ],
    }
