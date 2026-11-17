"""M26.21: reject unrepresentative or incompletely specified hardware regimes.

String/model equivalence and mass/environment comparisons are self-reported
screens, never proof of matched serial numbers, experimental installation or
genuine full-aircraft physical validation.
"""
from __future__ import annotations

from collections.abc import Mapping
from physics.validation.flight_clock_alignment import _finite

_MODEL_KEYS = {
    "aircraft_type", "motor_model", "propeller_model", "esc_model",
    "battery_pack_model", "installed_rotor_count", "mount_configuration_id",
    "takeoff_mass_kg",
}
_MEASURED_KEYS = _MODEL_KEYS | {"ambient_temperature_c"}


def screen_declared_hardware_match(
    reference_hardware: Mapping, measured_hardware: Mapping, *,
    maximum_predeclared_mass_fraction_difference: float,
    declared_ambient_min_c: float,
    declared_ambient_max_c: float,
) -> dict:
    """Fail closed on missing components, changed mounting or excluded environment."""
    if (not isinstance(reference_hardware, Mapping)
            or set(reference_hardware) != _MODEL_KEYS
            or not isinstance(measured_hardware, Mapping)
            or set(measured_hardware) != _MEASURED_KEYS):
        raise ValueError("exact reference and measured vehicle/hardware fields required")
    categorical = (
        "aircraft_type", "motor_model", "propeller_model", "esc_model",
        "battery_pack_model", "mount_configuration_id",
    )
    for key in categorical:
        for item in (reference_hardware, measured_hardware):
            value = item[key]
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"missing or invalid installed hardware identity: {key}")
    rotors_ref, rotors_obs = (reference_hardware["installed_rotor_count"],
                             measured_hardware["installed_rotor_count"])
    if (type(rotors_ref) is not int or type(rotors_obs) is not int
            or not 1 <= rotors_ref <= 32 or not 1 <= rotors_obs <= 32):
        raise ValueError("installed_rotor_count must be an integer 1..32")
    mass_ref = _finite(reference_hardware["takeoff_mass_kg"], "reference mass")
    mass_obs = _finite(measured_hardware["takeoff_mass_kg"], "measured mass")
    if mass_ref <= 0 or mass_obs <= 0:
        raise ValueError("aircraft mass must be strictly positive")
    mass_tolerance = _finite(
        maximum_predeclared_mass_fraction_difference,
        "maximum_predeclared_mass_fraction_difference", nonnegative=True,
    )
    if mass_tolerance > 1:
        raise ValueError("mass fraction tolerance cannot exceed 1")
    ambient_min = _finite(declared_ambient_min_c, "declared_ambient_min_c")
    ambient_max = _finite(declared_ambient_max_c, "declared_ambient_max_c")
    ambient = _finite(measured_hardware["ambient_temperature_c"], "measured ambient")
    if ambient_min > ambient_max:
        raise ValueError("declared ambient temperature range reversed")
    mismatch = [key for key in categorical
                if reference_hardware[key] != measured_hardware[key]]
    if rotors_ref != rotors_obs:
        mismatch.append("installed_rotor_count")
    relative_mass_error = abs(mass_ref - mass_obs) / mass_ref
    if relative_mass_error > mass_tolerance:
        mismatch.append("takeoff_mass_kg")
    if not ambient_min <= ambient <= ambient_max:
        mismatch.append("ambient_temperature_c")
    return {
        "status": (
            "DECLARED_HARDWARE_AND_REGIME_MATCH_UNAUTHENTICATED"
            if not mismatch else "INCOMPATIBLE_OR_OUTSIDE_DECLARED_HARDWARE_ENVELOPE"
        ),
        "operator_declared_hardware_fields_mismatched": sorted(mismatch),
        "relative_takeoff_mass_difference": relative_mass_error,
        "declared_mass_tolerance_fraction": mass_tolerance,
        "declared_ambient_range_c": [ambient_min, ambient_max],
        "operator_measured_ambient_c": ambient,
        "eligible_for_conditional_numerical_screen": not mismatch,
        "installed_serials_and_hardware_revisions_independently_verified": False,
        "true_aircraft_assembly_and_test_conditions_authenticated": False,
        "flight_release_authorized": False,
    }
