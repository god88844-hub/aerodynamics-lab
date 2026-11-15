"""Control mixer: desired wrench [total thrust, tx, ty, tz] -> per-rotor
thrusts, using the plant's geometry matrix (same equations as hover_trim).

Saturation handling: negative demands are clipped to zero and the reduced
system re-solved iteratively (standard approach); the mixer reports whether
any rotor saturated or any demand was unachievable, so reports can flag it
instead of silently distorting the wrench.
"""

from __future__ import annotations

import numpy as np

from physics.dynamics.quadrotor import MultirotorPlant

MAX_CLIP_ITERATIONS = 4


class Mixer:
    def __init__(
        self,
        plant: MultirotorPlant,
        max_thrust_per_rotor_n: float | None = None,
    ) -> None:
        self.plant = plant
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

    def mix(
        self, total_thrust: float, torque_body: np.ndarray
    ) -> tuple[np.ndarray, dict]:
        """Solve per-rotor thrusts; returns (thrusts, status).

        status flags: 'clipped_negative', 'saturated_max', 'torque_residual'.
        """
        n = len(self.plant.rotors)
        wrench = np.array([total_thrust, *np.asarray(torque_body, dtype=float)])
        active = np.ones(n, dtype=bool)
        thrusts = np.zeros(n)
        status: dict[str, bool] = {
            "clipped_negative": False,
            "saturated_max": False,
            "torque_residual": False,
        }

        for _ in range(MAX_CLIP_ITERATIONS):
            sol, _, _, _ = np.linalg.lstsq(self.matrix[:, active], wrench, rcond=None)
            thrusts_active = sol
            if np.any(thrusts_active < -1e-9):
                # Clip the most negative rotor and re-solve on the rest.
                idx_active = np.where(active)[0]
                worst = idx_active[int(np.argmin(thrusts_active))]
                thrusts[worst] = 0.0
                active[worst] = False
                status["clipped_negative"] = True
                continue
            thrusts[active] = thrusts_active
            if self.max_thrust_per_rotor_n is not None:
                over = thrusts > self.max_thrust_per_rotor_n
                if np.any(over):
                    thrusts[over] = self.max_thrust_per_rotor_n
                    status["saturated_max"] = True
                    # Keep solving on the non-saturated set.
                    newly = np.where(over)[0]
                    for j in newly:
                        active[j] = False
                    continue
            break

        # Report unachievable torque when the clipped solution cannot deliver
        # the demanded wrench (yaw authority especially).
        achieved = self.matrix @ thrusts
        if np.linalg.norm(achieved[1:] - wrench[1:]) > 1e-3:
            status["torque_residual"] = True
        return thrusts, status
