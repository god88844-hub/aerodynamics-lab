"""P0D-015: Vision, ES-EKF localization, A* navigation, and synthetic vs hardware separation."""

from __future__ import annotations

import pytest

from physics.autonomy.ekf_estimator import run_ekf_fusion_verification
from physics.autonomy.sitl_and_swarms import localize_fiducial_apriltag_proxy, plan_obstacle_free_path


def test_p0d_015_ekf_fusion_astar_navigation_and_vision_loss():
    ekf = run_ekf_fusion_verification(seed=42)
    assert ekf["mean_ekf_err_m"] < ekf["mean_raw_gps_err_m"]

    path = plan_obstacle_free_path(start_xy=(0, 0), goal_xy=(6, 0), blocked_cells={(3, 0), (3, 1)})
    assert path[0] == (0, 0) and path[-1] == (6, 0)
    assert (3, 0) not in path

    out_of_fov = localize_fiducial_apriltag_proxy(tag_world_m=(12.0, 0.0, 4.0), camera_pos_m=(0.0, 0.0, 4.0))
    assert out_of_fov["detected"] is False
    assert out_of_fov["channel_provenance"] == "SYNTHETIC"

    with pytest.raises(ValueError, match="blocked"):
        plan_obstacle_free_path(start_xy=(3, 0), goal_xy=(6, 0), blocked_cells={(3, 0)})
