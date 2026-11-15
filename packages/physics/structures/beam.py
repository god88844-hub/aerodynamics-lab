"""Frame arm structural checks (cantilever bending of circular tubes).

MODEL STATUS: static bending at the arm root, conservative:
  M_root = F_motor * arm_length      (worst-case arm carries the full motor thrust)
  sigma   = M * c / I                (c = OD/2, I = tube second moment of area)

NOT modeled (flagged in results): torsion from the motor reaction torque,
vibration/fatigue, stress concentrations at clamps, buckling of thin walls,
dynamic amplification during landings. Margin results carry the material
uncertainty; the failure threshold is the material yield with no additional
safety factor applied (margin >= 1 passes, margin < 1 fails, margin < 1.5
warns — policy declared here so reports can state it).

Verified against hand calculations in tests/physics/test_structures.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from physics.structures.materials import MaterialProps


def tube_second_moment(od_m: float, id_m: float) -> float:
    """I = pi/64 (OD^4 - ID^4) for a circular tube."""
    if not (0.0 < id_m < od_m):
        raise ValueError("tube dimensions must satisfy 0 < ID < OD")
    return math.pi / 64.0 * (od_m**4 - id_m**4)


def bending_stress_pa(force_n: float, length_m: float, od_m: float, id_m: float) -> float:
    """Root bending stress (Pa) for a cantilever tube under a tip load."""
    if force_n < 0.0 or length_m <= 0.0:
        raise ValueError("force must be >= 0 and length > 0")
    inertia = tube_second_moment(od_m, id_m)
    moment = force_n * length_m
    return moment * (od_m / 2.0) / inertia


@dataclass(frozen=True)
class StructureCheck:
    ok: bool
    stress_pa: float
    yield_pa: float
    margin: float  # yield / stress (>1 passes)
    warn: bool     # margin < 1.5
    message: str


def check_arm(
    motor_force_n: float,
    arm_length_m: float,
    tube_od_m: float,
    tube_id_m: float,
    material: MaterialProps,
) -> StructureCheck:
    stress = bending_stress_pa(motor_force_n, arm_length_m, tube_od_m, tube_id_m)
    margin = material.yield_strength_pa / stress if stress > 0 else float("inf")
    ok = margin >= 1.0
    warn = margin < 1.5
    msg = (
        f"arm root bending {stress / 1e6:.1f} MPa vs yield "
        f"{material.yield_strength_pa / 1e6:.0f} MPa ({material.name}): "
        f"margin {margin:.2f}"
    )
    return StructureCheck(ok=ok, stress_pa=stress, yield_pa=material.yield_strength_pa,
                          margin=margin, warn=warn, message=msg)
