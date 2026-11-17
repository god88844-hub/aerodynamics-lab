"""Multi-rotor plant: per-rotor thrust commands -> net 6-DOF derivatives.

M1 model fidelity (documented, per docs/validation_strategy.md):
- Thrust from each rotor acts along body +z at a fixed position relative to
  the assembly CoG (no elastic deflection, no propeller asymmetry).
- Rotor reaction torque about body z: ``-spin_direction * k * thrust``
  with k = torque per unit thrust (N·m per N). M1 default k = 0; sourced
  per-component values arrive with the propulsion database (M2).
- Airframe drag: first-order equivalent-area model (physics.aerodynamics.drag).

NOT modeled yet (results outside these conditions are outside the validated
envelope and must be flagged in reports): induced velocity / advance ratio,
ground effect, rotor-rotor interference, propeller gyroscopic moments, motor
dynamics and lag, control latency.

Verified in tests/physics/test_hover.py (trim = weight per rotor, stationary
hover, CoG-offset trim) and tests/physics/test_rigid_body.py (free fall with
zero thrust).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from physics.aerodynamics.drag import AirframeDrag
from physics.constants import STANDARD_GRAVITY
from physics.dynamics.quaternion import conjugate, rotate
from physics.dynamics.rigid_body import RigidBody, unpack_state


@dataclass(frozen=True)
class Rotor:
    """A rotor unit at a fixed position relative to the assembly CoG."""

    position_m: np.ndarray  # (3,) CoG-relative, body frame
    spin_direction: int = 1  # +1 or -1 (prop angular momentum sign)

    def __post_init__(self) -> None:
        pos = np.asarray(self.position_m, dtype=float)
        object.__setattr__(self, "position_m", pos)
        if pos.shape != (3,) or not np.all(np.isfinite(pos)):
            raise ValueError("rotor position must be a finite 3-vector")
        if self.spin_direction not in (1, -1):
            raise ValueError("spin_direction must be +1 or -1")


@dataclass
class MultirotorPlant:
    """Rigid body + rotor layout + aerodynamic extras -> 6-DOF derivatives."""

    body: RigidBody
    rotors: list[Rotor] = field(default_factory=list)
    drag: AirframeDrag | None = None
    rotor_torque_per_thrust: float = 0.0  # N·m per N, uniform M1 approximation
    wind_world: np.ndarray | None = None  # optional uniform wind; never rotor inflow

    def __post_init__(self) -> None:
        if self.wind_world is not None:
            wind = np.asarray(self.wind_world, dtype=float)
            if wind.shape != (3,) or not np.all(np.isfinite(wind)):
                raise ValueError("wind_world must be a finite 3-vector in world coordinates")
            self.wind_world = wind
        if not np.isfinite(self.rotor_torque_per_thrust) or self.rotor_torque_per_thrust < 0:
            raise ValueError("rotor torque coefficient must be finite and nonnegative")

    def net_force_torque(
        self, state: np.ndarray, thrusts: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Applied (non-gravitational) resultant force/torque in the body frame."""
        thrusts = np.asarray(thrusts, dtype=float)
        if thrusts.shape != (len(self.rotors),):
            raise ValueError(f"expected {len(self.rotors)} thrust values, got {thrusts.shape}")
        if not np.all(np.isfinite(thrusts)):
            raise ValueError("multirotor thrust must contain finite values")
        if np.any(thrusts < 0.0):
            raise ValueError("multirotor thrust must be >= 0 (props cannot reverse)")
        _, v, q, _ = unpack_state(state)

        e3 = np.array([0.0, 0.0, 1.0])
        f_body = np.zeros(3)
        t_body = np.zeros(3)
        for rotor, t in zip(self.rotors, thrusts):
            f_i = t * e3
            f_body += f_i
            t_body += np.cross(rotor.position_m, f_i)
            t_body += -rotor.spin_direction * self.rotor_torque_per_thrust * t * e3
        if self.drag is not None:
            f_body += rotate(conjugate(q), self.drag.force_world(v, wind_world=self.wind_world))
        return f_body, t_body

    def derivs(
        self, state: np.ndarray, thrusts: np.ndarray, gravity: bool = True
    ) -> np.ndarray:
        """Full 13-state derivative for the given per-rotor thrusts."""
        f_body, t_body = self.net_force_torque(state, thrusts)
        return self.body.derivs(state, f_body, t_body, gravity=gravity)

    def hover_trim(self, gravity: float = STANDARD_GRAVITY) -> np.ndarray:
        """Per-rotor thrusts for static hover equilibrium (ΣF=0, Στ=0).

        Linear least-squares in the thrust vector; exact for a 4-rotor layout
        with the CoG at the rotor centroid. Raises ValueError when the layout
        cannot be trimmed (fail-closed, no silent compensation).
        """
        n = len(self.rotors)
        if n == 0:
            raise ValueError("plant has no rotors")
        # The τ_z equation only constrains the solution when reaction torque is
        # modeled (k > 0); with k = 0 it is trivially satisfied.
        rows = [np.ones(n)]
        targets = [self.body.mass_kg * gravity]
        tx = np.zeros(n)
        ty = np.zeros(n)
        for j, rotor in enumerate(self.rotors):
            rp = rotor.position_m  # CoG-relative
            tx[j] = rp[1]  # τ_x = Σ t_i * r_y
            ty[j] = -rp[0]  # τ_y = Σ -t_i * r_x
        rows += [tx, ty]
        targets += [0.0, 0.0]
        if self.rotor_torque_per_thrust > 0.0:
            rows.append(
                np.array(
                    [-rotor.spin_direction * self.rotor_torque_per_thrust
                     for rotor in self.rotors]
                )
            )
            targets.append(0.0)
        a = np.vstack(rows)
        b = np.array(targets)

        thrusts, _, rank, _ = np.linalg.lstsq(a, b, rcond=None)
        residual = float(np.linalg.norm(a @ thrusts - b))
        if rank < len(rows) or residual > 1e-8:
            raise ValueError(
                "rotor layout cannot achieve hover trim (ΣF=0, Στ=0): "
                f"rank={rank}, residual={residual:.3g}"
            )
        if np.any(thrusts < 0.0):
            raise ValueError("hover trim requires negative thrust — layout infeasible")
        return thrusts
