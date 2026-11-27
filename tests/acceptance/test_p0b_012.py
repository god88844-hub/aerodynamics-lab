"""P0B-012: Register family-specific fixed-wing validation policy and frozen model annexes."""

from __future__ import annotations

import json
from pathlib import Path

from physics.validation.protocol_registry import load_frozen_protocol_catalog

ROOT = Path(__file__).resolve().parents[2]
EXT_CATALOG = ROOT / "data" / "research" / "extended_protocols.json"


def test_p0b_012_fixed_wing_protocol_annex_registered_without_multirotor_transfer():
    catalog = load_frozen_protocol_catalog(EXT_CATALOG)
    fw_reg = [p for p in catalog["protocols"] if p["protocol_id"] == "P0B012-FIXEDWING-GLIDER-V1"]
    assert len(fw_reg) == 1
    assert fw_reg[0]["independently_approved"] is False
    assert fw_reg[0]["decision_equivalent_to_physical_testing"] is False
    assert len(fw_reg[0]["holdout_experiments"]) >= 2

    raw = json.loads(EXT_CATALOG.read_text(encoding="utf-8"))
    raw_fw = next(item["protocol"] for item in raw["protocols"] if item["protocol"]["protocol_id"] == "P0B012-FIXEDWING-GLIDER-V1")
    assert "lifting-line" in raw_fw["intended_engineering_decision"].lower()
    assert raw_fw["independent_reviewer_reference"] == "PENDING_EXTERNAL_REVIEWER_RECEIPT_P0B_017"
    assert raw_fw["approved_test_safety_plan_reference"] == "PENDING_CUSTODIAN_SAFETY_PLAN_P0B_013"
