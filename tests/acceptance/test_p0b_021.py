"""P0B-021: Exit: fixed-wing software slice verification and domain/gap declaration."""

from __future__ import annotations

import json
from pathlib import Path

from physics.validation.protocol_registry import load_frozen_protocol_catalog

ROOT = Path(__file__).resolve().parents[2]


def test_p0b_021_fixed_wing_software_exit_proof_and_gap_declaration():
    tasks = json.loads((ROOT / "docs" / "planning" / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    by_id = {t["id"]: t for t in tasks}
    # Verify unresolved physical gates remain external/open rather than fabricated
    for phys_id in ("P0B-013", "P0B-014", "P0B-015", "P0B-016", "P0B-017", "P0B-022"):
        assert by_id[phys_id]["status"] == "todo"

    catalog = load_frozen_protocol_catalog(ROOT / "data" / "research" / "extended_protocols.json")
    assert any(p["protocol_id"] == "P0B012-FIXEDWING-GLIDER-V1" for p in catalog["protocols"])

    proof_021 = ROOT / "docs" / "acceptance" / "P0B-021.md"
    assert proof_021.is_file()
    text = proof_021.read_text(encoding="utf-8")
    assert "P0B-013" in text and "physical" in text.lower()
