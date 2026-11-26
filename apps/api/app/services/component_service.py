"""Component evidence database service: lists the sourced component entries
for the editor's pickers and exports. Every entry carries provenance; unsourced
typical values and assumed uncertainty bands surface UNVERIFIED_ESTIMATE."""

from __future__ import annotations

from pathlib import Path

from aeroforge_schemas.component import SOURCED, UNVERIFIED_ESTIMATE, collect_unverified_estimates
from physics.propulsion.loader import ComponentLibrary

REPO_ROOT = Path(__file__).resolve().parents[4]  # app/services -> aeroforge root


def _provenance_dict(spec) -> dict:
    prov = getattr(spec, "parameter_provenance", None) or {}
    return {
        k: (v.model_dump() if hasattr(v, "model_dump") else dict(v))
        for k, v in prov.items()
    }


def _summary(spec) -> dict:
    unverified = collect_unverified_estimates(spec)
    source = getattr(spec, "source", None)
    estimated = bool(source.estimated) if hasattr(source, "estimated") else bool(getattr(spec, "estimated", False))
    uncertainty_pct = source.uncertainty_pct if hasattr(source, "uncertainty_pct") else getattr(spec, "uncertainty_pct", 10.0)
    source_text = source.source if hasattr(source, "source") else getattr(spec, "source", "")
    status = UNVERIFIED_ESTIMATE if (unverified or estimated) else SOURCED
    return {
        "id": spec.id,
        "name": spec.name,
        "physical_identity": getattr(spec, "physical_identity", None),
        "units": getattr(spec, "units", None),
        "operating_limits": getattr(spec, "operating_limits", None),
        "estimated": estimated,
        "uncertainty_pct": uncertainty_pct,
        "source": source_text,
        "evidence_id": getattr(source, "evidence_id", None) if hasattr(source, "evidence_id") else getattr(spec, "evidence_id", None),
        "provenance_status": status,
        "has_unverified_estimates": bool(unverified),
        "unverified_estimates": unverified,
        "parameter_provenance": _provenance_dict(spec),
        "mass_kg": getattr(spec, "mass_kg", None),
    }


def list_components(data_dir: Path | None = None) -> dict:
    library = ComponentLibrary(data_dir or (REPO_ROOT / "data" / "components"))
    out: dict[str, list[dict]] = {
        "motors": [],
        "propellers": [],
        "batteries": [],
        "escs": [],
        "wiring": [],
        "sensors": [],
    }

    kind_dirs = {
        "motors": "motors",
        "propellers": "propellers",
        "batteries": "batteries",
        "escs": "controllers",
        "wiring": "wiring",
        "sensors": "sensors",
    }
    models = {
        "motors": "motor",
        "propellers": "propeller",
        "batteries": "battery",
        "escs": "esc",
        "wiring": "wiring",
        "sensors": "sensor",
    }
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
            if list_key == "wiring":
                entry["resistance_ohm_per_m"] = spec.resistance_ohm_per_m
                entry["max_continuous_current_a"] = spec.max_continuous_current_a
                entry["mass_kg_per_m"] = spec.mass_kg_per_m
            if list_key == "sensors":
                entry["sensor_kind"] = spec.sensor_kind
                entry["sample_rate_hz"] = spec.sample_rate_hz
                entry["latency_s"] = spec.latency_s
            out[list_key].append(entry)

    # Materials (structural DB).
    materials_path = library.data_dir / "materials.json"
    materials = []
    if materials_path.is_file():
        catalog = library.materials_catalog()
        for m in catalog.materials:
            unverified = collect_unverified_estimates(m)
            materials.append({
                "id": m.id,
                "name": m.name,
                "category": m.category,
                "physical_identity": m.physical_identity,
                "units": m.units,
                "density_kg_m3": m.density_kg_m3,
                "yield_strength_pa": m.yield_strength_pa,
                "operating_limits": m.operating_limits,
                "source": m.source,
                "evidence_id": m.evidence_id,
                "uncertainty_pct": m.uncertainty_pct,
                "estimated": m.estimated,
                "provenance_status": UNVERIFIED_ESTIMATE if (unverified or m.estimated) else SOURCED,
                "has_unverified_estimates": bool(unverified),
                "unverified_estimates": unverified,
                "parameter_provenance": _provenance_dict(m),
            })
    out["materials"] = materials
    return out
