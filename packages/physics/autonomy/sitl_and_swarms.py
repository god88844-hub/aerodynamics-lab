"""Slice 0D autonomy software core: ArduPilot/PX4 SITL lock-step bridge, synthetic LiDAR/A*, geofence, and swarm."""

from __future__ import annotations

import heapq
import math
from typing import Any

import numpy as np


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
    ) -> dict[str, Any]:
        if len(pwm_commands) != self.n_actuators:
            raise ValueError(f"Expected {self.n_actuators} actuator commands, got {len(pwm_commands)}")
        if any(not math.isfinite(p) or not 0.0 <= p <= 1.0 for p in pwm_commands):
            raise ValueError("SITL normalized PWM commands must stay in [0.0, 1.0]")
        t_usec = int(round(self.step_index * self.dt_s * 1_000_000))
        self.step_index += 1
        return {
            "protocol": f"{self.firmware_kind}_lockstep_1",
            "time_usec": t_usec,
            "sensors": {
                "pos_ned_m": list(pos_ned_m),
                "vel_ned_m_s": list(vel_ned_m_s),
                "battery_v": float(bus_voltage_v),
            },
            "actuators_pwm_norm": list(pwm_commands),
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

    for _ in range(steps):
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

    return {
        "schema_version": "1.0",
        "agent_count": n,
        "status": "failed" if abort_reason else "completed",
        "verdict": verdict,
        "abort_reason": abort_reason,
        "min_observed_separation_m": round(min_obs_sep, 4),
        "final_positions_m": pos.tolist(),
        "physical_validation_status": "UNVALIDATED",
    }
