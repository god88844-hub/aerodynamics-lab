"""M28.5 geometry tests are mathematical fixtures, never actual aircraft measurements."""
from pathlib import Path

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.structures.swept_cylinder_clearance import screen_3d_rotor_swept_envelopes


ROOT = Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def run(design=None, *, diameters=None, heights=None, xy_error=0,
        z_error=0, diameter_error=0, clearance=0.01, alignment=True):
    return screen_3d_rotor_swept_envelopes(
        design or reference(),
        installed_diameters_m=diameters if diameters is not None else [0.381]*4,
        swept_vertical_heights_m=heights if heights is not None else [0.02]*4,
        xy_center_hard_bounds_m=[xy_error]*4,
        z_center_hard_bounds_m=[z_error]*4,
        diameter_hard_bounds_m=[diameter_error]*4,
        required_clearance_m=clearance,
        geometry_source="synthetic fixture",
        hard_bound_source="hypothetical worst-case errors",
        axes_parallel_body_z_declared=alignment,
        axis_alignment_source="synthetic upright motor-mount assumption",
    )


def test_reference_nominal_3d_gap_math_not_physical_evidence():
    result = run()
    assert result["status"] == "ANALYTICAL_ASSUMED_3D_CYLINDER_NONINTERSECTION_ONLY"
    assert result["conservative_minimum_3d_separation_m"] == pytest.approx(.119)
    assert len(result["pairs"]) == 6
    assert result["analytical_screen_passed"]
    assert not result["original_as_built_measurements_authenticated"]
    assert not result["actual_dynamic_rotor_3d_clearance_validated"]
    assert not result["flightworthiness_established"]


def test_overlapping_xy_disks_can_be_separated_by_large_known_z_gap():
    d = reference()
    d.rotors[1].position_m = [-.25, .25, .2]
    result = run(d, diameters=[.55, .55, .05, .05], heights=[.02]*4)
    pair = next(p for p in result["pairs"] if p["rotor_a"] == 0 and p["rotor_b"] == 1)
    assert pair["minimum_xy_gap_m"] < 0
    assert pair["minimum_axial_gap_m"] == pytest.approx(.16)
    assert pair["conservative_3d_separation_lower_m"] == pytest.approx(.16)
    assert result["analytical_screen_passed"]
    assert not result["actual_dynamic_rotor_3d_clearance_validated"]


def test_same_nominal_geometry_fails_if_z_position_error_unknown_or_large():
    d = reference()
    d.rotors[1].position_m = [-.25, .25, .2]
    result = run(d, diameters=[.55, .55, .05, .05], z_error=.19)
    pair = next(p for p in result["pairs"] if p["rotor_a"] == 0 and p["rotor_b"] == 1)
    assert pair["possible_intersection_or_contact"]
    assert not result["analytical_screen_passed"]


def test_nominal_rotor_swept_overlap_is_not_approved():
    result = run(diameters=[.55]*4)
    assert result["status"] == "3D_SWEPT_ENVELOPE_SEPARATION_NOT_ESTABLISHED"
    assert not result["analytical_screen_passed"]
    assert any(p["possible_intersection_or_contact"] for p in result["pairs"])


@pytest.mark.parametrize("bad", [-1, True, float("nan"), float("inf")])
def test_invalid_hard_bounds_fail_closed(bad):
    with pytest.raises(ValueError, match="finite and nonnegative"):
        run(xy_error=bad)


def test_unknown_axis_orientation_does_not_get_fake_clearance():
    with pytest.raises(ValueError, match="body-Z-parallel"):
        run(alignment=False)


def test_zero_swept_height_is_rejected():
    with pytest.raises(ValueError, match="positive swept"):
        run(heights=[0]*4)


def test_overflowed_geometry_rejected():
    with pytest.raises(ValueError, match="overflow"):
        run(diameters=[1e308]*4)


def test_more_than_assumed_clearance_requirement_fails():
    result = run(clearance=.2)
    assert not result["analytical_screen_passed"]
