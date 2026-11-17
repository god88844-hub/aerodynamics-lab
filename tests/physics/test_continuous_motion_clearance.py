"""Synthetic M28.9 motion bounds do not prove actual rotor/airframe clearance."""
from copy import deepcopy
from pathlib import Path
import pytest

from aeroforge_schemas.design import DroneDesign
from physics.structures.continuous_motion_clearance import screen_continuous_motion_clearance

ROOT = Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def fixture():
    d = reference()
    rotor_positions = [list(rotor.position_m) for rotor in d.rotors]
    return {
        "rotor_diameters_m": [.381]*4,
        "rotor_swept_heights_m": [.02]*4,
        "rotor_diameter_hard_bounds_m": [0]*4,
        "rotor_center_position_hard_bounds_m": [0]*4,
        "rotor_center_speed_hard_bounds_m_per_s": [0]*4,
        "obstacle_envelopes": [{
            "obstacle_id": "frame",
            "outer_radius_m": .02, "outer_radius_hard_bound_m": 0,
            "center_position_hard_bound_m": 0,
            "center_speed_hard_bound_m_per_s": 0,
        }],
        "time_samples": [
            {"time_s": 0, "rotor_centers_m": deepcopy(rotor_positions),
             "obstacle_centers_m": [[0,0,0]]},
            {"time_s": 1, "rotor_centers_m": deepcopy(rotor_positions),
             "obstacle_centers_m": [[0,0,0]]},
        ],
        "minimum_declared_clearance_m": .01,
        "trajectory_source": "synthetic unmeasured centers",
        "hard_bounds_source": "hypothetical strict speeds and hard radii",
        "obstacle_inventory_source": "synthetic frame only, not as-built whole aircraft",
    }


def audit(data=None):
    return screen_continuous_motion_clearance(reference(), **(fixture() if data is None else data))


def test_static_declared_finite_horizon_analytic_clearance_is_not_flight_validation():
    data = fixture()
    old = deepcopy(data)
    report = audit(data)
    assert data == old
    assert report["status"] == "ANALYTICAL_DECLARED_CONTINUOUS_TRAJECTORY_NONINTERSECTION_ONLY"
    assert report["sample_count"] == 2
    assert report["time_span_s"] == 1
    assert len(report["pair_summaries"]) == 4
    assert report["minimum_continuous_analytical_gap_lower_m"] > .1
    assert report["analytical_screen_passed"]
    assert not report["continuous_speed_hard_bounds_independently_verified"]
    assert not report["actual_airframe_obstacle_inventory_authenticated"]
    assert not report["real_world_dynamic_collision_validation_established"]
    assert not report["flight_release_authorized"]


def test_declared_fast_unsampled_motion_blocks_even_if_sampled_endpoints_clean():
    data = fixture()
    data["rotor_center_speed_hard_bounds_m_per_s"] = [1]*4
    report = audit(data)
    assert report["status"] == "DECLARED_CONTINUOUS_TRAJECTORY_CLEARANCE_NOT_ESTABLISHED"
    assert not report["analytical_screen_passed"]
    assert all(p["collision_or_contact_cannot_be_excluded"] for p in report["pair_summaries"])


def test_slow_motion_tightens_but_does_not_invalidate_math():
    data = fixture()
    data["rotor_center_speed_hard_bounds_m_per_s"] = [.01]*4
    report = audit(data)
    assert report["analytical_screen_passed"]
    assert report["minimum_continuous_analytical_gap_lower_m"] < audit()["minimum_continuous_analytical_gap_lower_m"]


def test_endpoint_displacement_larger_than_claimed_speed_is_rejected():
    data = fixture()
    data["time_samples"][1]["rotor_centers_m"][0][0] += .5
    with pytest.raises(ValueError, match="speed bound contradicts"):
        audit(data)
    data = fixture()
    data["time_samples"][1]["obstacle_centers_m"][0][0] += .5
    with pytest.raises(ValueError, match="speed bound contradicts"):
        audit(data)


def test_unsampled_obstacles_cannot_be_treated_as_checked():
    data = fixture()
    data["obstacle_envelopes"] = []
    with pytest.raises(ValueError, match="1–128"):
        audit(data)


def test_nonincreasing_or_nonzero_start_time_refused():
    data = fixture()
    data["time_samples"][1]["time_s"] = 0
    with pytest.raises(ValueError, match="strictly increase"):
        audit(data)
    data = fixture()
    data["time_samples"][0]["time_s"] = 1
    data["time_samples"][1]["time_s"] = 2
    with pytest.raises(ValueError, match="begin at time zero"):
        audit(data)


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True])
def test_invalid_speed_and_dimensions_fail_closed(bad):
    data = fixture()
    data["rotor_center_speed_hard_bounds_m_per_s"][0] = bad
    with pytest.raises(ValueError, match="finite"):
        audit(data)


def test_impossible_large_accumulated_bounds_rejected():
    data = fixture()
    data["obstacle_envelopes"][0]["outer_radius_m"] = 1e308
    data["obstacle_envelopes"][0]["outer_radius_hard_bound_m"] = 1e308
    with pytest.raises(ValueError, match="overflow"):
        audit(data)


def test_wrong_number_of_time_slice_centers_refused():
    data = fixture()
    data["time_samples"][1]["rotor_centers_m"].pop()
    with pytest.raises(ValueError, match="one center per rotor"):
        audit(data)
