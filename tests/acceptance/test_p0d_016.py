"""P0D-016: Obstacle avoidance, geofences, perception failures, and manual operator overrides."""

from __future__ import annotations

import pytest

from physics.autonomy.sitl_and_swarms import evaluate_geofence_and_override, plan_obstacle_free_path


def test_p0d_016_geofence_override_and_unavailable_avoidance_fail():
    nom = evaluate_geofence_and_override(position_m=(10.0, 5.0, 2.0), geofence_radius_m=50.0, min_obstacle_clearance_m=2.0)
    assert nom["decision"] == "NOMINAL_AUTONOMOUS"
    assert nom["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    breach = evaluate_geofence_and_override(position_m=(60.0, 0.0, 2.0), geofence_radius_m=50.0)
    assert breach["decision"] == "GEOFENCE_BREACH_RTL"
    assert breach["verdict"] == "FAIL"

    override = evaluate_geofence_and_override(position_m=(60.0, 0.0, 2.0), geofence_radius_m=50.0, manual_override_active=True)
    assert override["decision"] == "MANUAL_OPERATOR_OVERRIDE"
    assert override["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    no_auth = evaluate_geofence_and_override(position_m=(5.0, 0.0, 2.0), min_obstacle_clearance_m=0.2, avoidance_authority_available=False)
    assert no_auth["decision"] == "AVOIDANCE_UNAVAILABLE_FAIL"
    assert no_auth["verdict"] == "FAIL"

    with pytest.raises(ValueError, match="outside geofence"):
        plan_obstacle_free_path(start_xy=(0, 0), goal_xy=(40, 0), blocked_cells=set(), geofence_radius_cells=25)
