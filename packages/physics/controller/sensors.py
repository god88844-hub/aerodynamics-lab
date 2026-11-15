"""Sensor models: additive noise + latency on the state fed to the controller.

MODEL STATUS (M4): first-order — zero-order-hold latency buffer, Gaussian
noise per channel, quaternion noise as a small random rotation. Noise is
seeded (deterministic, traceable). NOT modeled: bias/drift, dropouts,
quantization, vibration-induced aliasing.

The controller sees the *measured* state; the plant always integrates the
true state.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from physics.dynamics.quaternion import multiply, normalize, from_axis_angle


@dataclass
class SensorConfig:
    seed: int = 12345
    sigma_position_m: float = 0.0
    sigma_velocity_m_s: float = 0.0
    sigma_attitude_deg: float = 0.0
    sigma_rate_deg_s: float = 0.0
    latency_s: float = 0.0
    control_dt_s: float = 0.004
    # Constant biases (M9 failure-mode testing): the controller never sees
    # them compensated — a real gyro/accelerometer bias behaves this way.
    bias_position_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bias_velocity_m_s: tuple[float, float, float] = (0.0, 0.0, 0.0)
    bias_rate_rad_s: tuple[float, float, float] = (0.0, 0.0, 0.0)


class SensorModel:
    def __init__(self, config: SensorConfig) -> None:
        self.cfg = config
        self._rng = np.random.default_rng(config.seed)
        self._buffer: deque = deque()

    def _noisy(self, state: np.ndarray) -> np.ndarray:
        cfg = self.cfg
        s = state.copy()
        if cfg.bias_position_m:
            s[0:3] = s[0:3] + np.asarray(cfg.bias_position_m)
        if cfg.bias_velocity_m_s:
            s[3:6] = s[3:6] + np.asarray(cfg.bias_velocity_m_s)
        if cfg.bias_rate_rad_s:
            s[10:13] = s[10:13] + np.asarray(cfg.bias_rate_rad_s)
        if cfg.sigma_position_m > 0:
            s[0:3] = s[0:3] + self._rng.normal(0.0, cfg.sigma_position_m, 3)
        if cfg.sigma_velocity_m_s > 0:
            s[3:6] = s[3:6] + self._rng.normal(0.0, cfg.sigma_velocity_m_s, 3)
        if cfg.sigma_attitude_deg > 0:
            dtheta = np.radians(self._rng.normal(0.0, cfg.sigma_attitude_deg, 3))
            dq = from_axis_angle(dtheta, float(np.linalg.norm(dtheta)))
            s[6:10] = normalize(multiply(s[6:10], dq))
        if cfg.sigma_rate_deg_s > 0:
            s[10:13] = s[10:13] + np.radians(self._rng.normal(0.0, cfg.sigma_rate_deg_s, 3))
        return s

    def measure(self, state: np.ndarray, t: float) -> np.ndarray:
        """Return the controller's view of the state at time t."""
        cfg = self.cfg
        has_bias = any(cfg.bias_position_m) or any(cfg.bias_velocity_m_s) \
            or any(cfg.bias_rate_rad_s)
        if (cfg.latency_s <= 0.0 and not has_bias
                and cfg.sigma_position_m == 0 and cfg.sigma_velocity_m_s == 0
                and cfg.sigma_attitude_deg == 0 and cfg.sigma_rate_deg_s == 0):
            return state
        # Zero-order-hold latency: measurements arrive delayed.
        self._buffer.append((t, np.asarray(state, dtype=float).copy()))
        cutoff = t - cfg.latency_s
        measured = state
        for tt, st in reversed(self._buffer):
            if tt <= cutoff:
                measured = st
                break
        while len(self._buffer) > 2 and self._buffer[0][0] < cutoff - 0.5:
            self._buffer.popleft()
        return self._noisy(measured)
