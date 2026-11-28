"""Python loader and BOM evaluator for the expanded Standard Part & Propulsion Library."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "components" / "standards" / "standard_library_catalog.json"


def load_standard_library() -> dict[str, Any]:
    """Load the full JSON catalog of standard parts, fasteners, bearings, tubes, and propulsors."""
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def list_standard_library(category: str | None = None, query: str | None = None) -> list[dict[str, Any]]:
    """Filter standard library items by category and/or case-insensitive query."""
    items = load_standard_library().get("items", [])
    cat_l = (category or "").strip().lower()
    q_l = (query or "").strip().lower()
    out: list[dict[str, Any]] = []
    for item in items:
        if cat_l and cat_l != "all" and item.get("category", "").lower() != cat_l:
            continue
        if q_l and q_l not in item.get("name", "").lower() and q_l not in item.get("id", "").lower():
            continue
        out.append(item)
    return out


def get_standard_part(part_id: str) -> dict[str, Any]:
    """Retrieve a single standard part specification by ID."""
    for item in load_standard_library().get("items", []):
        if item.get("id") == part_id:
            return item
    raise KeyError(f"Unknown standard library part id: {part_id}")


def build_standard_bom_summary(part_ids: list[str]) -> dict[str, Any]:
    """Summarize total SI mass, part count, and provenance breakdown for inserted library parts."""
    catalog = {it["id"]: it for it in load_standard_library().get("items", [])}
    total_mass_kg = 0.0
    resolved: list[dict[str, Any]] = []
    for pid in part_ids:
        if pid not in catalog:
            raise KeyError(f"Unknown standard library part id: {pid}")
        it = catalog[pid]
        total_mass_kg += float(it["mass_kg"])
        resolved.append({"id": pid, "name": it["name"], "category": it["category"], "mass_kg": float(it["mass_kg"]), "provenance": it["provenance"]})
    return {
        "schema_version": "1.0",
        "count": len(resolved),
        "total_mass_kg": round(total_mass_kg, 6),
        "items": resolved,
    }
