"""M28.8 declared aircraft obstacle inventory completeness and rotor clearance audit.

All completeness statements are limited to the operator's explicitly
declared target list; they cannot prove no unlisted actual hardware exists.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_obstacle_clearance import screen_rotor_to_obstacle_spheres

_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def audit_declared_obstacle_inventory(
    design: DroneDesign,
    *,
    expected_obstacle_ids: Sequence[str],
    obstacle_spheres: Sequence[Mapping],
    installed_rotor_diameters_m: Sequence[float],
    rotor_swept_heights_m: Sequence[float],
    rotor_center_motion_hard_bounds_m: Sequence[float],
    rotor_diameter_hard_bounds_m: Sequence[float],
    minimum_3d_gap_m: float,
    expected_inventory_source: str,
    rotor_source: str,
    obstacle_source: str,
    hard_bounds_source: str,
) -> dict:
    """Reject a missing declared obstacle before evaluating any rotor-to-object pair."""
    if isinstance(expected_obstacle_ids, (str, bytes)) or not isinstance(expected_obstacle_ids, Sequence):
        raise ValueError("explicit expected obstacle inventory required")
    if not 1 <= len(expected_obstacle_ids) <= 128:
        raise ValueError("declared inventory must list 1–128 obstacles")
    if any(not isinstance(x, str) or not _NAME.fullmatch(x) for x in expected_obstacle_ids):
        raise ValueError("invalid expected obstacle identifier")
    expected = set(expected_obstacle_ids)
    if len(expected) != len(expected_obstacle_ids):
        raise ValueError("duplicate expected obstacle identifier")
    if not isinstance(expected_inventory_source, str) or not 1 <= len(expected_inventory_source.strip()) <= 500:
        raise ValueError("expected inventory provenance required")
    if isinstance(obstacle_spheres, (str, bytes)) or not isinstance(obstacle_spheres, Sequence):
        raise ValueError("explicit obstacle envelopes required")
    ids = []
    for obs in obstacle_spheres:
        if not isinstance(obs, Mapping) or not isinstance(obs.get("obstacle_id"), str):
            raise ValueError("each obstacle must supply its inventory identifier")
        ids.append(obs["obstacle_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate actual declared obstacle identifier")
    supplied = set(ids)
    if supplied != expected:
        raise ValueError("declared obstacle inventory incomplete or contains unexpected obstacle")
    geo = screen_rotor_to_obstacle_spheres(
        design,
        rotor_diameters_m=installed_rotor_diameters_m,
        rotor_swept_heights_m=rotor_swept_heights_m,
        rotor_center_motion_hard_bounds_m=rotor_center_motion_hard_bounds_m,
        rotor_diameter_hard_bounds_m=rotor_diameter_hard_bounds_m,
        obstacle_spheres=obstacle_spheres,
        minimum_3d_gap_m=minimum_3d_gap_m,
        rotor_source=rotor_source,
        obstacle_source=obstacle_source,
        hard_bounds_source=hard_bounds_source,
    )
    canonical_inventory = {
        "design_name": design.name,
        "expected_obstacle_ids": sorted(expected),
        "expected_inventory_source_operator_supplied": expected_inventory_source.strip(),
        "rotor_count": len(design.rotors),
    }
    digest = hashlib.sha256(
        json.dumps(canonical_inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    passed = geo["analytical_screen_passed"]
    return {
        "status": ("DECLARED_OBSTACLE_INVENTORY_SCREENED_ANALYTICALLY_ONLY" if passed
                   else "DECLARED_ROTOR_OBSTACLE_CLEARANCE_NOT_ESTABLISHED"),
        "declared_inventory_digest_sha256": digest,
        "declared_inventory_count": len(expected),
        "declared_inventory_exactly_covered": True,
        "analytical_screen_passed": passed,
        "geometry_report": geo,
        "actual_aircraft_obstacle_inventory_authenticated": False,
        "installed_geometry_hard_bounds_independently_verified": False,
        "real_world_rotor_frame_collision_clearance_established": False,
        "aircraft_flightworthiness_established": False,
        "manufacturing_or_flight_release_authorized": False,
        "limitations": [
            "Exact completeness applies only to an operator-declared list; absent real parts remain unrecognized",
            "Bounding spheres and all rotor center-travel hard errors are user-declared",
            "Frame CAD, hardware identity, physical blade motion and qualified inspection not verified",
        ],
    }
