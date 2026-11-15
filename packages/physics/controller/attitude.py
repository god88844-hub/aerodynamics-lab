"""Cascaded quadcopter controller: position -> attitude -> rate -> mixer.

Architecture (classic cascade, all loops at the same fixed control period):
  - position hold (x, y): P-PD on horizontal error -> desired tilt (small-angle,
    yaw-compensated), capped.
  - altitude: PID on height error -> total thrust command (tilt-compensated
    via 1/cos(tilt)).
  - attitude: P on roll/pitch angle errors -> desired body rates (saturated).
  - rate: PID on body-rate errors -> body torques.
  - yaw: P on yaw error -> desired yaw rate -> rate PID.
  - mixer: [thrust, torques] -> per-rotor thrusts.

Gains are derived from the assembled plant (mass/inertia) with sane defaults
so both the 2 kg synthetic quad and the 3.7 kg MN3508 quad stabilize without
hand tuning; explicit override is possible via ControlGains.

Model status (M3): perfect state knowledge, ideal actuators, no sensor
noise/delay (M4). Small-angle assumptions in the position/altitude cross-feed
are documented and valid for the near-hover regime this milestone targets.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from physics.controller.mixer import Mixer
from physics.controller.pid import PID
from physics.dynamics.quadrotor import MultirotorPlant
from physics.dynamics.quaternion import rotation_matrix
from physics.dynamics.rigid_body import unpack_state


@dataclass
class ControlTargets:
    """Commanded state. `position_xy=None` disables position hold (pure
    attitude command mode); `altitude_m` is always active."""

    altitude_m: float
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    position_xy: tuple[float, float] | None = None


@dataclass
class ControlGains:
    # rate loops (torque per rad/s, rad/s^2-ish)
    kp_rate_roll: float = 1.0
    kp_rate_pitch: float = 1.0
    kp_rate_yaw: float = 2.0
    ki_rate: float = 0.5
    # angle loop (desired rate per rad)
    kp_angle: float = 6.0
    max_rate_rad_s: float = 2.0
    # yaw
    kp_yaw_angle: float = 4.0
    # altitude (accel per m, accel per m/s, accel per (m*s)); near-critical
    # damping (zeta ~ 1.0). Integral is OFF by default: with ideal actuators
    # there is no thrust bias to integrate, and any integral accumulated
    # during a climb cannot unwind quickly at the wrong equilibrium. When a
    # bias exists (sourced powertrain + battery sag, M4), enable it with the
    # constructor's clamp (kept at +-1.5 m/s^2 = thrust-bias authority only).
    kp_alt: float = 1.5
    kd_alt: float = 2.45
    ki_alt: float = 0.0
    # position hold (accel per m, accel per m/s)
    kp_pos: float = 0.5
    kd_pos: float = 1.41
    max_tilt_rad: float = 0.26  # ~15 deg

    @classmethod
    def for_plant(cls, plant: MultirotorPlant, rate_time_constant: float = 0.05) -> "ControlGains":
        """Derive rate-loop gains from the assembled inertia (first-order
        closed loop with the given time constant); other loops keep defaults."""
        inertia = plant.body.inertia_about_cog
        ixx, iyy, izz = float(inertia[0, 0]), float(inertia[1, 1]), float(inertia[2, 2])
        return cls(
            kp_rate_roll=ixx / rate_time_constant,
            kp_rate_pitch=iyy / rate_time_constant,
            kp_rate_yaw=izz / (rate_time_constant * 1.2),
        )


class QuadcopterController:
    def __init__(
        self,
        plant: MultirotorPlant,
        gains: ControlGains | None = None,
        mixer: Mixer | None = None,
    ) -> None:
        self.plant = plant
        self.gains = gains or ControlGains.for_plant(plant)
        self.mixer = mixer or Mixer(plant)
        g = self.gains
        torque_limit = 10.0  # generous torque clamp (N·m) for rate PIDs
        self.rate_roll = PID(g.kp_rate_roll, g.ki_rate, 0.0, (-torque_limit, torque_limit))
        self.rate_pitch = PID(g.kp_rate_pitch, g.ki_rate, 0.0, (-torque_limit, torque_limit))
        self.rate_yaw = PID(g.kp_rate_yaw, g.ki_rate * 0.5, 0.0, (-torque_limit, torque_limit))
        self.altitude = PID(
            g.kp_alt, g.ki_alt, g.kd_alt,
            (-plant.body.mass_kg * 9.0, plant.body.mass_kg * 9.0),  # accel command limits
            (-1.5, 1.5),  # integral = thrust-bias compensation only (m/s²)
        )
        self._last_accel_cmd = 0.0

    def reset(self) -> None:
        for pid in (self.rate_roll, self.rate_pitch, self.rate_yaw, self.altitude):
            pid.reset()
        self._last_accel_cmd = 0.0

    def step(self, state: np.ndarray, targets: ControlTargets, dt: float) -> np.ndarray:
        """One control period: returns per-rotor thrusts (N)."""
        r, v, q, w = unpack_state(state)
        mass = self.plant.body.mass_kg
        R = rotation_matrix(q)
        roll, pitch, yaw = self._euler_zyx(R)

        # --- position hold (yaw-compensated horizontal error -> tilt) -------
        tilt_x = 0.0  # desired pitch (rad): +x accel
        tilt_y = 0.0  # desired roll (rad): -y accel (rotation about +x tips -y)
        if targets.position_xy is not None:
            cy, sy = np.cos(yaw), np.sin(yaw)
            # world -> yaw-aligned body horizontal error
            ex = targets.position_xy[0] - r[0]
            ey = targets.position_xy[1] - r[1]
            ex_b = cy * ex + sy * ey
            ey_b = -sy * ex + cy * ey
            vx_b = cy * v[0] + sy * v[1]
            vy_b = -sy * v[0] + cy * v[1]
            ax = self.gains.kp_pos * ex_b - self.gains.kd_pos * vx_b
            ay = self.gains.kp_pos * ey_b - self.gains.kd_pos * vy_b
            # small-angle: tilt ≈ atan(a / g), capped
            tilt_x = float(np.clip(np.arctan2(ax, 9.81), -self.gains.max_tilt_rad, self.gains.max_tilt_rad))
            tilt_y = float(np.clip(np.arctan2(-ay, 9.81), -self.gains.max_tilt_rad, self.gains.max_tilt_rad))

        # --- attitude: desired rates from angle errors ----------------------
        roll_des = targets.roll_deg * np.pi / 180.0 + tilt_y
        pitch_des = targets.pitch_deg * np.pi / 180.0 + tilt_x
        roll_des = float(np.clip(roll_des, -self.gains.max_tilt_rad, self.gains.max_tilt_rad))
        pitch_des = float(np.clip(pitch_des, -self.gains.max_tilt_rad, self.gains.max_tilt_rad))
        rate_x_des = float(np.clip(self.gains.kp_angle * (roll_des - roll), -self.gains.max_rate_rad_s, self.gains.max_rate_rad_s))
        rate_y_des = float(np.clip(self.gains.kp_angle * (pitch_des - pitch), -self.gains.max_rate_rad_s, self.gains.max_rate_rad_s))
        yaw_des = targets.yaw_deg * np.pi / 180.0
        rate_z_des = float(np.clip(self.gains.kp_yaw_angle * (yaw_des - yaw), -self.gains.max_rate_rad_s, self.gains.max_rate_rad_s))

        # --- rate loops -> torques ------------------------------------------
        tx = self.rate_roll.step(rate_x_des - w[0], w[0], dt)
        ty = self.rate_pitch.step(rate_y_des - w[1], w[1], dt)
        tz = self.rate_yaw.step(rate_z_des - w[2], w[2], dt)

        # --- altitude: thrust with tilt compensation ------------------------
        cos_tilt = max(np.cos(roll) * np.cos(pitch), 0.5)  # guards near-90° tilt
        accel_cmd = self.altitude.step(targets.altitude_m - r[2], r[2], dt)
        self._last_accel_cmd = accel_cmd
        total_thrust = mass * (9.80665 + accel_cmd) / cos_tilt

        thrusts, _mix_status = self.mixer.mix(total_thrust, np.array([tx, ty, tz]))
        return thrusts

    @staticmethod
    def _euler_zyx(R: np.ndarray) -> tuple[float, float, float]:
        """(roll, pitch, yaw) from a body->world rotation matrix (ZYX convention)."""
        roll = float(np.arctan2(R[2, 1], R[2, 2]))
        pitch = float(np.arcsin(max(-1.0, min(1.0, -R[2, 0]))))
        yaw = float(np.arctan2(R[1, 0], R[0, 0]))
        return roll, pitch, yaw
