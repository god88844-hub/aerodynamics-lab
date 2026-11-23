"""Control mixer: desired wrench [total thrust, tx, ty, tz] -> per-rotor
thrusts, using the plant's geometry matrix (same equations as hover_trim).

When a requested wrench needs an out-of-range rotor thrust, solve the same
least-squares objective over all rotors with nonnegative thrust and any
configured per-rotor ceiling. Report the remaining collective and torque errors.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import lsq_linear

from physics.dynamics.quadrotor import MultirotorPlant

ALLOCATION_FLAGS = ("clipped_negative", "saturated_max", "collective_residual", "torque_residual")
BOUND_TOLERANCE_N = 1e-9
RESIDUAL_TOLERANCE = 1e-3


class Mixer:
    def __init__(
        self,
        plant: MultirotorPlant,
        max_thrust_per_rotor_n: float | None = None,
    ) -> None:
        self.plant = plant
        if max_thrust_per_rotor_n is not None and (
            not np.isfinite(max_thrust_per_rotor_n) or max_thrust_per_rotor_n < 0
        ):
            raise ValueError("maximum rotor thrust must be finite and nonnegative")
        self.max_thrust_per_rotor_n = max_thrust_per_rotor_n
        n = len(plant.rotors)
        if n == 0:
            raise ValueError("plant has no rotors")
        a = np.zeros((4, n))
        a[0, :] = 1.0
        for j, rotor in enumerate(plant.rotors):
            rp = rotor.position_m
            a[1, j] = rp[1]  # tau_x
            a[2, j] = -rp[0]  # tau_y
            a[3, j] = -rotor.spin_direction * plant.rotor_torque_per_thrust  # tau_z
        self.matrix = a
        # Nominal allocator with explicit branch inhibition, NOT a new
        # fault-tolerant redistribution or recovery controller.
        self.disabled_rotors: tuple[int, ...] = ()
        self.last_requested_wrench: np.ndarray | None = None
        self.last_status: dict[str, bool] = {}

    def mix(
        self, total_thrust: float, torque_body: np.ndarray
    ) -> tuple[np.ndarray, dict]:
        """Return physically bounded rotor thrusts and allocation flags."""
        torque = np.asarray(torque_body, dtype=float)
        if torque.shape != (3,) or not np.isfinite(total_thrust) or not np.all(np.isfinite(torque)):
            raise ValueError("control allocation requires a finite thrust and three finite torques")
        wrench = np.concatenate(([total_thrust], torque))
        limit = self.max_thrust_per_rotor_n if self.max_thrust_per_rotor_n is not None else np.inf
        unconstrained = np.linalg.lstsq(self.matrix, wrench, rcond=None)[0]
        negative = bool(np.any(unconstrained < -BOUND_TOLERANCE_N))
        above_limit = bool(np.any(unconstrained > limit + BOUND_TOLERANCE_N))

        if limit == 0:
            thrusts = np.zeros_like(unconstrained)
        elif negative or above_limit:
            solved = lsq_linear(self.matrix, wrench, bounds=(0.0, limit), method="bvls")
            if not solved.success or not np.all(np.isfinite(solved.x)):
                raise ValueError("bounded control allocation did not converge")
            thrusts = np.clip(solved.x, 0.0, limit)
        else:
            thrusts = np.clip(unconstrained, 0.0, limit)

        self.last_requested_wrench = wrench.copy()
        if self.disabled_rotors:
            thrusts[list(self.disabled_rotors)] = 0.0
            above_limit = True
        residual = self.matrix @ thrusts - wrench
        status = {
            "clipped_negative": negative,
            "saturated_max": above_limit,
            "collective_residual": bool(abs(residual[0]) > RESIDUAL_TOLERANCE),
            "torque_residual": bool(np.linalg.norm(residual[1:]) > RESIDUAL_TOLERANCE),
        }
        self.last_status = status.copy()
        return thrusts, status
