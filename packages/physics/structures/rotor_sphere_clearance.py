"""M28.6 conservative orientation-independent spherical outer-envelope screen.

Any rigid right circular cylinder centered on its geometric center, regardless
of rotation/axis tilt, fits inside a sphere of radius hypot(r, height/2).
This proves only nonintersection of those ASSUMED bounding spheres, not actual
blade motion, assembly or safety. Unknown center travel remains unbounded.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.swept_cylinder_clearance import _source, _vector, _finite


def screen_orientation_independent_rotor_envelopes(
    design: DroneDesign,
    installed_diameters_m: Sequence[float],
    maximum_swept_heights_m: Sequence[float],
    xy_center_hard_bounds_m: Sequence[float],
    z_center_hard_bounds_m: Sequence[float],
    diameter_hard_bounds_m: Sequence[float],
    *,
    minimum_required_3d_clearance_m: float,
    geometry_source: str,
    hard_bound_source: str,
    center_motion_source: str,
) -> dict:
    """Fail closed when any two per-rotor enclosing spheres might meet.

    The bound remains valid for arbitrary orientation about the declared
    moving center *only if* cylinder dimensions and all center motion are
    bounded by the supplied values. It may conservatively reject a perfectly
    acceptable rotor configuration. It never certifies clearance in operation.
    """
    n = len(design.rotors)
    if n < 2 or n > 32:
        raise ValueError("2–32 rotor centers required")
    geometry_source = _source(geometry_source, "geometry_source")
    hard_bound_source = _source(hard_bound_source, "hard_bound_source")
    center_motion_source = _source(center_motion_source, "center_motion_source")
    requested = _finite(minimum_required_3d_clearance_m, "minimum_required_3d_clearance_m")
    d = _vector(installed_diameters_m, n, "installed_diameters_m", strictly_positive=True)
    heights = _vector(maximum_swept_heights_m, n, "maximum_swept_heights_m", strictly_positive=True)
    xy = _vector(xy_center_hard_bounds_m, n, "xy_center_hard_bounds_m")
    z = _vector(z_center_hard_bounds_m, n, "z_center_hard_bounds_m")
    du = _vector(diameter_hard_bounds_m, n, "diameter_hard_bounds_m")

    centers = []
    outer_radii = []
    center_errors = []
    for i, rotor in enumerate(design.rotors):
        center = rotor.position_m
        if len(center) != 3:
            raise ValueError("center must have exactly three coordinates")
        xyz = []
        for v in center:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("center must be finite")
            try:
                number = float(v)
            except (OverflowError, ValueError) as exc:
                raise ValueError("center must be finite") from exc
            if not math.isfinite(number):
                raise ValueError("center must be finite")
            xyz.append(number)
        centers.append(tuple(xyz))
        max_diameter = d[i] + du[i]
        if not math.isfinite(max_diameter):
            raise ValueError("rotor dimension accumulation overflow")
        radius = math.hypot(max_diameter / 2, heights[i] / 2)
        center_error = math.hypot(xy[i], z[i])
        if not math.isfinite(radius) or not math.isfinite(center_error):
            raise ValueError("rotor bounding sphere accumulation overflow")
        outer_radii.append(radius)
        center_errors.append(center_error)

    pairs = []
    governing = math.inf
    for i in range(n):
        for j in range(i + 1, n):
            distance = math.dist(centers[i], centers[j])
            combined = outer_radii[i] + outer_radii[j] + center_errors[i] + center_errors[j]
            if not math.isfinite(distance) or not math.isfinite(combined):
                raise ValueError("pair bounding sphere accumulation overflow")
            lower = max(0.0, distance - combined)
            if not math.isfinite(lower):
                raise ValueError("minimum separation overflow")
            meets = lower > 0 and lower >= requested
            governing = min(governing, lower)
            pairs.append({
                "rotor_a": i,
                "rotor_b": j,
                "nominal_center_distance_m": distance,
                "orientation_independent_3d_separation_lower_m": lower,
                "possibly_intersecting_spheres": lower == 0,
                "meets_declared_assumed_3d_clearance": meets,
            })
    passes = all(p["meets_declared_assumed_3d_clearance"] for p in pairs)
    return {
        "status": ("ANALYTICAL_ORIENTATION_INDEPENDENT_SPHERE_SEPARATION_ONLY"
                   if passes else "ORIENTATION_INDEPENDENT_SEPARATION_NOT_ESTABLISHED"),
        "design_name": design.name,
        "minimum_conservative_3d_separation_m": governing,
        "minimum_required_3d_clearance_m": requested,
        "pairs": pairs,
        "analytical_screen_passed": passes,
        "geometry_source_operator_declared": geometry_source,
        "hard_bound_source_operator_declared": hard_bound_source,
        "center_motion_source_operator_declared": center_motion_source,
        "physical_center_motion_bounds_authenticated": False,
        "actual_blade_interference_physically_validated": False,
        "real_aircraft_flightworthiness_established": False,
        "release_authorized": False,
        "limitations": [
            "Enclosing spheres deliberately discard geometry and may reject safe separations",
            "Cylinders and full flex/tilt/pivot center travel must already be truly hard-bounded",
            "Actual rotor shape, blade dynamics, frame/landing gear, thermal growth and mounts not checked",
            "No measured as-built geometry, independent physical evidence or flight validation",
        ],
    }
