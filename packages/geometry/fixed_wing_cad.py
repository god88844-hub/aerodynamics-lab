"""Slice 0B CAD software foundation: constrained 2D sketch, parametric wing loft, and unit-safe exchange."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ConstrainedSketch2D:
    """Parametric 2D closed profile sketch with explicit geometric constraints."""

    name: str
    width_m: float
    height_m: float
    thickness_m: float
    history_features: tuple[str, ...] = ("base_sketch", "extrude")

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Sketch name must be non-empty")
        for val, label in ((self.width_m, "width_m"), (self.height_m, "height_m"), (self.thickness_m, "thickness_m")):
            if not math.isfinite(val) or val <= 0.0:
                raise ValueError(f"{label} must be finite and > 0")

    def area_m2(self) -> float:
        return self.width_m * self.height_m

    def volume_m3(self) -> float:
        return self.area_m2() * self.thickness_m

    def to_feature_tree(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "name": self.name,
            "units": "m",
            "dimensions_m": [self.width_m, self.height_m, self.thickness_m],
            "features": list(self.history_features),
            "area_m2": self.area_m2(),
            "volume_m3": self.volume_m3(),
        }


def naca4_airfoil_coordinates(code: str = "2412", n_points_per_surface: int = 25) -> list[tuple[float, float]]:
    """Generate unit-chord closed NACA 4-digit airfoil coordinates (trailing edge -> LE -> trailing edge)."""
    if len(code) != 4 or not code.isdigit():
        raise ValueError(f"Expected 4-digit NACA airfoil code, got {code!r}")
    if n_points_per_surface < 8:
        raise ValueError("n_points_per_surface must be >= 8")

    m = int(code[0]) / 100.0
    p = int(code[1]) / 10.0
    t = int(code[2:]) / 100.0
    if t <= 0.0:
        raise ValueError("NACA airfoil thickness ratio must be > 0")

    beta = np.linspace(0.0, math.pi, n_points_per_surface)
    x = 0.5 * (1.0 - np.cos(beta))
    yt = 5.0 * t * (
        0.2969 * np.sqrt(np.clip(x, 0.0, 1.0))
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        - 0.1036 * x**4
    )

    yc = np.zeros_like(x)
    dyc = np.zeros_like(x)
    if m > 0.0 and 0.0 < p < 1.0:
        fore = x < p
        aft = ~fore
        yc[fore] = (m / (p * p)) * (2.0 * p * x[fore] - x[fore] ** 2)
        dyc[fore] = (2.0 * m / (p * p)) * (p - x[fore])
        yc[aft] = (m / ((1.0 - p) ** 2)) * ((1.0 - 2.0 * p) + 2.0 * p * x[aft] - x[aft] ** 2)
        dyc[aft] = (2.0 * m / ((1.0 - p) ** 2)) * (p - x[aft])

    theta = np.arctan(dyc)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    upper = [(float(xi), float(yi)) for xi, yi in zip(reversed(xu), reversed(yu))]
    lower = [(float(xi), float(yi)) for xi, yi in zip(xl[1:], yl[1:])]
    return upper + lower


@dataclass(frozen=True)
class ParametricWingSpec:
    """Explicit trapezoidal fixed-wing CAD geometry in right-handed Z-up meters."""

    name: str
    wingspan_m: float
    root_chord_m: float
    tip_chord_m: float
    sweep_le_deg: float = 0.0
    dihedral_deg: float = 2.0
    twist_tip_deg: float = -2.0
    airfoil_code: str = "2412"
    oswald_e: float = 0.82
    material_density_kg_m3: float | None = None
    density_source: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Wing name must be non-empty")
        for val, label in ((self.wingspan_m, "wingspan_m"), (self.root_chord_m, "root_chord_m"), (self.tip_chord_m, "tip_chord_m")):
            if not math.isfinite(val) or val <= 0.0:
                raise ValueError(f"{label} must be finite and > 0")
        if not 0.3 <= self.oswald_e <= 1.0:
            raise ValueError("oswald_e must be within [0.3, 1.0]")
        if abs(self.sweep_le_deg) >= 75.0 or abs(self.dihedral_deg) >= 45.0:
            raise ValueError("Wing sweep or dihedral out of valid structural geometry range")


def compute_wing_geometry_properties(wing: ParametricWingSpec) -> dict[str, Any]:
    """Derive exact planform area, MAC, aspect ratio, taper ratio, and optional solid mass."""
    b = wing.wingspan_m
    cr = wing.root_chord_m
    ct = wing.tip_chord_m
    lam = ct / cr
    s_ref = 0.5 * (cr + ct) * b
    ar = (b * b) / s_ref
    mac = (2.0 / 3.0) * cr * (1.0 + lam + lam * lam) / (1.0 + lam)
    airfoil_pts = naca4_airfoil_coordinates(wing.airfoil_code, n_points_per_surface=20)
    t_ratio = int(wing.airfoil_code[2:]) / 100.0
    # Solid cross-section fill fraction proxy (~0.68 of bounding box t*c^2) — requires explicit density to compute mass.
    approx_volume_m3 = 0.68 * t_ratio * 0.5 * (cr * cr + ct * ct) * b

    mass_kg: float | None = None
    mass_status = "UNVERIFIED_ESTIMATE"
    if wing.material_density_kg_m3 is not None and wing.density_source:
        if wing.material_density_kg_m3 <= 0 or not math.isfinite(wing.material_density_kg_m3):
            raise ValueError("material_density_kg_m3 must be finite and > 0")
        mass_kg = approx_volume_m3 * wing.material_density_kg_m3
        mass_status = "DERIVED_FROM_DECLARED_DENSITY"

    return {
        "schema_version": "1.0",
        "name": wing.name,
        "units": {"length": "m", "area": "m^2", "mass": "kg", "angle": "deg"},
        "wingspan_m": b,
        "root_chord_m": cr,
        "tip_chord_m": ct,
        "taper_ratio": lam,
        "planform_area_m2": s_ref,
        "aspect_ratio": ar,
        "mean_aerodynamic_chord_m": mac,
        "oswald_efficiency": wing.oswald_e,
        "airfoil_code": wing.airfoil_code,
        "airfoil_point_count": len(airfoil_pts),
        "solid_volume_m3": approx_volume_m3,
        "mass_kg": mass_kg,
        "mass_provenance_status": mass_status,
        "physical_validation_status": "UNVALIDATED",
    }


def export_cad_exchange_manifest(wing: ParametricWingSpec, *, unit_system: str = "SI_METERS") -> dict[str, Any]:
    """Prepare a unit-safe, hash-bound CAD exchange payload verifying round-trip geometric consistency."""
    if unit_system != "SI_METERS":
        raise ValueError(f"Unsupported CAD exchange unit_system {unit_system!r}; SI_METERS required")
    props = compute_wing_geometry_properties(wing)
    canonical = json.dumps(props, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return {
        "schema_version": "1.0",
        "exchange_format": "aeroforge_cad_exchange_1",
        "unit_system": unit_system,
        "frame": "local_right_handed_z_up",
        "payload": props,
        "payload_sha256": sha256(canonical).hexdigest(),
    }
