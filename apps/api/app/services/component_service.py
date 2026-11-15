"""Component evidence database service: lists the sourced component entries
for the editor's pickers. Every entry carries provenance; estimated entries
are flagged so the UI can mark them."""

from __future__ import annotations

from pathlib import Path

from physics.propulsion.loader import ComponentLibrary

REPO_ROOT = Path(__file__).resolve().parents[4]  # app/services -> aeroforge root


def _summary(spec) -> dict:
    return {
        "id": spec.id,
        "name": spec.name,
        "estimated": bool(spec.source.estimated),
        "uncertainty_pct": spec.source.uncertainty_pct,
        "source": spec.source.source,
        "mass_kg": getattr(spec, "mass_kg", None),
    }


def list_components(data_dir: Path | None = None) -> dict:
    library = ComponentLibrary(data_dir or (REPO_ROOT / "data" / "components"))
    out: dict[str, list[dict]] = {"motors": [], "propellers": [], "batteries": [], "escs": []}

    kind_dirs = {"motors": "motors", "propellers": "propellers",
                 "batteries": "batteries", "escs": "controllers"}
    models = {"motors": "motor", "propellers": "propeller",
              "batteries": "battery", "escs": "esc"}
    for list_key, dir_name in kind_dirs.items():
        kind_dir = library.data_dir / dir_name
        if not kind_dir.is_dir():
            continue
        for path in sorted(kind_dir.glob("*.json")):
            spec = library.load(models[list_key], path.stem)
            entry = _summary(spec)
            if list_key == "propellers":
                entry["diameter_in"] = spec.diameter_in
                entry["pitch_in"] = spec.pitch_in
            if list_key == "batteries":
                entry["capacity_ah"] = spec.capacity_ah
                entry["cells_series"] = spec.cells_series
            if list_key == "escs":
                entry["max_continuous_current_a"] = spec.max_continuous_current_a
            out[list_key].append(entry)

    # Materials (structural DB).
    materials_path = library.data_dir / "materials.json"
    materials = []
    if materials_path.is_file():
        import json

        raw = json.loads(materials_path.read_text(encoding="utf-8"))
        for m in raw.get("materials", []):
            materials.append({
                "id": m["id"],
                "name": m["name"],
                "yield_strength_pa": m.get("yield_strength_pa"),
                "uncertainty_pct": m.get("uncertainty_pct", 10.0),
            })
    out["materials"] = materials
    return out
