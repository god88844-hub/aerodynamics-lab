"""Slice 0D autonomy software core: ArduPilot/PX4 SITL lock-step bridge, synthetic LiDAR/A*, geofence, and swarm."""

from __future__ import annotations

import heapq
import math
from typing import Any

import numpy as np

from physics.autonomy.ekf_estimator import DronePositionEkf


class SitlLockstepBridge:
    """Deterministic lock-step sensor/actuator handshake compatible with ArduPilot & PX4 frames."""

    def __init__(self, *, firmware_kind: str = "ardupilot", dt_s: float = 0.004, n_actuators: int = 4) -> None:
        if firmware_kind not in ("ardupilot", "px4"):
            raise ValueError(f"Unsupported firmware_kind {firmware_kind!r}; expected 'ardupilot' or 'px4'")
        if dt_s <= 0.0 or n_actuators < 1:
            raise ValueError("dt_s must be > 0 and n_actuators >= 1")
        self.firmware_kind = firmware_kind
        self.dt_s = dt_s
        self.n_actuators = n_actuators
        self.step_index = 0

    def step_packet(
        self,
        *,
        pos_ned_m: tuple[float, float, float],
        vel_ned_m_s: tuple[float, float, float],
        bus_voltage_v: float,
        pwm_commands: list[float],
        link_lost: bool = False,
        latency_ms: float = 4.0,
    ) -> dict[str, Any]:
        if len(pwm_commands) != self.n_actuators:
            raise ValueError(f"Expected {self.n_actuators} actuator commands, got {len(pwm_commands)}")
        if any(not math.isfinite(p) or not 0.0 <= p <= 1.0 for p in pwm_commands):
            raise ValueError("SITL normalized PWM commands must stay in [0.0, 1.0]")
        if not math.isfinite(latency_ms) or latency_ms < 0.0 or latency_ms > 250.0:
            raise ValueError(f"SITL telemetry latency {latency_ms} ms exceeds safe lockstep bound (<= 250 ms)")
        t_usec = int(round(self.step_index * self.dt_s * 1_000_000))
        self.step_index += 1
        mode = "FAILSAFE_LINK_LOSS" if link_lost else "LOCKSTEP_ACTIVE"
        actuators = [0.0] * self.n_actuators if link_lost else list(pwm_commands)
        return {
            "protocol": f"{self.firmware_kind}_lockstep_1",
            "time_usec": t_usec,
            "mode": mode,
            "link_lost": link_lost,
            "latency_ms": float(latency_ms),
            "sensors": {
                "pos_ned_m": list(pos_ned_m),
                "vel_ned_m_s": list(vel_ned_m_s),
                "battery_v": float(bus_voltage_v),
            },
            "actuators_pwm_norm": actuators,
        }


def generate_synthetic_lidar_scan(
    *,
    sensor_pos_m: tuple[float, float, float],
    obstacles: list[dict[str, Any]],
    n_rays: int = 36,
    max_range_m: float = 20.0,
) -> dict[str, Any]:
    """Ray-cast synthetic 2D horizontal LiDAR ranges against rectangular TestGround obstacles."""
    if n_rays < 4 or max_range_m <= 0.0:
        raise ValueError("n_rays >= 4 and max_range_m > 0 required")
    ox, oy, oz = sensor_pos_m
    ranges = []
    angles_rad = np.linspace(0.0, 2.0 * math.pi, n_rays, endpoint=False)
    for ang in angles_rad:
        dx, dy = math.cos(float(ang)), math.sin(float(ang))
        best = max_range_m
        for obs in obstacles:
            cx, cy, cz = obs["center_m"]
            sx, sy, sz = obs["size_m"]
            if not (cz - 0.5 * sz <= oz <= cz + 0.5 * sz):
                continue
            # Slab intersection in XY
            tmin, tmax = 0.0, max_range_m
            for p0, d, c, half_s in ((ox, dx, cx, 0.5 * sx), (oy, dy, cy, 0.5 * sy)):
                lo, hi = c - half_s, c + half_s
                if abs(d) < 1e-12:
                    if p0 < lo or p0 > hi:
                        tmin = max_range_m + 1.0
                        break
                else:
                    t1, t2 = (lo - p0) / d, (hi - p0) / d
                    if t1 > t2:
                        t1, t2 = t2, t1
                    tmin = max(tmin, t1)
                    tmax = min(tmax, t2)
            if tmin <= tmax and 0.0 <= tmin < best:
                best = tmin
        ranges.append(round(float(best), 4))
    return {
        "schema_version": "1.0",
        "dataset_kind": "synthetic",
        "channel_provenance": "SYNTHETIC",
        "sensor_pos_m": list(sensor_pos_m),
        "ranges_m": ranges,
        "note": "Synthetic raycast sensor output; never substitutes for measured real-hardware validation.",
    }


def plan_obstacle_free_path(
    *,
    start_xy: tuple[int, int],
    goal_xy: tuple[int, int],
    blocked_cells: set[tuple[int, int]],
    geofence_radius_cells: int = 30,
) -> list[tuple[int, int]]:
    """Deterministic A* 2D obstacle-avoiding planner constrained inside cylindrical geofence."""
    if start_xy in blocked_cells or goal_xy in blocked_cells:
        raise ValueError("Start or goal cell is blocked by obstacle")
    if math.hypot(*goal_xy) > geofence_radius_cells:
        raise ValueError("Goal lies outside geofence boundary")

    pq: list[tuple[float, int, tuple[int, int]]] = [(0.0, 0, start_xy)]
    came: dict[tuple[int, int], tuple[int, int] | None] = {start_xy: None}
    cost: dict[tuple[int, int], int] = {start_xy: 0}

    while pq:
        _, g, cur = heapq.heappop(pq)
        if cur == goal_xy:
            path = []
            node: tuple[int, int] | None = cur
            while node is not None:
                path.append(node)
                node = came[node]
            path.reverse()
            return path
        if g > cost[cur]:
            continue
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in blocked_cells or math.hypot(*nxt) > geofence_radius_cells:
                continue
            ng = g + 1
            if ng < cost.get(nxt, 1_000_000):
                cost[nxt] = ng
                came[nxt] = cur
                h = math.hypot(goal_xy[0] - nxt[0], goal_xy[1] - nxt[1])
                heapq.heappush(pq, (ng + h, ng, nxt))

    raise ValueError("No collision-free path within geofence")


def run_multi_drone_swarm(
    *,
    initial_positions_m: list[tuple[float, float, float]],
    target_positions_m: list[tuple[float, float, float]],
    min_separation_m: float = 1.0,
    geofence_radius_m: float = 50.0,
    dt_s: float = 0.05,
    duration_s: float = 2.0,
) -> dict[str, Any]:
    """Run deterministic coordinated N-drone fleet kinematics with separation and geofence guards."""
    n = len(initial_positions_m)
    if n < 2 or n != len(target_positions_m):
        raise ValueError("Swarm requires >= 2 drones with matching target positions")
    pos = np.array(initial_positions_m, dtype=float)
    tgt = np.array(target_positions_m, dtype=float)
    vel = np.zeros_like(pos)
    steps = max(1, math.ceil(duration_s / dt_s))
    min_obs_sep = float("inf")
    verdict = "NO_MODELED_LIMIT_BREACHED"
    abort_reason: str | None = None
    traj_t: list[float] = [0.0]
    traj_pos: list[list[list[float]]] = [pos.tolist()]

    for step_idx in range(steps):
        for i in range(n):
            for j in range(i + 1, n):
                d = float(np.linalg.norm(pos[i] - pos[j]))
                min_obs_sep = min(min_obs_sep, d)
                if d < min_separation_m:
                    verdict = "FAIL"
                    abort_reason = f"Swarm inter-agent separation violation ({d:.3f} < {min_separation_m:.3f} m)"
                    break
            if float(np.linalg.norm(pos[i, :2])) > geofence_radius_m:
                verdict = "FAIL"
                abort_reason = f"Drone {i} breached geofence radius {geofence_radius_m} m"
                break
        if abort_reason:
            break
        acc = 2.5 * (tgt - pos) - 2.0 * vel
        # Repulsive artificial potential near 1.5 * min_separation_m
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                diff = pos[i] - pos[j]
                dist = float(np.linalg.norm(diff))
                if 1e-6 < dist < 1.5 * min_separation_m:
                    acc[i] += (diff / dist) * (3.0 / max(0.1, dist - min_separation_m + 0.1))
        vel += acc * dt_s
        pos += vel * dt_s
        traj_t.append(round((step_idx + 1) * dt_s, 4))
        traj_pos.append(pos.tolist())

    return {
        "schema_version": "1.0",
        "agent_count": n,
        "status": "failed" if abort_reason else "completed",
        "verdict": verdict,
        "abort_reason": abort_reason,
        "min_observed_separation_m": round(min_obs_sep, 4),
        "final_positions_m": pos.tolist(),
        "trajectory_t_s": traj_t,
        "trajectory_positions_m": traj_pos,
        "physical_validation_status": "UNVALIDATED",
    }


def run_sitl_closed_loop_mission(
    *,
    firmware_kind: str = "ardupilot",
    start_xy: tuple[int, int] = (0, 0),
    goal_xy: tuple[int, int] = (6, 4),
    blocked_cells: set[tuple[int, int]] | None = None,
    obstacles_3d: list[dict[str, Any]] | None = None,
    dt_s: float = 0.02,
    seed: int = 42,
) -> dict[str, Any]:
    """Closed-loop SITL lockstep + EKF state estimation + LiDAR obstacle scan + A* waypoint transit."""
    blocked = blocked_cells or {(3, 1), (3, 2), (3, 3)}
    obs_list = obstacles_3d or [{"center_m": [3.0, 2.0, 2.0], "size_m": [1.0, 3.0, 4.0]}]
    path = plan_obstacle_free_path(start_xy=start_xy, goal_xy=goal_xy, blocked_cells=blocked, geofence_radius_cells=25)
    bridge = SitlLockstepBridge(firmware_kind=firmware_kind, dt_s=dt_s, n_actuators=4)
    ekf = DronePositionEkf(initial_pos_m=(float(start_xy[0]), float(start_xy[1]), 2.0), accel_noise_std_m_s2=0.15, gps_pos_noise_std_m=0.35)
    rng = np.random.default_rng(np.random.PCG64(seed))

    packets = []
    min_lidar_clearance_m = float("inf")
    ekf_errs = []
    p_true = np.array([float(start_xy[0]), float(start_xy[1]), 2.0], dtype=float)
    for step_idx, wp in enumerate(path[1:], start=1):
        tgt = np.array([float(wp[0]), float(wp[1]), 2.0], dtype=float)
        # 18 sub-steps per waypoint segment so diagonal corner-cutting stays outside obstacle clearance
        for _ in range(18):
            a_cmd = np.clip(2.0 * (tgt - p_true), -3.0, 3.0)
            p_true = p_true + 0.5 * a_cmd * dt_s * dt_s + 0.18 * (tgt - p_true)
            ekf.predict(a_cmd + rng.normal(0.0, 0.1, size=3), dt_s)
            ekf.update_position(p_true + rng.normal(0.0, 0.25, size=3))
            ekf_errs.append(float(np.linalg.norm(ekf.x[0:3] - p_true)))
        scan = generate_synthetic_lidar_scan(sensor_pos_m=(float(p_true[0]), float(p_true[1]), 2.0), obstacles=obs_list, n_rays=18)
        min_lidar_clearance_m = min(min_lidar_clearance_m, min(scan["ranges_m"]))
        pkt = bridge.step_packet(
            pos_ned_m=(float(ekf.x[0]), float(ekf.x[1]), -float(ekf.x[2])),
            vel_ned_m_s=(float(ekf.x[3]), float(ekf.x[4]), -float(ekf.x[5])),
            bus_voltage_v=24.8,
            pwm_commands=[0.55, 0.55, 0.55, 0.55],
        )
        packets.append(pkt)

    return {
        "schema_version": "1.0",
        "firmware_kind": firmware_kind,
        "waypoint_count": len(path),
        "packet_count": len(packets),
        "mean_ekf_position_error_m": round(sum(ekf_errs) / max(1, len(ekf_errs)), 4),
        "min_lidar_clearance_m": round(min_lidar_clearance_m, 4),
        "verdict": "NO_MODELED_LIMIT_BREACHED" if min_lidar_clearance_m > 0.25 else "FAIL",
        "channel_provenance": "SYNTHETIC",
        "physical_validation_status": "UNVALIDATED",
    }


def localize_fiducial_apriltag_proxy(
    *,
    tag_world_m: tuple[float, float, float],
    camera_pos_m: tuple[float, float, float],
    fov_deg: float = 82.0,
    max_range_m: float = 12.0,
    seed: int = 7,
) -> dict[str, Any]:
    """Synthetic pinhole-camera AprilTag PnP relative-pose & FOV occlusion estimator (SYNTHETIC)."""
    if fov_deg <= 10.0 or fov_deg >= 170.0 or max_range_m <= 0.0:
        raise ValueError("Invalid optical camera FOV or range bounds")
    rel = np.array(tag_world_m, dtype=float) - np.array(camera_pos_m, dtype=float)
    dist = float(np.linalg.norm(rel))
    if dist < 1e-6 or dist > max_range_m:
        return {"detected": False, "reason": "Tag out of optical range", "channel_provenance": "SYNTHETIC"}
    # Camera points downward (-Z) with small tolerance or forward (+X) check via half-FOV cone
    angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, -rel[2] / dist))))
    if angle_deg > 0.5 * fov_deg:
        return {"detected": False, "reason": "Tag outside camera FOV cone", "channel_provenance": "SYNTHETIC"}
    rng = np.random.default_rng(np.random.PCG64(seed))
    noise = rng.normal(0.0, 0.015 * dist, size=3)
    return {
        "schema_version": "1.0",
        "detected": True,
        "estimated_rel_pos_m": [round(float(v), 4) for v in (rel + noise)],
        "range_m": round(dist, 4),
        "off_nadir_deg": round(angle_deg, 2),
        "channel_provenance": "SYNTHETIC",
        "physical_validation_status": "UNVALIDATED",
    }


def evaluate_geofence_and_override(
    *,
    position_m: tuple[float, float, float],
    geofence_radius_m: float = 50.0,
    min_obstacle_clearance_m: float = 1.2,
    avoidance_authority_available: bool = True,
    manual_override_active: bool = False,
) -> dict[str, Any]:
    """Enforce cylindrical geofence, obstacle clearance, avoidance authority, and pilot manual override."""
    radial = math.hypot(position_m[0], position_m[1])
    if manual_override_active:
        decision = "MANUAL_OPERATOR_OVERRIDE"
        verdict = "NO_MODELED_LIMIT_BREACHED"
    elif radial > geofence_radius_m:
        decision = "GEOFENCE_BREACH_RTL"
        verdict = "FAIL"
    elif min_obstacle_clearance_m < 0.5:
        if not avoidance_authority_available:
            decision = "AVOIDANCE_UNAVAILABLE_FAIL"
            verdict = "FAIL"
        else:
            decision = "AVOIDANCE_BRAKE_HOLD"
            verdict = "NO_MODELED_LIMIT_BREACHED"
    else:
        decision = "NOMINAL_AUTONOMOUS"
        verdict = "NO_MODELED_LIMIT_BREACHED"
    return {
        "schema_version": "1.0",
        "decision": decision,
        "verdict": verdict,
        "manual_override_active": manual_override_active,
        "radial_distance_m": round(radial, 4),
        "physical_validation_status": "UNVALIDATED",
    }
