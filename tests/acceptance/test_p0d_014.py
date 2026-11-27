"""P0D-014: Timestamped synthetic camera, LiDAR, IMU/GPS sensor streams decoupled from plant state."""

from __future__ import annotations

from physics.autonomy.sitl_and_swarms import generate_synthetic_lidar_scan, localize_fiducial_apriltag_proxy


def test_p0d_014_synthetic_camera_and_lidar_provenance():
    scan = generate_synthetic_lidar_scan(
        sensor_pos_m=(0.0, 0.0, 2.0),
        obstacles=[{"center_m": [3.0, 0.0, 2.0], "size_m": [1.0, 2.0, 4.0]}],
        n_rays=36,
    )
    assert scan["channel_provenance"] == "SYNTHETIC"
    assert scan["dataset_kind"] == "synthetic"
    assert min(scan["ranges_m"]) == 2.5

    cam = localize_fiducial_apriltag_proxy(tag_world_m=(0.4, 0.2, 0.0), camera_pos_m=(0.0, 0.0, 4.0))
    assert cam["detected"] is True
    assert cam["channel_provenance"] == "SYNTHETIC"
    assert cam["physical_validation_status"] == "UNVALIDATED"
