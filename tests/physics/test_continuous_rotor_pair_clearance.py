"""M28.10 synthetic rotor-pair speed enclosures never certify actual motion."""
from copy import deepcopy
from pathlib import Path

import pytest
from aeroforge_schemas.design import DroneDesign
from physics.structures.continuous_rotor_pair_clearance import screen_continuous_rotor_pair_clearance

ROOT=Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT/"data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def fixture():
    centers=[list(rotor.position_m) for rotor in reference().rotors]
    return {
        "installed_rotor_diameters_m":[.381]*4,
        "maximum_swept_heights_m":[.02]*4,
        "diameter_hard_bounds_m":[0]*4,
        "center_position_hard_bounds_m":[0]*4,
        "center_speed_hard_bounds_m_per_s":[0]*4,
        "time_samples":[
            {"time_s":0,"rotor_centers_m":deepcopy(centers)},
            {"time_s":1,"rotor_centers_m":deepcopy(centers)},
        ],
        "minimum_declared_pair_gap_m":.01,
        "trajectory_source":"synthetic fixed rotor center positions",
        "geometry_hard_bound_source":"synthetic nominal propeller geometry",
        "rotor_center_speed_source":"hypothetical zero speed",
    }


def audit(body=None):
    return screen_continuous_rotor_pair_clearance(
        reference(),**(fixture() if body is None else body)
    )


def test_all_static_pairs_have_conditional_3d_clearance_but_no_physical_certification():
    body=fixture()
    old=deepcopy(body)
    result=audit(body)
    assert body==old
    assert result["status"]=="ANALYTICAL_CONTINUOUS_ROTOR_PAIR_SEPARATION_ASSUMPTIONS_ONLY"
    assert result["analytical_screen_passed"]
    assert result["pair_count"]==6
    assert result["minimum_analytical_full_interval_gap_m"]>.11
    assert not result["continuous_rotor_motion_bounds_independently_authenticated"]
    assert not result["actual_rotor_dynamic_collision_test_passed"]
    assert not result["real_world_flightworthiness_established"]
    assert not result["flight_release_authorized"]


def test_rapid_possible_motion_prevents_claiming_continuous_clearance():
    body=fixture()
    body["center_speed_hard_bounds_m_per_s"]=[1]*4
    result=audit(body)
    assert not result["analytical_screen_passed"]
    assert result["status"]=="CONTINUOUS_ROTOR_PAIR_CLEARANCE_NOT_ESTABLISHED"


def test_small_declared_speed_reduces_continuous_minimum_gap():
    body=fixture()
    body["center_speed_hard_bounds_m_per_s"]=[.01]*4
    result=audit(body)
    assert result["analytical_screen_passed"]
    assert result["minimum_analytical_full_interval_gap_m"]<audit()["minimum_analytical_full_interval_gap_m"]


def test_trajectory_incompatible_with_speed_hard_bound_rejected():
    body=fixture()
    body["time_samples"][1]["rotor_centers_m"][0][0]+=.5
    with pytest.raises(ValueError,match="contradicts declared speed"):
        audit(body)


def test_center_error_can_admit_displaced_samples_but_not_necessarily_clearance():
    body=fixture()
    body["center_position_hard_bounds_m"]=[.3]*4
    body["time_samples"][1]["rotor_centers_m"][0][0]+=.5
    result=audit(body)
    assert not result["analytical_screen_passed"]


@pytest.mark.parametrize("bad",[-1,float("nan"),float("inf"),True])
def test_invalid_speed_bounds_rejected(bad):
    body=fixture()
    body["center_speed_hard_bounds_m_per_s"][0]=bad
    with pytest.raises(ValueError,match="finite"):
        audit(body)


def test_nonincreasing_timestamps_fail_closed():
    body=fixture()
    body["time_samples"][1]["time_s"]=0
    with pytest.raises(ValueError,match="strictly increases"):
        audit(body)


def test_missing_rotor_cannot_be_skipped_in_snapshots():
    body=fixture()
    body["time_samples"][1]["rotor_centers_m"].pop()
    with pytest.raises(ValueError,match="one 3D center"):
        audit(body)


def test_outer_envelope_hard_bounds_overflow_rejected():
    body=fixture()
    body["diameter_hard_bounds_m"]=[1e308]*4
    with pytest.raises(ValueError,match="overflow"):
        audit(body)


def test_unknown_source_cannot_generate_an_analytic_pass():
    body=fixture()
    body["rotor_center_speed_source"]=""
    with pytest.raises(ValueError,match="rotor_center_speed_source"):
        audit(body)
