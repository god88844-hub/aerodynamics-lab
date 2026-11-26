"""Structural material database loader (data/components/materials.json).

Every material carries source + uncertainty; a structural check or mass-property
computation that lacks a finite positive density or a valid source must fail closed
("unknown property", not "pass").
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aeroforge_schemas.component import SOURCED, UNVERIFIED_ESTIMATE


@dataclass(frozen=True)
class MaterialProps:
    id: str
    name: str
    density_kg_m3: float
    youngs_modulus_pa: float
    yield_strength_pa: float
    ultimate_tensile_strength_pa: float
    source: str
    uncertainty_pct: float
    notes: str
    status: str = SOURCED
    physical_identity: dict[str, Any] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)
    operating_limits: dict[str, float | int] = field(default_factory=dict)
    parameter_provenance: dict[str, Any] = field(default_factory=dict)


def load_materials(materials_json: Path | str) -> dict[str, MaterialProps]:
    path = Path(materials_json)
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, MaterialProps] = {}
    for m in raw["materials"]:
        mat_id = m.get("id", "<unknown>")
        density = m.get("density_kg_m3")
        if density is None or isinstance(density, bool) or not math.isfinite(float(density)) or float(density) <= 0.0:
            raise ValueError(f"material {mat_id!r}: missing or non-positive density_kg_m3")
        source = m.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"material {mat_id!r}: missing density/material source")
        if "uncertainty_pct" not in m or m["uncertainty_pct"] is None:
            raise ValueError(f"material {mat_id!r}: missing uncertainty_pct")
        unc = float(m["uncertainty_pct"])
        if not math.isfinite(unc) or unc < 0.0:
            raise ValueError(f"material {mat_id!r}: uncertainty_pct must be finite and >= 0")
        estimated = bool(m.get("estimated", False))
        status = str(m.get("status") or (UNVERIFIED_ESTIMATE if estimated else SOURCED))
        out[m["id"]] = MaterialProps(
            id=m["id"],
            name=m["name"],
            density_kg_m3=float(density),
            youngs_modulus_pa=float(m["youngs_modulus_pa"]),
            yield_strength_pa=float(m["yield_strength_pa"]),
            ultimate_tensile_strength_pa=float(m["ultimate_tensile_strength_pa"]),
            source=source.strip(),
            uncertainty_pct=unc,
            notes=m.get("notes", ""),
            status=status,
            physical_identity=dict(m.get("physical_identity") or {}),
            units=dict(m.get("units") or {}),
            operating_limits=dict(m.get("operating_limits") or {}),
            parameter_provenance=dict(m.get("parameter_provenance") or {}),
        )
    return out
