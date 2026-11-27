"""P0C-014: Register rotorcraft and VTOL validation campaigns and freeze annexes prior to reveal."""

from __future__ import annotations

import json
from pathlib import Path

from physics.validation.protocol_registry import load_frozen_protocol_catalog

ROOT = Path(__file__).resolve().parents[2]
EXT_CATALOG = ROOT / "data" / "research" / "extended_protocols.json"


def test_p0c_014_rotorcraft_vtol_campaign_registered_and_unrevealed():
    cat = load_frozen_protocol_catalog(EXT_CATALOG)
    reg = next(p for p in cat["protocols"] if p["protocol_id"] == "P0C014-ROTORCRAFT-VTOL-V1")
    assert reg["independently_approved"] is False
    assert reg["decision_equivalent_to_physical_testing"] is False
    assert len(reg["holdout_experiments"]) >= 2

    raw = json.loads(EXT_CATALOG.read_text(encoding="utf-8"))
    raw_014 = next(x["protocol"] for x in raw["protocols"] if x["protocol"]["protocol_id"] == "P0C014-ROTORCRAFT-VTOL-V1")
    assert raw_014["independent_reviewer_reference"] == "PENDING_EXTERNAL_REVIEWER_RECEIPT_P0C_020"
    assert raw_014["approved_test_safety_plan_reference"] == "PENDING_CUSTODIAN_SAFETY_PLAN_P0C_015"
