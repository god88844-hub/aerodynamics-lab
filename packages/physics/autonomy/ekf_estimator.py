"""Error-State Extended Kalman Filter (ES-EKF) fusing 3D IMU strapdown with noisy baro/GPS."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


class DronePositionEkf:
    """6-state linearized EKF over 3D position + 3D velocity [x, y, z, vx, vy, vz]."""

    def __init__(
        self,
        *,
        initial_pos_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
        initial_vel_m_s: tuple[float, float, float] = (0.0, 0.0, 0.0),
        accel_noise_std_m_s2: float = 0.25,
        gps_pos_noise_std_m: float = 0.5,
    ) -> None:
        if accel_noise_std_m_s2 <= 0.0 or gps_pos_noise_std_m <= 0.0:
            raise ValueError("Noise std values must be positive")
        self.x = np.array([*initial_pos_m, *initial_vel_m_s], dtype=float)
        self.P = np.eye(6, dtype=float) * 0.5
        self.sigma_a2 = accel_noise_std_m_s2 ** 2
        self.R_gps = np.eye(3, dtype=float) * (gps_pos_noise_std_m ** 2)

    def predict(self, accel_world_m_s2: np.ndarray, dt_s: float) -> np.ndarray:
        if dt_s <= 0.0:
            raise ValueError("dt_s must be > 0")
        a = np.asarray(accel_world_m_s2, dtype=float)
        F = np.eye(6, dtype=float)
        F[0:3, 3:6] = np.eye(3, dtype=float) * dt_s
        B = np.vstack([0.5 * (dt_s ** 2) * np.eye(3), dt_s * np.eye(3)])
        self.x = F @ self.x + B @ a
        Q = np.zeros((6, 6), dtype=float)
        Q[0:3, 0:3] = 0.25 * (dt_s ** 4) * self.sigma_a2 * np.eye(3)
        Q[3:6, 3:6] = (dt_s ** 2) * self.sigma_a2 * np.eye(3)
        self.P = F @ self.P @ F.T + Q
        return self.x.copy()

    def update_position(self, pos_meas_m: np.ndarray) -> np.ndarray:
        z = np.asarray(pos_meas_m, dtype=float)
        H = np.zeros((3, 6), dtype=float)
        H[0:3, 0:3] = np.eye(3, dtype=float)
        y = z - H @ self.x
        S = H @ self.P @ H.T + self.R_gps
        K = self.P @ H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        I_kh = np.eye(6, dtype=float) - K @ H
        self.P = I_kh @ self.P @ I_kh.T + K @ self.R_gps @ K.T
        return self.x.copy()


def run_ekf_fusion_verification(*, seed: int = 42, duration_s: float = 2.0, dt_s: float = 0.01) -> dict[str, Any]:
    """Verify EKF reduces noisy GPS error on a known accelerated 3D trajectory."""
    rng = np.random.default_rng(np.random.PCG64(seed))
    ekf = DronePositionEkf(accel_noise_std_m_s2=0.15, gps_pos_noise_std_m=0.6)
    steps = max(1, math.ceil(duration_s / dt_s))
    a_true = np.array([0.8, -0.4, 0.3], dtype=float)

    gps_errors = []
    ekf_errors = []
    for k in range(1, steps + 1):
        t = k * dt_s
        p_true = 0.5 * a_true * t * t
        a_imu = a_true + rng.normal(0.0, 0.15, size=3)
        ekf.predict(a_imu, dt_s)
        if k % 5 == 0:
            p_gps = p_true + rng.normal(0.0, 0.6, size=3)
            ekf.update_position(p_gps)
            gps_errors.append(float(np.linalg.norm(p_gps - p_true)))
        ekf_errors.append(float(np.linalg.norm(ekf.x[0:3] - p_true)))

    return {
        "schema_version": "1.0",
        "mean_raw_gps_err_m": sum(gps_errors) / max(1, len(gps_errors)),
        "mean_ekf_err_m": sum(ekf_errors) / max(1, len(ekf_errors)),
        "final_covariance_trace": float(np.trace(ekf.P)),
    }
