"""Synthetic rotor sphere tests do not establish measured flight clearance."""
from pathlib import Path

import pytest
from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_sphere_clearance import screen_orientation_independent_rotor_envelopes

ROOT = Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def run(design=None, *, diameter=.381, height=.02,
        center_xy_error=0, center_z_error=0, diameter_error=0, requested=.01):
    return screen_orientation_independent_rotor_envelopes(
        design or reference(),
        installed_diameters_m=[diameter]*4,
        maximum_swept_heights_m=[height]*4,
        xy_center_hard_bounds_m=[center_xy_error]*4,
        z_center_hard_bounds_m=[center_z_error]*4,
        diameter_hard_bounds_m=[diameter_error]*4,
        minimum_required_3d_clearance_m=requested,
        geometry_source="synthetic unmeasured rotor geometry",
        hard_bound_source="synthetic absolute error enclosures",
        center_motion_source="synthetic assumed rotor center travel",
    )


def test_spheres_bound_rotors_without_claiming_physical_validation():
    result = run()
    assert result["status"] == "ANALYTICAL_ORIENTATION_INDEPENDENT_SPHERE_SEPARATION_ONLY"
    nominal_radius = (.381**2 / 4 + .02**2 / 4) ** .5
    assert result["minimum_conservative_3d_separation_m"] == pytest.approx(.5 - 2*nominal_radius)
    assert len(result["pairs"]) == 6
    assert result["analytical_screen_passed"]
    assert not result["physical_center_motion_bounds_authenticated"]
    assert not result["actual_blade_interference_physically_validated"]
    assert not result["real_aircraft_flightworthiness_established"]
    assert not result["release_authorized"]


def test_large_uncertainties_block_even_if_nominal_geometry_clear():
    result = run(center_xy_error=.08)
    assert result["status"] == "ORIENTATION_INDEPENDENT_SEPARATION_NOT_ESTABLISHED"
    assert not result["analytical_screen_passed"]


def test_vertical_separation_can_allow_3d_sphere_nonintersection():
    d = reference()
    d.rotors[1].position_m = [.25, .25, 1.0]
    result = run(d)
    pair = next(p for p in result["pairs"] if p["rotor_a"] == 0 and p["rotor_b"] == 1)
    assert pair["orientation_independent_3d_separation_lower_m"] == pytest.approx(1.0 - 2 * ((.381**2 + .02**2) ** .5 / 2))
    assert result["analytical_screen_passed"]


def test_unknown_center_travel_cannot_be_ignored():
    result = run(center_z_error=.25)
    assert not result["analytical_screen_passed"]


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), True])
def test_bad_rotor_dimensions_fail_closed(bad):
    with pytest.raises(ValueError, match="finite and nonnegative|positive"):
        run(diameter=bad)


def test_huge_hard_bound_cannot_overflow_to_an_apparent_success():
    with pytest.raises(ValueError, match="overflow"):
        run(center_xy_error=1e308, center_z_error=1e308)


def test_missing_motion_source_refused():
    with pytest.raises(ValueError, match="center_motion_source"):
        screen_orientation_independent_rotor_envelopes(
            reference(), [.381]*4, [.02]*4, [0]*4, [0]*4, [0]*4,
            minimum_required_3d_clearance_m=.01,
            geometry_source="synthetic", hard_bound_source="synthetic",
            center_motion_source="",
        )
