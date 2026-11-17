"""M28.1 conservative 2-D projected propeller sweep clearance screening.

A clearance between *projected rotor disks* is not an assembled CAD collision
check. Rotor positions and installed diameters are operator-declared.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from aeroforge_schemas.design import DroneDesign


def _finite(value: object, name: str, *, strictly_positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        v = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(v) or (strictly_positive and v <= 0):
        raise ValueError(f"{name} must be finite" + (" and positive" if strictly_positive else ""))
    return v


def evaluate_rotor_sweep_clearance(
    design: DroneDesign,
    installed_propeller_diameters_m: Sequence[float],
    *,
    geometry_and_diameter_source: str,
    minimum_declared_tip_clearance_m: float = 0.0,
) -> dict:
    """Assess pairwise XY projected circular rotor-tip disks.

    Deliberately refuses absent per-rotor diameters. Z separation is reported,
    not used to waive apparent overlap: blade thickness, elastic motion, RPM,
    phase, coaxial control, mounting tolerances and actual CAD are unknown.
    """
    rotors = design.rotors
    if not 2 <= len(rotors) <= 32:
        raise ValueError("rotor sweep clearance requires 2–32 rotors")
    if not isinstance(geometry_and_diameter_source, str) or not 1 <= len(geometry_and_diameter_source.strip()) <= 500:
        raise ValueError("geometry_and_diameter_source is required")
    if isinstance(installed_propeller_diameters_m, (str, bytes)) or not isinstance(installed_propeller_diameters_m, Sequence):
        raise ValueError("per-rotor installed propeller diameters are required")
    if len(installed_propeller_diameters_m) != len(rotors):
        raise ValueError("one actual installed propeller diameter per rotor required")
    diameters = [
        _finite(value, f"propeller {i} diameter", strictly_positive=True)
        for i, value in enumerate(installed_propeller_diameters_m)
    ]
    minimum = _finite(minimum_declared_tip_clearance_m, "tip clearance")
    if minimum < 0:
        raise ValueError("tip clearance requirement cannot be negative")
    centers = []
    for i, rotor in enumerate(rotors):
        p = rotor.position_m
        if len(p) != 3:
            raise ValueError("rotor position must be a 3-vector")
        center = tuple(_finite(v, f"rotor {i} position") for v in p)
        centers.append(center)
    pairs = []
    minimum_xy = math.inf
    any_overlap = False
    any_shortfall = False
    for i in range(len(rotors)):
        for j in range(i + 1, len(rotors)):
            a, b = centers[i], centers[j]
            lateral = math.hypot(a[0] - b[0], a[1] - b[1])
            radial_sum = (diameters[i] + diameters[j]) / 2
            if not math.isfinite(lateral) or not math.isfinite(radial_sum):
                raise ValueError("rotor spacing calculation overflowed")
            clearance = lateral - radial_sum
            if not math.isfinite(clearance):
                raise ValueError("rotor clearance overflowed")
            overlap = clearance <= 0  # tangent included as zero allowed margin
            shortfall = clearance < minimum or overlap
            minimum_xy = min(minimum_xy, clearance)
            any_overlap |= overlap
            any_shortfall |= shortfall
            pairs.append({
                "rotor_a": i, "rotor_b": j,
                "center_lateral_separation_m": lateral,
                "center_vertical_separation_m": abs(a[2] - b[2]),
                "projected_tip_clearance_m": clearance,
                "projected_disk_touch_or_overlap": overlap,
                "below_declared_tip_clearance": shortfall,
            })
    verdict = ("PROJECTED_DISK_TOUCH_OR_OVERLAP_POTENTIAL"
               if any_overlap else "INSUFFICIENT_DECLARED_PROJECTED_TIP_CLEARANCE"
               if any_shortfall else "ANALYTIC_PROJECTED_TIP_CLEARANCE_ONLY")
    return {
        "status": verdict,
        "design_name": design.name,
        "geometry_and_diameter_source_operator_declared": geometry_and_diameter_source.strip(),
        "minimum_declared_tip_clearance_m": minimum,
        "minimum_observed_projected_tip_clearance_m": minimum_xy,
        "pairs": pairs,
        "screen_passed": not any_shortfall,
        "independently_measured_geometry_validated": False,
        "physical_interference_or_flightworthiness_established": False,
        "limitations": [
            "Projects all spinning rotor-tip disks onto body XY, intentionally not waiving overlaps due to height offsets",
            "Does not model blade thickness, flexibility, thermal expansion, motor mount tolerances or blade tip flapping",
            "No CAD mesh or frame/landing-gear/fuselage intersection checking",
            "Unknown precise installed propeller dimensions cannot be replaced by generic estimates",
            "Positive projected clearance does not establish physical safety or real-world flight validity",
        ],
    }
