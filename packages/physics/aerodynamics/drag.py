"""Airframe aerodynamic drag — first-order equivalent-area model.

MODEL STATUS: labeled approximation.
    F_drag(world) = -0.5 * rho * CdA * |v| * v

- CdA (equivalent drag area, m^2) must be provided with a source or an
  explicit uncertainty; there is no universal default and the schema forbids
  silently inventing one.
- Valid only for incompressible flow (Mach << 0.3) and constant density.
- Optional explicitly supplied steady uniform world-frame wind; no wind shear, gust\n  statistics, angle-of-attack dependence, rotor inflow or interference drag.

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

    def force_world(
        self, velocity_world: np.ndarray, wind_world: np.ndarray | None = None,
    ) -> np.ndarray:
        """World-frame drag from *air-relative* velocity, not ground speed.

        wind_world is the explicitly supplied ambient air velocity in the
        same world coordinates. No wind is assumed only when omitted, for
        backward compatibility. A constant uniform wind does not describe
        turbulence, rotor inflow, gust shear or installation effects.
        """
        v = np.asarray(velocity_world, dtype=float)
        if v.shape != (3,) or not np.all(np.isfinite(v)):
            raise ValueError("velocity_world must be a finite world-frame 3-vector")
        if wind_world is None:
            air = np.zeros(3, dtype=float)
        else:
            air = np.asarray(wind_world, dtype=float)
            if air.shape != (3,) or not np.all(np.isfinite(air)):
                raise ValueError("wind_world must be a finite world-frame 3-vector")
        relative = v - air
        speed = float(np.linalg.norm(relative))
        if not np.isfinite(speed):
            raise ValueError("relative-air velocity magnitude overflowed")
        if speed == 0.0:
            return np.zeros(3, dtype=float)
        drag = -0.5 * self.rho_kg_m3 * self.cd_a_m2 * speed * relative
        if not np.all(np.isfinite(drag)):
            raise ValueError("airframe drag computation overflowed")
        return drag
