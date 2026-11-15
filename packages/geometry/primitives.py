"""Inertia tensors of uniform-density primitives.

Standard rigid-body formulas (Hibbeler, *Engineering Mechanics: Dynamics*,
Appendix B — mass moments of inertia of common solid shapes). Used to build
component inertias from parametric geometry; measured part inertias always
take precedence when available.
"""

from __future__ import annotations

import numpy as np


def box_inertia(mass_kg: float, sx: float, sy: float, sz: float) -> np.ndarray:
    """Solid box inertia about CoG-aligned axes (diagonal 3x3, kg·m²).

    I_xx = m/12 (sy² + sz²), I_yy = m/12 (sx² + sz²), I_zz = m/12 (sx² + sy²).
    """
    for s in (sx, sy, sz):
        if s <= 0.0 or not np.isfinite(s):
            raise ValueError("box dimensions must be finite and > 0")
    if mass_kg < 0.0 or not np.isfinite(mass_kg):
        raise ValueError("mass must be finite and >= 0")
    return np.diag(
        [
            mass_kg / 12.0 * (sy * sy + sz * sz),
            mass_kg / 12.0 * (sx * sx + sz * sz),
            mass_kg / 12.0 * (sx * sx + sy * sy),
        ]
    )


def cylinder_inertia_z(mass_kg: float, radius_m: float, height_m: float) -> np.ndarray:
    """Solid cylinder inertia about CoG axes, cylinder axis = z (diagonal 3x3)."""
    if radius_m <= 0.0 or height_m <= 0.0 or not np.isfinite(mass_kg) or mass_kg < 0.0:
        raise ValueError("cylinder dimensions and mass must be finite and > 0")
    i_xx = mass_kg / 12.0 * (3.0 * radius_m**2 + height_m**2)
    i_zz = 0.5 * mass_kg * radius_m**2
    return np.diag([i_xx, i_xx, i_zz])


def point_mass_inertia(mass_kg: float) -> np.ndarray:
    """Zero inertia about a point mass's own CoG (translation handled by the
    parallel axis theorem in the assembly)."""
    if mass_kg < 0.0 or not np.isfinite(mass_kg):
        raise ValueError("mass must be finite and >= 0")
    return np.zeros((3, 3))
