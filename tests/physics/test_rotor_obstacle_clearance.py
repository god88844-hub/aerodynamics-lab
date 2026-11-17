"""M28.7 declared obstacle-only fixtures, not full real-aircraft collision proof."""
from pathlib import Path

import pytest
from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_obstacle_clearance import screen_rotor_to_obstacle_spheres

ROOT = Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def obstacle(*, center=(0, 0, 0), radius=.02, center_bound=0, radius_bound=0, name="synthetic_frame"):
    return {
        "obstacle_id": name, "center_m": list(center),
        "outer_radius_m": radius,
        "center_hard_bound_m": center_bound,
        "radius_hard_bound_m": radius_bound,
    }


def run(*, obstacles=None, minimum=.01, rotor_center_error=0, diameter_error=0):
    return screen_rotor_to_obstacle_spheres(
        reference(),
        rotor_diameters_m=[.381] * 4,
        rotor_swept_heights_m=[.02] * 4,
        rotor_center_motion_hard_bounds_m=[rotor_center_error]*4,
        rotor_diameter_hard_bounds_m=[diameter_error]*4,
        obstacle_spheres=obstacles if obstacles is not None else [obstacle()],
        minimum_3d_gap_m=minimum,
        rotor_source="synthetic nominal rotor layout",
        obstacle_source="hypothetical frame object",
        hard_bounds_source="unverified nominal hard error bounds",
    )


def test_included_center_obstacle_analytical_clearance_is_noncertifying():
    r = run()
    assert r["analytical_screen_passed"]
    assert r["declared_obstacle_count"] == 1
    assert r["minimum_conservative_obstacle_gap_m"] == pytest.approx(
        (0.25**2+0.25**2+.02**2)**.5 - (.381**2/4+.02**2/4)**.5 - .02
    )
    assert not r["obstacle_inventory_completeness_authenticated"]
    assert not r["physical_assembly_collision_validation_established"]
    assert not r["real_world_flightworthiness_established"]


def test_sphere_overlap_blocks_positive_screen():
    r = run(obstacles=[obstacle(center=(.25, .25, .02), radius=.01)])
    assert r["status"] == "DECLARED_ROTOR_OBSTACLE_SEPARATION_NOT_ESTABLISHED"
    assert not r["analytical_screen_passed"]
    assert any(p["possible_contact_or_intersection"] for p in r["pairs"])


def test_large_obstacle_or_center_uncertainty_refuses_clearance():
    r = run(obstacles=[obstacle(radius=.3)])
    assert not r["analytical_screen_passed"]
    r = run(rotor_center_error=.2)
    assert not r["analytical_screen_passed"]


def test_missing_obstacle_inventory_rejected_not_silently_passed():
    with pytest.raises(ValueError, match="1–128"):
        run(obstacles=[])


def test_duplicate_obstacle_name_and_unknown_fields_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        run(obstacles=[obstacle(), obstacle(center=(0,0,1))])
    obs = obstacle()
    obs["physically_measured"] = True
    with pytest.raises(ValueError, match="exact"):
        run(obstacles=[obs])


@pytest.mark.parametrize("radius,bound", [(-.1,0), (0,0), (float("inf"),0), (.02,float("nan")), (.02,-1)])
def test_invalid_obstacle_bounds_are_errors(radius, bound):
    with pytest.raises(ValueError, match="finite|positive"):
        run(obstacles=[obstacle(radius=radius,center_bound=bound)])


def test_pair_separation_overflow_refused():
    with pytest.raises(ValueError, match="overflow"):
        run(obstacles=[obstacle(radius=1e308,radius_bound=1e308)])


def test_explicit_gear_and_body_objects_evaluated_individually():
    r = run(obstacles=[obstacle(name="body"),obstacle(name="landing_gear",center=(0,0,-1))])
    assert len(r["pairs"]) == 8
    assert r["declared_obstacle_count"] == 2
    assert not r["obstacle_inventory_completeness_authenticated"]
