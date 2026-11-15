"""Component library: loads sourced component JSONs from data/components/**.

The library resolves by id using the repository's conventional layout:
    <data_dir>/motors/*.json
    <data_dir>/propellers/*.json
    <data_dir>/batteries/*.json
    <data_dir>/controllers/*.json   (ESC entries; flight controllers later)
Every file is validated against the shared Pydantic schema on load, so
malformed or unsourced data cannot silently enter a simulation.
"""

from __future__ import annotations

import json
from pathlib import Path

from aeroforge_schemas.component import BatterySpec, EscSpec, MotorSpec, PropellerSpec

_KIND_DIRS = {
    "motor": "motors",
    "propeller": "propellers",
    "battery": "batteries",
    "esc": "controllers",
}
_KIND_MODEL = {
    "motor": MotorSpec,
    "propeller": PropellerSpec,
    "battery": BatterySpec,
    "esc": EscSpec,
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

    def motor(self, component_id: str) -> MotorSpec:
        return self.load("motor", component_id)  # type: ignore[return-value]

    def propeller(self, component_id: str) -> PropellerSpec:
        return self.load("propeller", component_id)  # type: ignore[return-value]

    def battery(self, component_id: str) -> BatterySpec:
        return self.load("battery", component_id)  # type: ignore[return-value]

    def esc(self, component_id: str) -> EscSpec:
        return self.load("esc", component_id)  # type: ignore[return-value]
