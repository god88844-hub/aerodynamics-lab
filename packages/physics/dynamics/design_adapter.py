"""Adapter: aeroforge_schemas design snapshots -> physics simulation objects.

The snapshot is the single source of truth (traceability): the simulator
executes exactly what was saved. This adapter is the only place where the
schema and the physics core meet.
"""

from __future__ import annotations

import numpy as np

from aeroforge_schemas.design import DroneDesign
from geometry.primitives import box_inertia, cylinder_inertia_z
from physics.aerodynamics.drag import AirframeDrag
from physics.dynamics.mass_properties import MassProperties, Part, assemble_mass_properties
from physics.dynamics.quadrotor import MultirotorPlant, Rotor
from physics.dynamics.rigid_body import RigidBody


def build_multirotor(design: DroneDesign) -> tuple[MultirotorPlant, MassProperties]:
    """Build (plant, mass properties) from a validated design snapshot.

    Rotor positions are re-expressed relative to the assembled CoG so that
    torque computations use correct moment arms regardless of the datum.
    """
    parts: list[Part] = []
    for p in design.parts:
        inertia = None
        if p.inertia_about_own_cog_kg_m2 is not None:
            # Independent measured/declared inertia always overrides geometry.
            inertia = np.asarray(p.inertia_about_own_cog_kg_m2, dtype=float)
        elif p.geometry is not None:
            x, y, z = p.geometry.dimensions_m
            if p.geometry.shape == "box":
                inertia = box_inertia(p.mass_kg, x, y, z)
            elif p.geometry.shape == "cylinder":
                inertia = cylinder_inertia_z(p.mass_kg, x / 2.0, z)
            else:  # pragma: no cover - schema validates the shape
                raise ValueError(f"unsupported primitive geometry: {p.geometry.shape}")
        parts.append(
            Part(
                name=p.name,
                mass_kg=p.mass_kg,
                position_m=np.asarray(p.position_m, dtype=float),
                inertia_about_own_cog=inertia,
            )
        )

    mass_props = assemble_mass_properties(parts)
    body = RigidBody(mass_kg=mass_props.mass_kg, inertia_about_cog=mass_props.inertia_about_cog)
    rotors = [
        Rotor(
            position_m=np.asarray(r.position_m, dtype=float) - mass_props.cog_m,
            spin_direction=r.spin_direction,
        )
        for r in design.rotors
    ]
    drag = AirframeDrag(cd_a_m2=design.drag_cd_a_m2) if design.drag_cd_a_m2 is not None else None
    plant = MultirotorPlant(
        body=body,
        rotors=rotors,
        drag=drag,
        rotor_torque_per_thrust=design.rotor_torque_per_thrust_n_m_per_n,
    )
    return plant, mass_props
