"""Mass-property assembly from parts (parallel axis theorem).

Positions are expressed in the design body frame (design datum at origin).
The assembled inertia tensor is expressed about the assembly centre of mass,
in design-frame axes.

Fail-closed: a non-physical assembly (non-positive inertia, principal moments
violating the triangle inequality) raises ValueError instead of silently
producing an invalid simulation ("component failure = project failure" applies
to the model inputs too).

Verified in tests/physics/test_mass_properties.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class Part:
    """A rigid component with its own CoG located in the design frame."""

    name: str
    mass_kg: float
    position_m: np.ndarray  # (3,) position of the part's own CoG
    inertia_about_own_cog: np.ndarray | None = None  # (3,3), optional

    def __post_init__(self) -> None:
        pos = np.asarray(self.position_m, dtype=float)
        object.__setattr__(self, "position_m", pos)
        if not np.isfinite(self.mass_kg) or self.mass_kg < 0.0:
            raise ValueError(f"part {self.name!r}: mass must be finite and >= 0")
        if pos.shape != (3,) or not np.all(np.isfinite(pos)):
            raise ValueError(f"part {self.name!r}: position must be a finite 3-vector")
        if self.inertia_about_own_cog is not None:
            inertia = np.asarray(self.inertia_about_own_cog, dtype=float)
            if inertia.shape != (3, 3) or not np.all(np.isfinite(inertia)):
                raise ValueError(f"part {self.name!r}: inertia must be a finite 3x3 matrix")
            if not np.allclose(inertia, inertia.T):
                raise ValueError(f"part {self.name!r}: inertia tensor must be symmetric")
            object.__setattr__(self, "inertia_about_own_cog", inertia)


@dataclass(frozen=True)
class MassProperties:
    mass_kg: float
    cog_m: np.ndarray  # (3,)
    inertia_about_cog: np.ndarray  # (3,3) about the assembly CoG, design axes

    @property
    def principal_moments(self) -> np.ndarray:
        """Principal moments of inertia (eigenvalues), ascending."""
        return np.sort(np.linalg.eigvalsh(self.inertia_about_cog))

    @property
    def principal_axes(self) -> np.ndarray:
        """Principal axes (columns), ordered to match ``principal_moments``."""
        eigvals, eigvecs = np.linalg.eigh(self.inertia_about_cog)
        order = np.argsort(eigvals)
        return eigvecs[:, order]


def assemble_mass_properties(parts: Sequence[Part]) -> MassProperties:
    """Assemble total mass, CoG and inertia tensor from parts.

    Inertia of each part is transferred to the assembly CoG via the parallel
    axis theorem: I += I_own + m * (|d|^2 * E - d d^T), d = r_part - r_cog.
    """
    if not parts:
        raise ValueError("assembly requires at least one part")
    total = float(sum(p.mass_kg for p in parts))
    if total <= 0.0:
        raise ValueError("assembly has zero or negative total mass")
    cog = sum(p.mass_kg * p.position_m for p in parts) / total

    inertia = np.zeros((3, 3))
    for p in parts:
        d = p.position_m - cog
        inertia += p.mass_kg * (float(np.dot(d, d)) * np.eye(3) - np.outer(d, d))
        if p.inertia_about_own_cog is not None:
            inertia += p.inertia_about_own_cog

    _validate_inertia(inertia)
    return MassProperties(mass_kg=total, cog_m=cog, inertia_about_cog=inertia)


def _validate_inertia(inertia: np.ndarray) -> None:
    """Fail closed on physically impossible inertia tensors.

    Zero eigenvalues are allowed (idealized flat/point distributions, e.g. a
    dumbbell with a massless rod, have a free rotation axis); strictly
    negative eigenvalues are not. The triangle inequality on principal
    moments must hold, with equality permitted. RigidBody additionally
    requires positive definiteness because it must invert the tensor.
    """
    eigenvalues = np.linalg.eigvalsh(inertia)
    neg_tol = -1e-12 * max(1.0, float(abs(eigenvalues).max()))
    if np.any(eigenvalues < neg_tol):
        raise ValueError(f"non-physical inertia (negative eigenvalue): {eigenvalues}")
    i1, i2, i3 = np.sort(eigenvalues)  # ascending
    if i1 + i2 < i3 - 1e-9 * max(float(i3), 1.0):
        raise ValueError(
            "non-physical inertia: principal moments violate the triangle "
            f"inequality (I1+I2={i1 + i2:.6g} < I3={i3:.6g})"
        )


def require_material_density_and_source(
    density_kg_m3: float | None,
    density_source: str | None,
) -> tuple[float, str]:
    """Fail closed when density or its provenance citation is missing for mass-property calculations."""
    if density_kg_m3 is None or isinstance(density_kg_m3, bool):
        raise ValueError("mass-property computation refused: material density_kg_m3 is missing")
    value = float(density_kg_m3)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError("mass-property computation refused: material density_kg_m3 must be finite and > 0")
    if not isinstance(density_source, str) or not density_source.strip():
        raise ValueError("mass-property computation refused: material density source is missing")
    return value, density_source.strip()


def part_from_material_volume(
    name: str,
    volume_m3: float,
    position_m: Sequence[float] | np.ndarray,
    *,
    density_kg_m3: float | None = None,
    density_source: str | None = None,
    unit_density_inertia_m5: np.ndarray | None = None,
) -> Part:
    """Build a Part from volume and sourced density, refusing missing density/source."""
    if volume_m3 is None or isinstance(volume_m3, bool) or not np.isfinite(volume_m3) or float(volume_m3) <= 0.0:
        raise ValueError(f"part {name!r}: volume_m3 must be finite and > 0")
    density, _ = require_material_density_and_source(density_kg_m3, density_source)
    mass_kg = float(volume_m3) * density
    inertia = (
        np.asarray(unit_density_inertia_m5, dtype=float) * density
        if unit_density_inertia_m5 is not None
        else None
    )
    return Part(name=name, mass_kg=mass_kg, position_m=np.asarray(position_m, dtype=float), inertia_about_own_cog=inertia)


def iter_parts_schemas(parts: Iterable[Part]) -> Iterable[Part]:  # pragma: no cover
    """Placeholder for future schema-level part iteration helpers."""
    yield from parts
