"""M28.7 coarse 3D rotor-to-obstacle clearance with conservative enclosing spheres.

The screen only evaluates explicitly represented operator-declared obstacles;
an omitted frame component is NOT implicitly checked. A positive result never
establishes full-aircraft CAD nonintersection or flightworthiness.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.swept_cylinder_clearance import _finite, _vector, _source

_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def screen_rotor_to_obstacle_spheres(
    design: DroneDesign,
    *,
    rotor_diameters_m: Sequence[float],
    rotor_swept_heights_m: Sequence[float],
    rotor_center_motion_hard_bounds_m: Sequence[float],
    rotor_diameter_hard_bounds_m: Sequence[float],
    obstacle_spheres: Sequence[Mapping],
    minimum_3d_gap_m: float,
    rotor_source: str,
    obstacle_source: str,
    hard_bounds_source: str,
) -> dict:
    """Sufficient nonintersection check for rotor and obstacle outer spheres.

    For each rotor cylinder radius R=sqrt(((d+u_d)/2)^2+(h/2)^2).
    An obstacle already bounded by radius r with hard radius error u_r can be
    excluded from the rotor only if center distance - (R+r+u_r) -
    (u_rotor_center+u_obstacle_center) is strictly positive and >= min gap.
    All center errors are 3D Euclidean hard bounds.
    """
    n = len(design.rotors)
    if not 2 <= n <= 32:
        raise ValueError("2–32 declared rotor centers required")
    rotor_source = _source(rotor_source, "rotor_source")
    obstacle_source = _source(obstacle_source, "obstacle_source")
    hard_bounds_source = _source(hard_bounds_source, "hard_bounds_source")
    gap = _finite(minimum_3d_gap_m, "minimum_3d_gap_m")
    d = _vector(rotor_diameters_m, n, "rotor_diameters_m", strictly_positive=True)
    h = _vector(rotor_swept_heights_m, n, "rotor_swept_heights_m", strictly_positive=True)
    u_center = _vector(rotor_center_motion_hard_bounds_m, n, "rotor_center_motion_hard_bounds_m")
    u_d = _vector(rotor_diameter_hard_bounds_m, n, "rotor_diameter_hard_bounds_m")
    if isinstance(obstacle_spheres, (str, bytes)) or not isinstance(obstacle_spheres, Sequence) or not 1 <= len(obstacle_spheres) <= 128:
        raise ValueError("1–128 explicitly declared obstacle sphere envelopes required")
    centers = []
    radii = []
    for i, rotor in enumerate(design.rotors):
        p = rotor.position_m
        if len(p) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in p):
            raise ValueError("rotor center must be a finite 3-vector")
        try:
            position = tuple(float(v) for v in p)
        except (ValueError, OverflowError) as exc:
            raise ValueError("rotor center must be finite") from exc
        if not all(math.isfinite(v) for v in position):
            raise ValueError("rotor center must be finite")
        diameter = d[i] + u_d[i]
        if not math.isfinite(diameter):
            raise ValueError("rotor radius overflow")
        r = math.hypot(diameter/2, h[i]/2)
        if not math.isfinite(r):
            raise ValueError("rotor bounding envelope overflow")
        centers.append(position)
        radii.append(r)
    obstacle_data = []
    ids = set()
    required = {"obstacle_id", "center_m", "outer_radius_m", "center_hard_bound_m", "radius_hard_bound_m"}
    for obs in obstacle_spheres:
        if not isinstance(obs, Mapping) or set(obs) != required:
            raise ValueError("obstacles must have exact enclosing sphere fields")
        name = obs["obstacle_id"]
        if not isinstance(name, str) or not _NAME.fullmatch(name) or name in ids:
            raise ValueError("invalid or duplicate obstacle ID")
        ids.add(name)
        p = obs["center_m"]
        if isinstance(p, (str, bytes)) or not isinstance(p, Sequence) or len(p) != 3:
            raise ValueError("obstacle center requires 3 coordinates")
        xyz = []
        for v in p:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("obstacle center requires finite coordinates")
            try:
                f = float(v)
            except (OverflowError, ValueError) as exc:
                raise ValueError("obstacle center requires finite coordinates") from exc
            if not math.isfinite(f):
                raise ValueError("obstacle center requires finite coordinates")
            xyz.append(f)
        r = _finite(obs["outer_radius_m"], "outer_radius_m")
        if r <= 0:
            raise ValueError("obstacle outer radius must be positive")
        u_pos = _finite(obs["center_hard_bound_m"], "center_hard_bound_m")
        u_rad = _finite(obs["radius_hard_bound_m"], "radius_hard_bound_m")
        obstacle_data.append((name, tuple(xyz), r, u_pos, u_rad))
    pairs = []
    worst = math.inf
    for i in range(n):
        for name, position, r, center_u, radius_u in obstacle_data:
            center_distance = math.dist(centers[i], position)
            total_extent = radii[i] + r + u_center[i] + center_u + radius_u
            if not math.isfinite(center_distance) or not math.isfinite(total_extent):
                raise ValueError("rotor-obstacle sphere separation overflow")
            conservative = max(0., center_distance - total_extent)
            meets = conservative > 0 and conservative >= gap
            worst = min(worst, conservative)
            pairs.append({
                "rotor_index": i, "obstacle_id": name,
                "conservative_3d_gap_lower_m": conservative,
                "possible_contact_or_intersection": conservative == 0,
                "analytical_gap_meets_declared_requirement": meets,
            })
    passed = all(p["analytical_gap_meets_declared_requirement"] for p in pairs)
    return {
        "status": ("ANALYTICAL_DECLARED_ROTOR_OBSTACLE_OUTER_SPHERES_SEPARATED"
                   if passed else "DECLARED_ROTOR_OBSTACLE_SEPARATION_NOT_ESTABLISHED"),
        "design_name": design.name,
        "declared_obstacle_count": len(obstacle_data),
        "minimum_conservative_obstacle_gap_m": worst,
        "pairs": pairs,
        "analytical_screen_passed": passed,
        "rotor_source_operator_declared": rotor_source,
        "obstacle_source_operator_declared": obstacle_source,
        "hard_bounds_source_operator_declared": hard_bounds_source,
        "obstacle_inventory_completeness_authenticated": False,
        "physical_assembly_collision_validation_established": False,
        "real_world_flightworthiness_established": False,
        "flight_release_authorized": False,
        "limitations": [
            "Only explicitly supplied obstacles are checked; missing hardware is not detected",
            "All geometry, center travel and outer sphere hard bounds are unauthenticated operator values",
            "Bounding spheres may overestimate collision risk and cannot certify airframe clearance",
            "No deformation, contact dynamics, blade flutter, manufactured part inspection or flight measurement",
        ],
    }
