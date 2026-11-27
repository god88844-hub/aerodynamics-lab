"""P0D-009: Register adverse-weather validation protocols prior to independent custodian measurements."""

from __future__ import annotations

import json
from pathlib import Path

from physics.validation.protocol_registry import load_frozen_protocol_catalog

ROOT = Path(__file__).resolve().parents[2]
EXT_CATALOG = ROOT / "data" / "research" / "extended_protocols.json"


def test_p0d_009_weather_protocol_registered_and_unvalidated():
    cat = load_frozen_protocol_catalog(EXT_CATALOG)
    w = next(p for p in cat["protocols"] if p["protocol_id"] == "P0D009-ADVERSE-WEATHER-V1")
    assert w["independently_approved"] is False
    assert w["decision_equivalent_to_physical_testing"] is False
    assert len(w["holdout_experiments"]) >= 2

    raw = json.loads(EXT_CATALOG.read_text(encoding="utf-8"))
    raw_w = next(x["protocol"] for x in raw["protocols"] if x["protocol"]["protocol_id"] == "P0D009-ADVERSE-WEATHER-V1")
    assert "P0D_010" in raw_w["approved_test_safety_plan_reference"] or "P0D" in raw_w["independent_reviewer_reference"]
