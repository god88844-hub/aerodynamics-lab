"""M28.8 synthetic obstacle inventory completeness is not as-built completeness."""
from pathlib import Path
from copy import deepcopy

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.structures.obstacle_inventory import audit_declared_obstacle_inventory

ROOT = Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def obstacle(name, center, radius=.02):
    return {
        "obstacle_id": name, "center_m": list(center),
        "outer_radius_m": radius, "center_hard_bound_m": 0,
        "radius_hard_bound_m": 0,
    }


def fixture():
    return {
        "expected_obstacle_ids": ["frame", "landing_gear"],
        "obstacle_spheres": [
            obstacle("frame", (0, 0, 0)),
            obstacle("landing_gear", (0, 0, -1)),
        ],
        "installed_rotor_diameters_m": [.381]*4,
        "rotor_swept_heights_m": [.02]*4,
        "rotor_center_motion_hard_bounds_m": [0]*4,
        "rotor_diameter_hard_bounds_m": [0]*4,
        "minimum_3d_gap_m": .01,
        "expected_inventory_source": "synthetic operator-defined inventory, not actual BOM",
        "rotor_source": "synthetic",
        "obstacle_source": "synthetic",
        "hard_bounds_source": "synthetic, not measured",
    }


def test_declared_exact_inventory_screened_but_never_physically_authenticated():
    d = reference()
    req = fixture()
    original = deepcopy(req)
    r = audit_declared_obstacle_inventory(d, **req)
    assert req == original
    assert r["declared_inventory_exactly_covered"]
    assert r["declared_inventory_count"] == 2
    assert len(r["declared_inventory_digest_sha256"]) == 64
    assert len(r["geometry_report"]["pairs"]) == 8
    assert r["analytical_screen_passed"]
    assert not r["actual_aircraft_obstacle_inventory_authenticated"]
    assert not r["real_world_rotor_frame_collision_clearance_established"]
    assert not r["manufacturing_or_flight_release_authorized"]


def test_missing_or_surplus_obstacle_refused_before_geometry_pass():
    req = fixture()
    req["obstacle_spheres"] = req["obstacle_spheres"][:1]
    with pytest.raises(ValueError, match="incomplete or contains unexpected"):
        audit_declared_obstacle_inventory(reference(), **req)
    req = fixture()
    req["obstacle_spheres"].append(obstacle("antenna", (0, 0, .5)))
    with pytest.raises(ValueError, match="incomplete or contains unexpected"):
        audit_declared_obstacle_inventory(reference(), **req)


def test_duplicate_expected_or_declared_objects_rejected():
    req = fixture()
    req["expected_obstacle_ids"][1] = "frame"
    with pytest.raises(ValueError, match="duplicate expected"):
        audit_declared_obstacle_inventory(reference(), **req)
    req = fixture()
    req["obstacle_spheres"][1]["obstacle_id"] = "frame"
    with pytest.raises(ValueError, match="duplicate actual"):
        audit_declared_obstacle_inventory(reference(), **req)


def test_expected_inventory_order_does_not_change_canonical_digest():
    req = fixture()
    a = audit_declared_obstacle_inventory(reference(), **req)
    req["expected_obstacle_ids"].reverse()
    req["obstacle_spheres"].reverse()
    b = audit_declared_obstacle_inventory(reference(), **req)
    assert a["declared_inventory_digest_sha256"] == b["declared_inventory_digest_sha256"]


def test_obstacle_collision_blocks_even_with_complete_operator_inventory():
    req = fixture()
    req["obstacle_spheres"][0]["center_m"] = [.25, .25, .02]
    result = audit_declared_obstacle_inventory(reference(), **req)
    assert result["declared_inventory_exactly_covered"]
    assert result["status"] == "DECLARED_ROTOR_OBSTACLE_CLEARANCE_NOT_ESTABLISHED"
    assert not result["analytical_screen_passed"]


def test_empty_expected_inventory_or_no_provenance_rejected():
    req = fixture()
    req["expected_obstacle_ids"] = []
    with pytest.raises(ValueError, match="1–128"):
        audit_declared_obstacle_inventory(reference(), **req)
    req = fixture()
    req["expected_inventory_source"] = ""
    with pytest.raises(ValueError, match="provenance required"):
        audit_declared_obstacle_inventory(reference(), **req)
