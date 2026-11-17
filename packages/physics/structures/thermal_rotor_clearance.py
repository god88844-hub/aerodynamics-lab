"""M28.11: conservative thermal geometry error expansion for moving rotor envelopes.

Thermal increments are absolute operator-declared *hard* limits. This method
cannot independently establish material behavior, real thermal conditions,
composite anisotropy, blade warping, structural failure or physical clearance.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.swept_cylinder_clearance import _source, _vector
from physics.structures.continuous_rotor_pair_clearance import screen_continuous_rotor_pair_clearance

_ROTOR_FIELDS = {
    "installed_rotor_diameters_m", "maximum_swept_heights_m",
    "diameter_hard_bounds_m", "center_position_hard_bounds_m",
    "center_speed_hard_bounds_m_per_s", "time_samples",
    "minimum_declared_pair_gap_m", "trajectory_source",
    "geometry_hard_bound_source", "rotor_center_speed_source",
}
_THERMAL_FIELDS = {
    "temperature_excursion_hard_bounds_k",
    "diameter_abs_expansion_coeff_upper_per_k",
    "height_abs_expansion_coeff_upper_per_k",
    "arm_length_m",
    "arm_abs_expansion_coeff_upper_per_k",
    "thermal_environment_source",
    "material_expansion_source",
    "arm_geometry_source",
}


def apply_thermal_rotor_hard_bounds(
    design: DroneDesign,
    *,
    rotor_pair_motion_case: Mapping,
    thermal_case: Mapping,
) -> tuple[dict, list[dict]]:
    """Return a *new* rotor case with conservatively enlarged hard envelopes.

    Diameter increase: nominal_diameter * abs_alpha_d * abs_delta_T.
    Height increase: nominal_height * abs_alpha_h * abs_delta_T.
    Center displacement addition: nominal_arm_length * abs_alpha_arm * abs_delta_T.

    Absolute nominal coefficients are upper envelopes; no signed thermal
    contraction is allowed to improve clearance. Only geometric expansion
    and mounting translation are modeled, not temperature-induced rotor speed.
    """
    n = len(design.rotors)
    if not 2 <= n <= 32:
        raise ValueError("2–32 rotors required")
    if not isinstance(rotor_pair_motion_case, Mapping) or set(rotor_pair_motion_case) != _ROTOR_FIELDS:
        raise ValueError("exact base rotor motion case fields required")
    if not isinstance(thermal_case, Mapping) or set(thermal_case) != _THERMAL_FIELDS:
        raise ValueError("exact independent thermal hard-bound fields required")
    for name in ("thermal_environment_source", "material_expansion_source", "arm_geometry_source"):
        _source(thermal_case[name], name)
    temps = _vector(thermal_case["temperature_excursion_hard_bounds_k"], n, "temperature_excursion_hard_bounds_k")
    da = _vector(thermal_case["diameter_abs_expansion_coeff_upper_per_k"], n, "diameter_abs_expansion_coeff_upper_per_k")
    ha = _vector(thermal_case["height_abs_expansion_coeff_upper_per_k"], n, "height_abs_expansion_coeff_upper_per_k")
    arms = _vector(thermal_case["arm_length_m"], n, "arm_length_m")
    aa = _vector(thermal_case["arm_abs_expansion_coeff_upper_per_k"], n, "arm_abs_expansion_coeff_upper_per_k")
    diameters = _vector(rotor_pair_motion_case["installed_rotor_diameters_m"], n, "installed_rotor_diameters_m", strictly_positive=True)
    heights = _vector(rotor_pair_motion_case["maximum_swept_heights_m"], n, "maximum_swept_heights_m", strictly_positive=True)
    diameter_errors = _vector(rotor_pair_motion_case["diameter_hard_bounds_m"], n, "diameter_hard_bounds_m")
    center_errors = _vector(rotor_pair_motion_case["center_position_hard_bounds_m"], n, "center_position_hard_bounds_m")
    new_case = dict(rotor_pair_motion_case)
    new_heights, new_d_errors, new_c_errors, entries = [], [], [], []
    for i in range(n):
        extra_d = diameters[i] * da[i] * temps[i]
        extra_h = heights[i] * ha[i] * temps[i]
        extra_c = arms[i] * aa[i] * temps[i]
        current_h = heights[i] + extra_h
        current_d = diameter_errors[i] + extra_d
        current_c = center_errors[i] + extra_c
        if not all(math.isfinite(v) for v in (extra_d, extra_h, extra_c, current_h, current_d, current_c)):
            raise ValueError("temperature-induced geometry hard bound accumulation overflow")
        new_heights.append(current_h)
        new_d_errors.append(current_d)
        new_c_errors.append(current_c)
        entries.append({
            "rotor_index": i, "temperature_excursion_hard_bound_k": temps[i],
            "additional_diameter_error_m": extra_d,
            "additional_swept_height_m": extra_h,
            "additional_center_position_hard_bound_m": extra_c,
            "thermally_enlarged_diameter_hard_bound_m": current_d,
            "thermally_enlarged_center_position_hard_bound_m": current_c,
        })
    new_case["maximum_swept_heights_m"] = new_heights
    new_case["diameter_hard_bounds_m"] = new_d_errors
    new_case["center_position_hard_bounds_m"] = new_c_errors
    new_case["geometry_hard_bound_source"] = (
        str(rotor_pair_motion_case["geometry_hard_bound_source"])
        + " | thermal hard envelope: " + thermal_case["material_expansion_source"].strip()
    )
    if len(new_case["geometry_hard_bound_source"]) > 500:
        raise ValueError("combined geometry and thermal source reference is too long")
    return new_case, entries


def screen_thermal_rotor_pair_clearance(
    design: DroneDesign, *, rotor_pair_motion_case: Mapping, thermal_case: Mapping
) -> dict:
    expanded, per_rotor = apply_thermal_rotor_hard_bounds(
        design, rotor_pair_motion_case=rotor_pair_motion_case, thermal_case=thermal_case
    )
    geometry = screen_continuous_rotor_pair_clearance(design, **expanded)
    return {
        "status": ("ANALYTICAL_THERMAL_ROTOR_PAIR_CLEARANCE_ASSUMPTIONS_ONLY"
                   if geometry["analytical_screen_passed"]
                   else "THERMALLY_BOUNDED_ROTOR_PAIR_CLEARANCE_NOT_ESTABLISHED"),
        "analytical_screen_passed": geometry["analytical_screen_passed"],
        "per_rotor_thermal_error_increments": per_rotor,
        "expanded_geometry_report": geometry,
        "thermal_environment_source_operator_declared": thermal_case["thermal_environment_source"].strip(),
        "material_expansion_source_operator_declared": thermal_case["material_expansion_source"].strip(),
        "arm_geometry_source_operator_declared": thermal_case["arm_geometry_source"].strip(),
        "thermal_conditions_and_material_bounds_independently_measured": False,
        "actual_hot_or_cold_3d_rotor_clearance_validated": False,
        "real_world_airworthiness_established": False,
        "flight_release_authorized": False,
        "limitations": [
            "Only declared thermal geometry dilatation; no warping, softening, fatigue or structural failure",
            "All true worst-case temperature, material, arm and dynamic position bounds are unauthenticated",
            "Rotor swept geometry and speed bounds must enclose the full flight operating regime",
            "No physical hot/cold test, actual-aircraft inspection or flight certification",
        ],
    }
