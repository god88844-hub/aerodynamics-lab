"""P0D-012: ArduPilot SITL lockstep bridge, single authoritative clock, latency guard, and link-loss failsafe."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from physics.autonomy.sitl_and_swarms import SitlLockstepBridge, run_sitl_closed_loop_mission

ROOT = Path(__file__).resolve().parents[2]


def test_p0d_012_ardupilot_sitl_lockstep_link_loss_and_cli(tmp_path):
    bridge = SitlLockstepBridge(firmware_kind="ardupilot", dt_s=0.004, n_actuators=4)
    pkt1 = bridge.step_packet(pos_ned_m=(0.0, 0.0, -2.0), vel_ned_m_s=(0.0, 0.0, 0.0), bus_voltage_v=24.5, pwm_commands=[0.5, 0.5, 0.5, 0.5])
    assert pkt1["mode"] == "LOCKSTEP_ACTIVE"
    assert pkt1["time_usec"] == 0

    lost = bridge.step_packet(pos_ned_m=(0.0, 0.0, -2.0), vel_ned_m_s=(0.0, 0.0, 0.0), bus_voltage_v=24.5, pwm_commands=[0.6, 0.6, 0.6, 0.6], link_lost=True)
    assert lost["mode"] == "FAILSAFE_LINK_LOSS"
    assert lost["actuators_pwm_norm"] == [0.0, 0.0, 0.0, 0.0]

    with pytest.raises(ValueError, match="latency"):
        bridge.step_packet(pos_ned_m=(0.0, 0.0, -2.0), vel_ned_m_s=(0.0, 0.0, 0.0), bus_voltage_v=24.5, pwm_commands=[0.5, 0.5, 0.5, 0.5], latency_ms=400.0)

    res = run_sitl_closed_loop_mission(firmware_kind="ardupilot")
    assert res["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    in_p = tmp_path / "sitl_in.json"
    out_p = tmp_path / "sitl_out.json"
    in_p.write_text(json.dumps({"firmware_kind": "ardupilot", "start_xy": [0, 0], "goal_xy": [6, 4]}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "sitl-mission", str(in_p), str(out_p)], check=True, cwd=ROOT)
    assert json.loads(out_p.read_text(encoding="utf-8"))["packet_count"] == res["packet_count"]
