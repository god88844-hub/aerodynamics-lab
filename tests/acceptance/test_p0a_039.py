"""P0A-039 Slice 0A software exit acceptance check."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_slice_0a_software_prerequisites_complete_and_physical_exit_open() -> None:
    plan = json.loads((ROOT / "docs/planning/tasks.json").read_text(encoding="utf-8-sig"))
    by_id = {t["id"]: t for t in plan["tasks"]}

    p0a_039 = by_id["P0A-039"]
    assert p0a_039["gate"] == "software_exit"
    assert p0a_039["status"] == "done"
    for dep in p0a_039["dependencies"]:
        assert by_id[dep]["status"] == "done", f"Prerequisite {dep} must be done"

    # Physical exit and custodian/reviewer receipts stay honestly separate and open
    assert by_id["P0A-040"]["status"] == "todo"
    assert by_id["P0A-027"]["status"] == "todo"
    assert by_id["P0A-030"]["status"] == "todo"
    assert by_id["P0A-033"]["status"] == "todo"

    ledger = (ROOT / "docs/ACCEPTANCE_LEDGER.md").read_text(encoding="utf-8")
    assert "P0A-039" in ledger
    assert (ROOT / "docs/acceptance/P0A-039.md").is_file()
