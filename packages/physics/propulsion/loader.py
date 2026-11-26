"""Component library: loads sourced component JSONs from data/components/**.

The library resolves by id using the repository's conventional layout:
    <data_dir>/motors/*.json
    <data_dir>/propellers/*.json
    <data_dir>/batteries/*.json
    <data_dir>/controllers/*.json   (ESC entries; flight controllers later)
    <data_dir>/wiring/*.json
    <data_dir>/sensors/*.json
    <data_dir>/materials.json
Every file is validated against the shared Pydantic schema on load, so
malformed or unsourced data cannot silently enter a simulation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aeroforge_schemas.component import (
    BatterySpec,
    EscSpec,
    MaterialsCatalog,
    MotorSpec,
    PropellerSpec,
    SensorSpec,
    WiringSpec,
    validate_component_record_acceptance,
)

_KIND_DIRS = {
    "motor": "motors",
    "propeller": "propellers",
    "battery": "batteries",
    "esc": "controllers",
    "wiring": "wiring",
    "sensor": "sensors",
}
_KIND_MODEL = {
    "motor": MotorSpec,
    "propeller": PropellerSpec,
    "battery": BatterySpec,
    "esc": EscSpec,
    "wiring": WiringSpec,
    "sensor": SensorSpec,
}


class ComponentLibrary:
    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        if not self.data_dir.is_dir():
            raise FileNotFoundError(f"component data dir not found: {self.data_dir}")
        self._cache: dict[tuple[str, str], object] = {}

    def load(self, kind: str, component_id: str):
        if kind not in _KIND_DIRS:
            raise ValueError(f"unknown component kind {kind!r}")
        key = (kind, component_id)
        if key in self._cache:
            return self._cache[key]
        path = self.data_dir / _KIND_DIRS[kind] / f"{component_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"component {kind}/{component_id} not found at {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        spec = _KIND_MODEL[kind].model_validate(raw)
        self._cache[key] = spec
        return spec

    def load_verified(self, kind: str, component_id: str) -> tuple[Any, dict[str, Any]]:
        """Load a component and enforce P0A-016 acceptance metadata (units/identity/limits/evidence)."""
        spec = self.load(kind, component_id)
        audit = validate_component_record_acceptance(spec, kind)
        return spec, audit

    def motor(self, component_id: str) -> MotorSpec:
        return self.load("motor", component_id)  # type: ignore[return-value]

    def propeller(self, component_id: str) -> PropellerSpec:
        return self.load("propeller", component_id)  # type: ignore[return-value]

    def battery(self, component_id: str) -> BatterySpec:
        return self.load("battery", component_id)  # type: ignore[return-value]

    def esc(self, component_id: str) -> EscSpec:
        return self.load("esc", component_id)  # type: ignore[return-value]

    def wiring(self, component_id: str) -> WiringSpec:
        return self.load("wiring", component_id)  # type: ignore[return-value]

    def sensor(self, component_id: str) -> SensorSpec:
        return self.load("sensor", component_id)  # type: ignore[return-value]

    def materials_catalog(self) -> MaterialsCatalog:
        path = self.data_dir / "materials.json"
        if not path.is_file():
            raise FileNotFoundError(f"materials catalog not found at {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return MaterialsCatalog.model_validate(raw)

    def validate_all_records(self) -> list[dict[str, Any]]:
        """Verify every component and material record in data_dir passes P0A-016 acceptance."""
        results: list[dict[str, Any]] = []
        for kind, subdir in _KIND_DIRS.items():
            folder = self.data_dir / subdir
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                _, audit = self.load_verified(kind, path.stem)
                results.append(audit)
        if (self.data_dir / "materials.json").is_file():
            catalog = self.materials_catalog()
            for mat in catalog.materials:
                results.append(validate_component_record_acceptance(mat, "material"))
        return results
