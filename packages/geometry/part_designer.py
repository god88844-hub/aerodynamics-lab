"""Parametric custom part designer & assembly part-swap workflow (Open CASCADE + analytic fallback)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

import ezdxf

SUPPORTED_SKETCH_KINDS = ("rounded_plate", "ring_duct", "airfoil_section", "hex_mount", "custom_propeller", "custom_body_shell")


@dataclass(frozen=True)
class CustomPartRecipe:
    """Versioned parametric 2D-sketch -> 3D feature recipe in SI meters."""

    part_name: str
    sketch_kind: str = "rounded_plate"
    width_m: float = 0.048
    length_m: float = 0.240
    thickness_m: float = 0.012
    hole_radius_m: float = 0.008
    revolve_360: bool = False
    circular_pattern_count: int = 1
    density_kg_m3: float = 1580.0
    density_source: str = ""
    airfoil_code: str = "2412"

    def __post_init__(self) -> None:
        if not self.part_name.strip():
            raise ValueError("part_name must be non-empty")
        if self.sketch_kind not in SUPPORTED_SKETCH_KINDS:
            raise ValueError(f"Unsupported sketch_kind {self.sketch_kind!r}; expected one of {SUPPORTED_SKETCH_KINDS}")
        for val, label in (
            (self.width_m, "width_m"),
            (self.length_m, "length_m"),
            (self.thickness_m, "thickness_m"),
            (self.density_kg_m3, "density_kg_m3"),
        ):
            if not math.isfinite(val) or val <= 0.0:
                raise ValueError(f"{label} must be finite and > 0")
        if not math.isfinite(self.hole_radius_m) or self.hole_radius_m < 0.0:
            raise ValueError("hole_radius_m must be finite and >= 0")
        if self.circular_pattern_count < 1 or self.circular_pattern_count > 12:
            raise ValueError("circular_pattern_count must be between 1 and 12")
        if not self.density_source.strip():
            raise ValueError("Custom part mass properties refused: density_source provenance is required")


def _analytic_unit_volume_m3(recipe: CustomPartRecipe) -> float:
    if recipe.revolve_360:
        r_out = max(0.02, 0.5 * recipe.width_m + 0.25 * recipe.length_m)
        r_in = min(recipe.hole_radius_m, 0.8 * r_out)
        return math.pi * (r_out * r_out - r_in * r_in) * recipe.thickness_m
    if recipe.sketch_kind == "ring_duct":
        r_out = max(0.03, recipe.width_m)
        r_in = max(0.005, min(r_out - recipe.thickness_m, 0.9 * r_out))
        return math.pi * (r_out * r_out - r_in * r_in) * (0.5 * recipe.length_m)
    if recipe.sketch_kind == "custom_propeller":
        prop_d = max(0.12, 1.4 * recipe.length_m)
        blades = max(2, min(6, recipe.circular_pattern_count if recipe.circular_pattern_count >= 2 else 2))
        return blades * (0.45 * 0.5 * prop_d) * recipe.width_m * recipe.thickness_m
    if recipe.sketch_kind == "custom_body_shell":
        return 0.42 * math.pi * (1.1 * recipe.width_m) ** 2 * (2.2 * recipe.length_m)
    if recipe.sketch_kind == "airfoil_section":
        t_ratio = max(0.04, int(recipe.airfoil_code[2:]) / 100.0) if len(recipe.airfoil_code) == 4 and recipe.airfoil_code.isdigit() else 0.12
        return 0.685 * recipe.length_m * (recipe.length_m * t_ratio) * recipe.thickness_m
    hole_area = math.pi * recipe.hole_radius_m * recipe.hole_radius_m
    plate_area = recipe.length_m * recipe.width_m
    effective_area = max(0.1 * plate_area, plate_area - hole_area)
    return effective_area * recipe.thickness_m


def _export_dxf_sketch(recipe: CustomPartRecipe, dxf_path: Path) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    l_mm = recipe.length_m * 1000.0
    w_mm = recipe.width_m * 1000.0
    if recipe.sketch_kind == "ring_duct" or recipe.revolve_360:
        r_out_mm = max(20.0, 0.5 * w_mm + 0.25 * l_mm)
        msp.add_circle((0.0, 0.0), radius=r_out_mm)
        if recipe.hole_radius_m > 0.0:
            msp.add_circle((0.0, 0.0), radius=recipe.hole_radius_m * 1000.0)
    else:
        pts = [(0.0, -0.5 * w_mm), (l_mm, -0.5 * w_mm), (l_mm, 0.5 * w_mm), (0.0, 0.5 * w_mm)]
        msp.add_lwpolyline(pts, close=True)
        if recipe.hole_radius_m > 0.0:
            msp.add_circle((l_mm, 0.0), radius=recipe.hole_radius_m * 1000.0)
    dxf_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(dxf_path))


def _write_ascii_stl_box(recipe: CustomPartRecipe, stl_path: Path) -> None:
    lx, ly, lz = recipe.length_m, recipe.width_m, recipe.thickness_m
    hx, hy, hz = lx * 0.5, ly * 0.5, lz * 0.5
    v = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
        (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz),
    ]
    tris = [
        ((0, 0, -1), v[0], v[3], v[2]), ((0, 0, -1), v[0], v[2], v[1]),
        ((0, 0, 1), v[4], v[5], v[6]), ((0, 0, 1), v[4], v[6], v[7]),
        ((0, -1, 0), v[0], v[1], v[5]), ((0, -1, 0), v[0], v[5], v[4]),
        ((0, 1, 0), v[2], v[3], v[7]), ((0, 1, 0), v[2], v[7], v[6]),
        ((-1, 0, 0), v[3], v[0], v[4]), ((-1, 0, 0), v[3], v[4], v[7]),
        ((1, 0, 0), v[1], v[2], v[6]), ((1, 0, 0), v[1], v[6], v[5]),
    ]
    lines = [f"solid {recipe.part_name.replace(' ', '_')}"]
    for n, a, b, c in tris:
        lines.append(f"  facet normal {n[0]} {n[1]} {n[2]}")
        lines.append("    outer loop")
        lines.append(f"      vertex {a[0]:.6f} {a[1]:.6f} {a[2]:.6f}")
        lines.append(f"      vertex {b[0]:.6f} {b[1]:.6f} {b[2]:.6f}")
        lines.append(f"      vertex {c[0]:.6f} {c[1]:.6f} {c[2]:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {recipe.part_name.replace(' ', '_')}")
    stl_path.parent.mkdir(parents=True, exist_ok=True)
    stl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_custom_part(recipe: CustomPartRecipe, export_dir: Path | None = None) -> dict[str, Any]:
    """Build a custom parametric part using Open CASCADE when available, else analytic B-Rep fallback."""
    geometry_backend = "analytic_brep_fallback"
    step_path_str: str | None = None
    stl_path_str: str | None = None
    dxf_path_str: str | None = None

    unit_vol = _analytic_unit_volume_m3(recipe)
    total_vol = unit_vol * recipe.circular_pattern_count
    total_mass = total_vol * recipe.density_kg_m3
    feature_history = ["Sketch2D", "Revolve360" if recipe.revolve_360 else "ExtrudeBoss"]
    if recipe.hole_radius_m > 0.0:
        feature_history.append("CutHole")
    if recipe.circular_pattern_count > 1:
        feature_history.append(f"CircularPattern_x{recipe.circular_pattern_count}")

    occt_used = False
    if export_dir is not None:
        export_dir.mkdir(parents=True, exist_ok=True)
        slug = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in recipe.part_name.lower()).strip("_") or "custom_part"
        dxf_path = export_dir / f"{slug}_sketch.dxf"
        stl_path = export_dir / f"{slug}.stl"
        _export_dxf_sketch(recipe, dxf_path)
        dxf_path_str = str(dxf_path)

        try:
            import cadquery as cq  # type: ignore

            w_mm = recipe.width_m * 1000.0
            l_mm = recipe.length_m * 1000.0
            t_mm = recipe.thickness_m * 1000.0
            solid = cq.Workplane("XY").box(l_mm, w_mm, t_mm)
            if recipe.hole_radius_m > 0.0 and recipe.hole_radius_m * 2.0 < min(recipe.width_m, recipe.length_m):
                solid = solid.faces(">Z").workplane().hole(recipe.hole_radius_m * 2000.0)
            step_path = export_dir / f"{slug}.step"
            cq.exporters.export(solid, str(step_path))
            cq.exporters.export(solid, str(stl_path))
            step_path_str = str(step_path)
            stl_path_str = str(stl_path)
            geometry_backend = "cadquery_occt"
            occt_used = True
        except ImportError:
            _write_ascii_stl_box(recipe, stl_path)
            stl_path_str = str(stl_path)

    digest = sha256(json.dumps(asdict(recipe), sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "schema_version": "1.0",
        "part_name": recipe.part_name,
        "sketch_kind": recipe.sketch_kind,
        "geometry_backend": geometry_backend,
        "occt_exact_brep": occt_used,
        "feature_history": feature_history,
        "volume_m3": total_vol,
        "mass_kg": total_mass,
        "density_kg_m3": recipe.density_kg_m3,
        "density_source": recipe.density_source,
        "recipe_sha256": digest,
        "exports": {
            "dxf": dxf_path_str,
            "stl": stl_path_str,
            "step": step_path_str,
        },
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }


def swap_assembly_part(
    parts: list[dict[str, Any]],
    *,
    target_part_name: str,
    replacement: CustomPartRecipe,
    replacement_position_m: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """Replace a part in an existing vehicle assembly and recompute total mass and CoG."""
    built = build_custom_part(replacement)
    updated_parts: list[dict[str, Any]] = []
    replaced = False

    for item in parts:
        if item.get("name") == target_part_name and not replaced:
            pos = list(replacement_position_m) if replacement_position_m is not None else list(item.get("position_m", [0.0, 0.0, 0.0]))
            updated_parts.append(
                {
                    "name": replacement.part_name,
                    "category": "custom_redesigned_part",
                    "mass_kg": built["mass_kg"],
                    "position_m": pos,
                    "recipe_sha256": built["recipe_sha256"],
                }
            )
            replaced = True
        else:
            updated_parts.append(dict(item))

    if not replaced:
        raise ValueError(f"Target assembly part {target_part_name!r} not found")

    total_mass = sum(float(p["mass_kg"]) for p in updated_parts)
    if total_mass <= 0.0:
        raise ValueError("Combined assembly mass must be positive")
    cog = [
        sum(float(p["mass_kg"]) * float(p["position_m"][axis]) for p in updated_parts) / total_mass
        for axis in range(3)
    ]
    return {
        "schema_version": "1.0",
        "replaced_part": target_part_name,
        "new_part": replacement.part_name,
        "total_mass_kg": total_mass,
        "center_of_mass_m": cog,
        "parts": updated_parts,
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }
