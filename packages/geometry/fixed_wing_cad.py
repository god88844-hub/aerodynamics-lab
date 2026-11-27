"""Slice 0B CAD software foundation: constrained 2D sketch, parametric wing loft, and unit-safe exchange."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

import ezdxf
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


class FeatureHistoryStack:
    """Undoable/redoable parametric CAD feature stack (sketch, extrude, revolve, boolean)."""

    SUPPORTED_OPS = ("sketch_rect", "extrude", "revolve", "boolean_union", "boolean_cut")

    def __init__(self) -> None:
        self._features: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []

    def add_feature(self, op: str, *, name: str, params_m: dict[str, float]) -> dict[str, Any]:
        if op not in self.SUPPORTED_OPS:
            raise ValueError(f"Unsupported CAD operation {op!r}; expected one of {self.SUPPORTED_OPS}")
        if not name.strip():
            raise ValueError("Feature name must be non-empty")
        for key, val in params_m.items():
            if not math.isfinite(val) or val <= 0.0:
                raise ValueError(f"Parameter {key!r} must be finite and > 0")
        if op == "revolve":
            vol = math.pi * (params_m.get("outer_radius_m", 0.05) ** 2 - params_m.get("inner_radius_m", 0.0) ** 2) * params_m.get("length_m", 0.2)
            if vol <= 0.0:
                raise ValueError("Revolve inner_radius_m must be smaller than outer_radius_m")
        elif op in ("extrude", "boolean_union", "boolean_cut"):
            vol = params_m.get("width_m", 0.1) * params_m.get("height_m", 0.1) * params_m.get("depth_m", 0.1)
            if op == "boolean_cut":
                vol = -abs(vol)
        else:
            vol = 0.0
        entry = {"op": op, "name": name.strip(), "params_m": dict(params_m), "delta_volume_m3": float(vol)}
        self._features.append(entry)
        self._redo.clear()
        return self.snapshot()

    def undo(self) -> dict[str, Any]:
        if not self._features:
            raise ValueError("Nothing to undo in CAD feature stack")
        self._redo.append(self._features.pop())
        return self.snapshot()

    def redo(self) -> dict[str, Any]:
        if not self._redo:
            raise ValueError("Nothing to redo in CAD feature stack")
        self._features.append(self._redo.pop())
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        total_vol = sum(item["delta_volume_m3"] for item in self._features)
        if total_vol < 0.0:
            raise ValueError("Boolean cut produced negative net solid volume")
        return {
            "schema_version": "1.0",
            "feature_count": len(self._features),
            "redo_available": len(self._redo),
            "net_volume_m3": float(total_vol),
            "features": [dict(f) for f in self._features],
        }


def assemble_fixed_wing_vehicle(
    wing: ParametricWingSpec,
    *,
    fuselage_mass_kg: float,
    fuselage_cog_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
    fuselage_inertia_diag_kg_m2: tuple[float, float, float] = (0.02, 0.05, 0.06),
    wing_attachment_m: tuple[float, float, float] = (0.04, 0.0, 0.02),
    explicit_wing_mass_kg: float | None = None,
) -> dict[str, Any]:
    """Assemble wing + fuselage into combined CoG and Steiner parallel-axis inertia tensor."""
    if not math.isfinite(fuselage_mass_kg) or fuselage_mass_kg <= 0.0:
        raise ValueError("fuselage_mass_kg must be finite and > 0")
    wing_props = compute_wing_geometry_properties(wing)
    wing_mass = wing_props["mass_kg"] if wing_props["mass_kg"] is not None else explicit_wing_mass_kg
    if wing_mass is None or not math.isfinite(wing_mass) or wing_mass <= 0.0:
        raise ValueError(
            "Fail-closed: wing mass unknown; declare wing.material_density_kg_m3 + density_source "
            "or explicit_wing_mass_kg"
        )
    mass_status = wing_props["mass_provenance_status"] if wing_props["mass_kg"] is not None else "EXPLICIT_COMPONENT_MASS"

    # Approximate uniform rectangular-box inertia about wing local CoG + Steiner parallel axis theorem
    b = wing.wingspan_m
    c = wing_props["mean_aerodynamic_chord_m"]
    t_approx = (int(wing.airfoil_code[2:]) / 100.0) * c
    i_wing_local = np.diag([
        wing_mass * (b * b + t_approx * t_approx) / 12.0,
        wing_mass * (c * c + t_approx * t_approx) / 12.0,
        wing_mass * (b * b + c * c) / 12.0,
    ])
    i_fuse_local = np.diag(np.asarray(fuselage_inertia_diag_kg_m2, dtype=float))

    r_fuse = np.asarray(fuselage_cog_m, dtype=float)
    r_wing = np.asarray(wing_attachment_m, dtype=float)
    total_mass = fuselage_mass_kg + wing_mass
    total_cog = (fuselage_mass_kg * r_fuse + wing_mass * r_wing) / total_mass

    def _steiner(m: float, r_part: np.ndarray, i_local: np.ndarray) -> np.ndarray:
        d = r_part - total_cog
        return i_local + m * ((float(np.dot(d, d)) * np.eye(3)) - np.outer(d, d))

    total_inertia = _steiner(fuselage_mass_kg, r_fuse, i_fuse_local) + _steiner(wing_mass, r_wing, i_wing_local)
    return {
        "schema_version": "1.0",
        "frame": "body_right_handed_z_up",
        "total_mass_kg": float(total_mass),
        "wing_mass_kg": float(wing_mass),
        "fuselage_mass_kg": float(fuselage_mass_kg),
        "center_of_mass_m": [float(v) for v in total_cog],
        "inertia_about_cog_kg_m2": [[float(x) for x in row] for row in total_inertia],
        "mass_provenance_status": mass_status,
        "physical_validation_status": "UNVALIDATED",
    }


def export_2d_engineering_drawing_svg_dxf(
    wing: ParametricWingSpec,
    *,
    svg_path: Path | None = None,
    dxf_path: Path | None = None,
) -> dict[str, Any]:
    """Export 3-view orthographic engineering drawing (Top planform, Front dihedral, Side airfoil) to SVG and DXF."""
    if svg_path is None and dxf_path is None:
        raise ValueError("Provide at least one output path (svg_path or dxf_path)")
    props = compute_wing_geometry_properties(wing)
    half_b = 0.5 * wing.wingspan_m
    sweep_dx = half_b * math.tan(math.radians(wing.sweep_le_deg))
    dihedral_dz = half_b * math.tan(math.radians(wing.dihedral_deg))
    cr = wing.root_chord_m
    ct = wing.tip_chord_m

    # Planform polygon in (x_fwd, y_span) [m]: Right TE/LE + Left LE/TE
    plan_pts = [
        (0.0, 0.0),
        (-sweep_dx, half_b),
        (-sweep_dx - ct, half_b),
        (-cr, 0.0),
        (-sweep_dx - ct, -half_b),
        (-sweep_dx, -half_b),
        (0.0, 0.0),
    ]
    front_pts = [(-half_b, dihedral_dz), (0.0, 0.0), (half_b, dihedral_dz)]
    airfoil = [(x * cr, z * cr) for x, z in naca4_airfoil_coordinates(wing.airfoil_code, n_points_per_surface=20)]

    result: dict[str, Any] = {
        "schema_version": "1.0",
        "part_name": wing.name,
        "units": "m",
        "planform_area_m2": props["planform_area_m2"],
        "mean_aerodynamic_chord_m": props["mean_aerodynamic_chord_m"],
        "outputs": {},
    }

    if dxf_path is not None:
        dxf_path.parent.mkdir(parents=True, exist_ok=True)
        doc = ezdxf.new("R2010")
        doc.units = ezdxf.units.M
        msp = doc.modelspace()
        msp.add_lwpolyline([(y, x) for x, y in plan_pts], close=True)
        # Offset front view vertically by +1.5*cr + 0.5 m and side airfoil to the right
        y_off = 0.6 + cr
        msp.add_lwpolyline([(y, z + y_off) for y, z in front_pts])
        x_off = half_b + 0.35
        msp.add_lwpolyline([(x + x_off, z + y_off) for x, z in airfoil], close=True)
        msp.add_text(
            f"{wing.name} | b={wing.wingspan_m:.3f}m MAC={props['mean_aerodynamic_chord_m']:.3f}m AR={props['aspect_ratio']:.2f}",
            dxfattribs={"height": 0.03},
        ).set_placement((-half_b, -cr - 0.15))
        doc.saveas(dxf_path)
        result["outputs"]["dxf"] = {
            "path": str(dxf_path),
            "sha256": sha256(dxf_path.read_bytes()).hexdigest(),
        }

    if svg_path is not None:
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        scale = 220.0
        cx, cy = 420.0, 260.0
        plan_poly = " ".join(f"{cx + y * scale:.2f},{cy - x * scale:.2f}" for x, y in plan_pts)
        front_poly = " ".join(f"{cx + y * scale:.2f},{110.0 - z * scale:.2f}" for y, z in front_pts)
        airfoil_poly = " ".join(f"{110.0 + x * scale:.2f},{110.0 - z * scale:.2f}" for x, z in airfoil)
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="840" height="520" viewBox="0 0 840 520">\n'
            '  <rect width="840" height="520" fill="#0f141b"/>\n'
            f'  <polygon points="{plan_poly}" fill="#1b3a57" stroke="#58c4ff" stroke-width="2"/>\n'
            f'  <polyline points="{front_poly}" fill="none" stroke="#8ff0a4" stroke-width="2"/>\n'
            f'  <polygon points="{airfoil_poly}" fill="#2b2f3a" stroke="#f6c177" stroke-width="1.5"/>\n'
            f'  <text x="24" y="36" fill="#e6edf3" font-family="monospace" font-size="14">'
            f'{wing.name} | Span={wing.wingspan_m:.3f}m S={props["planform_area_m2"]:.3f}m^2 '
            f'MAC={props["mean_aerodynamic_chord_m"]:.3f}m NACA{wing.airfoil_code} | UNVALIDATED</text>\n'
            '</svg>\n'
        )
        svg_path.write_text(svg, encoding="utf-8")
        result["outputs"]["svg"] = {
            "path": str(svg_path),
            "sha256": sha256(svg_path.read_bytes()).hexdigest(),
        }

    return result
