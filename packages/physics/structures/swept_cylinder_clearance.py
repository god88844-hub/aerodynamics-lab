"""M28.5 conservative swept cylinder envelopes for body-Z-parallel rotors.

This is geometric *nonintersection* of prescribed rigid cylinders under
operator-declared deterministic hard geometry bounds, NOT an as-built
assembly, rotor flex/tilt or 3D CAD collision validation result.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_tolerance import _finite


def _vector(values: Sequence[float], count: int, name: str, *, strictly_positive=False) -> list[float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence) or len(values) != count:
        raise ValueError(f"{name}: exact per-rotor values required")
    out = [_finite(value, name) for value in values]
    if strictly_positive and any(v <= 0 for v in out):
        raise ValueError(f"{name}: positive swept dimensions required")
    return out


def _source(value: object, name: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 500:
        raise ValueError(f"{name}: original source/reference required")
    return value.strip()


def screen_3d_rotor_swept_envelopes(
    design: DroneDesign,
    installed_diameters_m: Sequence[float],
    swept_vertical_heights_m: Sequence[float],
    xy_center_hard_bounds_m: Sequence[float],
    z_center_hard_bounds_m: Sequence[float],
    diameter_hard_bounds_m: Sequence[float],
    *,
    required_clearance_m: float,
    geometry_source: str,
    hard_bound_source: str,
    axes_parallel_body_z_declared: bool,
    axis_alignment_source: str,
) -> dict:
    """Conservatively separate rigid body-Z-parallel swept cylinders.

    Each cylinder's radius is (installed diameter + absolute diameter hard
    error)/2; its height is the FULL declared maximum swept vertical height,
    including flex/flapping *if that has actually been bounded*. Center
    displacement is independently bounded in XY Euclidean distance and Z.
    On the assumptions, 3D distance lower bound is hypot(max(0,xy_gap),
    max(0,z_gap)); must be strictly positive and >= required clearance.
    """
    n = len(design.rotors)
    if not 2 <= n <= 32:
        raise ValueError("2–32 rotor centers required")
    if axes_parallel_body_z_declared is not True:
        raise ValueError("rotor axes must be explicitly declared body-Z-parallel")
    geometry_source = _source(geometry_source, "geometry_source")
    hard_bound_source = _source(hard_bound_source, "hard_bound_source")
    axis_alignment_source = _source(axis_alignment_source, "axis_alignment_source")
    min_gap = _finite(required_clearance_m, "required_clearance_m")
    diameters = _vector(installed_diameters_m, n, "installed_diameters_m", strictly_positive=True)
    heights = _vector(swept_vertical_heights_m, n, "swept_vertical_heights_m", strictly_positive=True)
    xy_errors = _vector(xy_center_hard_bounds_m, n, "xy_center_hard_bounds_m")
    z_errors = _vector(z_center_hard_bounds_m, n, "z_center_hard_bounds_m")
    dia_errors = _vector(diameter_hard_bounds_m, n, "diameter_hard_bounds_m")
    centers = []
    for i, rotor in enumerate(design.rotors):
        pos = rotor.position_m
        if len(pos) != 3:
            raise ValueError("rotor center must have exactly three coordinates")
        xyz = []
        for axis, x in enumerate(pos):
            if isinstance(x, bool) or not isinstance(x, (int, float)):
                raise ValueError("nonfinite rotor center")
            try:
                v = float(x)
            except (ValueError, OverflowError) as exc:
                raise ValueError("nonfinite rotor center") from exc
            if not math.isfinite(v):
                raise ValueError("nonfinite rotor center")
            xyz.append(v)
        centers.append(xyz)
    pairs = []
    min_3d = math.inf
    for i in range(n):
        for j in range(i + 1, n):
            a, b = centers[i], centers[j]
            lateral = math.hypot(a[0] - b[0], a[1] - b[1])
            vertical = abs(a[2] - b[2])
            xy_error = xy_errors[i] + xy_errors[j]
            z_error = z_errors[i] + z_errors[j]
            outer_diameter_sum = diameters[i] + dia_errors[i] + diameters[j] + dia_errors[j]
            height_sum = heights[i] + heights[j]
            if not all(map(math.isfinite, (lateral, vertical, xy_error, z_error, outer_diameter_sum, height_sum))):
                raise ValueError("geometry accumulation overflow")
            xy_sep_lower = max(0.0, lateral - xy_error) - outer_diameter_sum / 2
            z_sep_lower = max(0.0, vertical - z_error) - height_sum / 2
            nonpenetrating_xy = max(0.0, xy_sep_lower)
            nonpenetrating_z = max(0.0, z_sep_lower)
            separation = math.hypot(nonpenetrating_xy, nonpenetrating_z)
            if not math.isfinite(separation):
                raise ValueError("3D separation overflow")
            min_3d = min(min_3d, separation)
            meets = separation > 0 and separation >= min_gap
            pairs.append({
                "rotor_a": i, "rotor_b": j,
                "minimum_xy_gap_m": xy_sep_lower,
                "minimum_axial_gap_m": z_sep_lower,
                "conservative_3d_separation_lower_m": separation,
                "meets_assumed_3d_envelope_clearance": meets,
                "possible_intersection_or_contact": separation == 0,
            })
    screen_passed = all(p["meets_assumed_3d_envelope_clearance"] for p in pairs)
    return {
        "status": (
            "ANALYTICAL_ASSUMED_3D_CYLINDER_NONINTERSECTION_ONLY"
            if screen_passed else "3D_SWEPT_ENVELOPE_SEPARATION_NOT_ESTABLISHED"
        ),
        "design_name": design.name,
        "conservative_minimum_3d_separation_m": min_3d,
        "required_clearance_m": min_gap,
        "pairs": pairs,
        "analytical_screen_passed": screen_passed,
        "axes_parallel_body_z_operator_declared": True,
        "geometry_source_operator_declared": geometry_source,
        "hard_bound_source_operator_declared": hard_bound_source,
        "axis_alignment_source_operator_declared": axis_alignment_source,
        "original_as_built_measurements_authenticated": False,
        "actual_dynamic_rotor_3d_clearance_validated": False,
        "flightworthiness_established": False,
        "limitations": [
            "Rigid body-Z-parallel swept cylinders only; tilting rotor disks require another method",
            "Declared height must already bound blade bending, flapping and wobble; not verified here",
            "Vertical and XY position hard bounds must be worst-case absolute bounds, not 1-sigma errors",
            "No blade/frame, motor, payload or landing gear collision check",
            "No independent as-built geometry or physical operating-envelope validation",
        ],
    }
