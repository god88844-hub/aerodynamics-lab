"""Slice 0D software verification: Adverse weather (wind/rain/icing), SITL bridges, synthetic LiDAR, A*, and swarms."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from physics.autonomy.sitl_and_swarms import (
    SitlLockstepBridge,
    generate_synthetic_lidar_scan,
    plan_obstacle_free_path,
    run_multi_drone_swarm,
)
from physics.environment.adverse_weather import (
    evaluate_icing_and_shedding,
    evaluate_rain_wet_effects,
    evaluate_spatial_turbulence,
)

ROOT = Path(__file__).resolve().parents[2]


def test_adverse_weather_turbulence_rain_icing_and_refusals(tmp_path):
    g1 = evaluate_spatial_turbulence(altitude_m=30.0, mean_wind_10m_m_s=(5.0, 1.0, 0.0), turbulence_intensity=0.15, seed=11)
    g2 = evaluate_spatial_turbulence(altitude_m=30.0, mean_wind_10m_m_s=(5.0, 1.0, 0.0), turbulence_intensity=0.15, seed=11)
    assert g1["gust_samples_m_s"] == g2["gust_samples_m_s"]

    wet = evaluate_rain_wet_effects(rain_mm_h=25.0)
    assert wet["wet_cl_max"] < 1.45 and wet["wet_cd0"] > 0.025
    with pytest.raises(ValueError, match="Extreme precipitation"):
        evaluate_rain_wet_effects(rain_mm_h=150.0)

    ice = evaluate_icing_and_shedding(oat_c=-4.0, lwc_g_m3=0.6, exposure_s=120.0, anti_ice_power_w=8.0)
    assert ice["icing_active"] is True and ice["accreted_mass_kg"] > 0.0 and ice["shedding_event"] is True

    in_path = tmp_path / "wx_in.json"
    out_path = tmp_path / "wx_out.json"
    in_path.write_text(json.dumps({"rain_mm_h": 12.0, "oat_c": -3.0, "lwc_g_m3": 0.4, "exposure_s": 60.0}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "adverse-weather", str(in_path), str(out_path)], check=True, cwd=ROOT)
    assert json.loads(out_path.read_text(encoding="utf-8"))["rain"]["status"] == "SUPPORTED_WITH_CAVEATS"


def test_sitl_lockstep_synthetic_lidar_astar_and_swarm(tmp_path):
    ardupilot = SitlLockstepBridge(firmware_kind="ardupilot", dt_s=0.004, n_actuators=4)
    px4 = SitlLockstepBridge(firmware_kind="px4", dt_s=0.004, n_actuators=4)
    pkt1 = ardupilot.step_packet(pos_ned_m=(0.0, 0.0, -2.0), vel_ned_m_s=(0.0, 0.0, 0.0), bus_voltage_v=24.8, pwm_commands=[0.5, 0.5, 0.5, 0.5])
    pkt2 = px4.step_packet(pos_ned_m=(0.0, 0.0, -2.0), vel_ned_m_s=(0.0, 0.0, 0.0), bus_voltage_v=24.8, pwm_commands=[0.5, 0.5, 0.5, 0.5])
    assert pkt1["time_usec"] == 0 and pkt2["protocol"] == "px4_lockstep_1"

    scan = generate_synthetic_lidar_scan(
        sensor_pos_m=(0.0, 0.0, 0.5),
        obstacles=[{"center_m": (4.0, 0.0, 0.5), "size_m": (1.0, 2.0, 2.0)}],
        n_rays=8,
        max_range_m=20.0,
    )
    assert scan["channel_provenance"] == "SYNTHETIC"
    assert scan["ranges_m"][0] == pytest.approx(3.5, abs=1e-4)

    path = plan_obstacle_free_path(start_xy=(0, 0), goal_xy=(4, 0), blocked_cells={(2, 0), (2, 1), (2, -1)}, geofence_radius_cells=10)
    assert path[0] == (0, 0) and path[-1] == (4, 0)
    assert (2, 0) not in path

    swarm_ok = run_multi_drone_swarm(
        initial_positions_m=[(0.0, 0.0, 2.0), (5.0, 0.0, 2.0), (0.0, 5.0, 2.0)],
        target_positions_m=[(1.0, 0.0, 3.0), (6.0, 0.0, 3.0), (1.0, 5.0, 3.0)],
        min_separation_m=1.0,
    )
    assert swarm_ok["status"] == "completed" and swarm_ok["min_observed_separation_m"] >= 1.0

    swarm_crash = run_multi_drone_swarm(
        initial_positions_m=[(0.0, 0.0, 2.0), (0.4, 0.0, 2.0)],
        target_positions_m=[(2.0, 0.0, 2.0), (2.0, 0.0, 2.0)],
        min_separation_m=1.0,
    )
    assert swarm_crash["status"] == "failed" and swarm_crash["verdict"] == "FAIL"

    in_path = tmp_path / "swarm_in.json"
    out_path = tmp_path / "swarm_out.json"
    in_path.write_text(json.dumps({"initial_positions_m": [[0, 0, 2], [4, 0, 2]], "target_positions_m": [[1, 0, 3], [5, 0, 3]]}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "swarm-sim", str(in_path), str(out_path)], check=True, cwd=ROOT)
    assert json.loads(out_path.read_text(encoding="utf-8"))["status"] == "completed"
