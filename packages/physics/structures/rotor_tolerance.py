"""M28.3: conservative projected rotor sweep with declared hard geometry error bounds.

The radial center-position bounds must bound Euclidean XY center displacement,
not merely independent 1-sigma per-axis errors. Diameter bounds must be
absolute worst-case errors. Source claims are user supplied, not authenticated.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_clearance import evaluate_rotor_sweep_clearance


def _finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{name} must be finite and nonnegative")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite and nonnegative") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def _bounds(values: Sequence[float], n: int, name: str) -> list[float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError(f"{name}: explicit per-rotor bounds required")
    if len(values) != n:
        raise ValueError(f"{name}: one bound per rotor required")
    return [_finite(v, name) for v in values]


def evaluate_bounded_rotor_clearance(
    design: DroneDesign,
    installed_propeller_diameters_m: Sequence[float],
    xy_center_position_hard_bounds_m: Sequence[float],
    diameter_hard_bounds_m: Sequence[float],
    *,
    geometry_source: str,
    hard_bound_source: str,
    minimum_declared_tip_clearance_m: float,
) -> dict:
    """Evaluate conservative *projected* gap for all rotor pairs.

    A positional error ball of radius u_i allows actual XY center position
    within u_i of the declared center. The pair distance cannot be smaller
    than max(0, nominal XY center separation - u_i - u_j). The true blade
    diameter can be up to d_i + delta_d_i, so subtract those max radii.
    This is a deterministic conservative bound, NOT a failure probability.
    """
    n = len(design.rotors)
    if not 2 <= n <= 32:
        raise ValueError("2–32 rotor positions required")
    if not isinstance(hard_bound_source, str) or not 1 <= len(hard_bound_source.strip()) <= 500:
        raise ValueError("hard_bound_source required for worst-case bounds")
    if not isinstance(geometry_source, str) or not 1 <= len(geometry_source.strip()) <= 500:
        raise ValueError("geometry_source required")
    center_u = _bounds(xy_center_position_hard_bounds_m, n, "xy_center_position_hard_bounds_m")
    diameter_u = _bounds(diameter_hard_bounds_m, n, "diameter_hard_bounds_m")
    nominal = evaluate_rotor_sweep_clearance(
        design, installed_propeller_diameters_m,
        geometry_and_diameter_source=geometry_source,
        minimum_declared_tip_clearance_m=minimum_declared_tip_clearance_m,
    )
    pairs = []
    all_bounded = True
    worst = math.inf
    nominal_interference = False
    for pair in nominal["pairs"]:
        i, j = pair["rotor_a"], pair["rotor_b"]
        center_distance = pair["center_lateral_separation_m"]
        radius_error = center_u[i] + center_u[j]
        diameter_sum = (installed_propeller_diameters_m[i] + diameter_u[i] +
                        installed_propeller_diameters_m[j] + diameter_u[j])
        if not all(math.isfinite(v) for v in (radius_error, diameter_sum)):
            raise ValueError("cumulative rotor geometry hard bounds overflowed")
        worst_center_separation = max(0.0, center_distance - radius_error)
        gap = worst_center_separation - 0.5 * diameter_sum
        if not math.isfinite(gap):
            raise ValueError("worst-case rotor tip clearance overflowed")
        nominal_interference |= pair["projected_disk_touch_or_overlap"]
        satisfied = gap > 0 and gap >= nominal["minimum_declared_tip_clearance_m"]
        all_bounded &= satisfied
        worst = min(worst, gap)
        pairs.append({
            "rotor_a": i,
            "rotor_b": j,
            "nominal_projected_tip_clearance_m": pair["projected_tip_clearance_m"],
            "worst_case_lower_projected_tip_clearance_m": gap,
            "guaranteed_declared_tip_gap_under_assumed_hard_bounds": satisfied,
            "declared_xy_position_error_sum_m": radius_error,
            "worst_case_lateral_center_separation_m": worst_center_separation,
        })
    if nominal_interference:
        status = "NOMINAL_PROJECTED_OVERLAP_OR_CONTACT"
    elif not all_bounded:
        status = "HARD_BOUND_PROJECTED_CLEARANCE_NOT_ESTABLISHED"
    else:
        status = "ANALYTICAL_HARD_BOUND_PROJECTED_CLEARANCE_ONLY"
    return {
        "status": status,
        "design_name": design.name,
        "geometry_source_operator_declared": geometry_source.strip(),
        "hard_bound_source_operator_declared": hard_bound_source.strip(),
        "minimum_declared_tip_clearance_m": nominal["minimum_declared_tip_clearance_m"],
        "minimum_worst_case_projected_tip_clearance_m": worst,
        "pairs": pairs,
        "analytical_screen_passed": all_bounded and not nominal_interference,
        "source_hard_bounds_independently_authenticated": False,
        "actual_3d_interference_validated": False,
        "flightworthiness_established": False,
        "limitations": [
            "Hard XY-center bounds must be Euclidean worst-case radii, not standard deviations",
            "Reported installed propeller diameters and bounds are not independently measured by this code",
            "Conservative XY projection does not resolve actual 3D blade motion, vertical spacing or frame clashes",
            "Passing analytically under assumed hard bounds is not a demonstrated physical success probability",
        ],
    }
