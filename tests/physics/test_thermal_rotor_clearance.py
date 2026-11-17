"""M28.11 synthetic thermal growth tests, not independently measured materials."""
from copy import deepcopy
from pathlib import Path

import pytest
from aeroforge_schemas.design import DroneDesign
from physics.structures.thermal_rotor_clearance import (
    apply_thermal_rotor_hard_bounds, screen_thermal_rotor_pair_clearance,
)

ROOT = Path(__file__).resolve().parents[2]


def design():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def fixture():
    centers = [list(r.position_m) for r in design().rotors]
    motion = {
        "installed_rotor_diameters_m": [.381]*4,
        "maximum_swept_heights_m": [.02]*4,
        "diameter_hard_bounds_m": [0]*4,
        "center_position_hard_bounds_m": [0]*4,
        "center_speed_hard_bounds_m_per_s": [0]*4,
        "time_samples": [
            {"time_s": 0, "rotor_centers_m": deepcopy(centers)},
            {"time_s": 1, "rotor_centers_m": deepcopy(centers)},
        ],
        "minimum_declared_pair_gap_m": .01,
        "trajectory_source": "synthetic, not real flight",
        "geometry_hard_bound_source": "synthetic baseline",
        "rotor_center_speed_source": "synthetic assumed motion limit",
    }
    thermal = {
        "temperature_excursion_hard_bounds_k": [20.]*4,
        "diameter_abs_expansion_coeff_upper_per_k": [.0001]*4,
        "height_abs_expansion_coeff_upper_per_k": [.0001]*4,
        "arm_length_m": [.25]*4,
        "arm_abs_expansion_coeff_upper_per_k": [.0001]*4,
        "thermal_environment_source": "assumed temperature range, not measured",
        "material_expansion_source": "assumed CTE, not manufacturer-certified",
        "arm_geometry_source": "assumed mounting arm lengths",
    }
    return motion, thermal


def run(motion=None, thermal=None):
    m, t = fixture()
    return screen_thermal_rotor_pair_clearance(
        design(), rotor_pair_motion_case=m if motion is None else motion,
        thermal_case=t if thermal is None else thermal,
    )


def test_thermal_growth_only_reduces_or_preserves_clearance_not_physical_validation():
    m, t = fixture()
    original_m, original_t = deepcopy(m), deepcopy(t)
    expanded, increments = apply_thermal_rotor_hard_bounds(
        design(), rotor_pair_motion_case=m, thermal_case=t
    )
    assert m == original_m and t == original_t
    assert increments[0]["additional_diameter_error_m"] == pytest.approx(.381*.0001*20)
    assert increments[0]["additional_swept_height_m"] == pytest.approx(.02*.0001*20)
    assert increments[0]["additional_center_position_hard_bound_m"] == pytest.approx(.25*.0001*20)
    assert expanded["diameter_hard_bounds_m"][0] == pytest.approx(.000762)
    assert expanded["center_position_hard_bounds_m"][0] == pytest.approx(.0005)
    result = run(m, t)
    assert result["status"] == "ANALYTICAL_THERMAL_ROTOR_PAIR_CLEARANCE_ASSUMPTIONS_ONLY"
    assert result["analytical_screen_passed"]
    assert not result["thermal_conditions_and_material_bounds_independently_measured"]
    assert not result["actual_hot_or_cold_3d_rotor_clearance_validated"]
    assert not result["real_world_airworthiness_established"]
    assert not result["flight_release_authorized"]


def test_unsupported_large_expansion_blocks_positive_analytic_gap():
    m, t = fixture()
    t["diameter_abs_expansion_coeff_upper_per_k"] = [.1]*4
    result = run(m, t)
    assert result["status"] == "THERMALLY_BOUNDED_ROTOR_PAIR_CLEARANCE_NOT_ESTABLISHED"
    assert not result["analytical_screen_passed"]


def test_zero_thermal_growth_leaves_input_hard_bounds_unchanged():
    m, t = fixture()
    t["temperature_excursion_hard_bounds_k"] = [0]*4
    expanded, increments = apply_thermal_rotor_hard_bounds(
        design(), rotor_pair_motion_case=m, thermal_case=t
    )
    assert expanded["maximum_swept_heights_m"] == m["maximum_swept_heights_m"]
    assert expanded["diameter_hard_bounds_m"] == m["diameter_hard_bounds_m"]
    assert expanded["center_position_hard_bounds_m"] == m["center_position_hard_bounds_m"]
    assert all(x["additional_diameter_error_m"] == 0 for x in increments)


@pytest.mark.parametrize("key,bad", [
    ("temperature_excursion_hard_bounds_k", -1),
    ("temperature_excursion_hard_bounds_k", float("nan")),
    ("diameter_abs_expansion_coeff_upper_per_k", True),
    ("height_abs_expansion_coeff_upper_per_k", float("inf")),
    ("arm_abs_expansion_coeff_upper_per_k", -1),
])
def test_unsupported_thermal_hard_values_rejected(key, bad):
    m, t = fixture()
    t[key][0] = bad
    with pytest.raises(ValueError, match="finite and nonnegative"):
        run(m, t)


def test_source_absence_and_per_rotor_count_mismatch_rejected():
    m, t = fixture()
    t["material_expansion_source"] = ""
    with pytest.raises(ValueError, match="material_expansion_source"):
        run(m, t)
    m, t = fixture()
    t["temperature_excursion_hard_bounds_k"] = [20]
    with pytest.raises(ValueError, match="per-rotor"):
        run(m, t)


def test_excessive_finite_temperature_times_expansion_overflows_fail_closed():
    m, t = fixture()
    t["temperature_excursion_hard_bounds_k"] = [1e308]*4
    t["diameter_abs_expansion_coeff_upper_per_k"] = [1e308]*4
    with pytest.raises(ValueError, match="overflow"):
        run(m, t)


def test_unverified_flex_or_expansion_claim_cannot_authorize_flight():
    m, t = fixture()
    t["actual_hot_cold_test_approved"] = True
    with pytest.raises(ValueError, match="exact independent thermal"):
        run(m, t)
