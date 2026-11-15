"""Structural material database loader (data/components/materials.json).

Every material carries source + uncertainty; a structural check that needs a
material not present here must fail closed ("unknown property", not "pass").
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


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


def load_materials(materials_json: Path | str) -> dict[str, MaterialProps]:
    path = Path(materials_json)
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, MaterialProps] = {}
    for m in raw["materials"]:
        out[m["id"]] = MaterialProps(
            id=m["id"],
            name=m["name"],
            density_kg_m3=float(m["density_kg_m3"]),
            youngs_modulus_pa=float(m["youngs_modulus_pa"]),
            yield_strength_pa=float(m["yield_strength_pa"]),
            ultimate_tensile_strength_pa=float(m["ultimate_tensile_strength_pa"]),
            source=m.get("source", ""),
            uncertainty_pct=float(m.get("uncertainty_pct", 10.0)),
            notes=m.get("notes", ""),
        )
    return out
