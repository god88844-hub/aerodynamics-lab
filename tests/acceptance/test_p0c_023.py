"""P0C-023: Exit: four-family and detailed-analysis software slice verification & open physical gap checks."""

from __future__ import annotations

import json
from pathlib import Path

from physics.validation.protocol_registry import load_frozen_protocol_catalog

ROOT = Path(__file__).resolve().parents[2]


def test_p0c_023_four_family_software_exit_proof_and_gap_preservation():
    tasks = json.loads((ROOT / "docs" / "planning" / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    by_id = {t["id"]: t for t in tasks}
    for phys_id in ("P0C-015", "P0C-016", "P0C-017", "P0C-018", "P0C-019", "P0C-020", "P0C-024"):
        assert by_id[phys_id]["status"] == "todo"

    cat = load_frozen_protocol_catalog(ROOT / "data" / "research" / "extended_protocols.json")
    assert any(p["protocol_id"] == "P0C014-ROTORCRAFT-VTOL-V1" for p in cat["protocols"])

    proof_023 = ROOT / "docs" / "acceptance" / "P0C-023.md"
    assert proof_023.is_file()
    txt = proof_023.read_text(encoding="utf-8")
    assert "P0C-015" in txt and "P0C-020" in txt
