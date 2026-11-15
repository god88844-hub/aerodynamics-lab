"""Airframe aerodynamic drag — first-order equivalent-area model.

MODEL STATUS: labeled approximation.
    F_drag(world) = -0.5 * rho * CdA * |v| * v

- CdA (equivalent drag area, m^2) must be provided with a source or an
  explicit uncertainty; there is no universal default and the schema forbids
  silently inventing one.
- Valid only for incompressible flow (Mach << 0.3) and constant density.
- No wind, no shear, no angle-of-attack dependence, no interference drag.

Forward-flight performance predictions using this model are low-confidence
until validated against flight data (M7 benchmark suite).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from physics.constants import SEA_LEVEL_AIR_DENSITY


@dataclass(frozen=True)
class AirframeDrag:
    cd_a_m2: float  # equivalent drag area [m^2]
    rho_kg_m3: float = SEA_LEVEL_AIR_DENSITY

    def __post_init__(self) -> None:
        if not np.isfinite(self.cd_a_m2) or self.cd_a_m2 <= 0.0:
            raise ValueError("cd_a_m2 must be finite and > 0")
        if not np.isfinite(self.rho_kg_m3) or self.rho_kg_m3 <= 0.0:
            raise ValueError("rho_kg_m3 must be finite and > 0")

    def force_world(self, velocity_world: np.ndarray) -> np.ndarray:
        """Drag force in the world frame for the given velocity (no wind)."""
        v = np.asarray(velocity_world, dtype=float)
        speed = float(np.linalg.norm(v))
        if speed == 0.0:
            return np.zeros(3)
        return -0.5 * self.rho_kg_m3 * self.cd_a_m2 * speed * v
