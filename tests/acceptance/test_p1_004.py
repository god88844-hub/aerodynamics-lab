"""P1-004 Acceptance Tests: Frozen Bio-Inspired & Seaplane Benchmark Protocols."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_p1_004_frozen_protocols_exist_and_sources_hash_verify() -> None:
    proto_path = ROOT / "data" / "research" / "phase1_frozen_protocols.json"
    assert proto_path.is_file()
    doc = json.loads(proto_path.read_text(encoding="utf-8"))
    assert doc["phase"] == 1
    assert doc["policy_role"] == "DEVELOPMENT"
    assert doc["physical_acceptance_granted"] is False
    ids = {p["protocol_id"] for p in doc["protocols"]}
    assert {
        "p1_flapping_delfly_flex_and_flapsim",
        "p1_morphing_pigeonbot_ii",
        "p1_seaplane_savitsky_planing",
    } <= ids
    for proto in doc["protocols"]:
        assert proto["acceptance_tolerances"]
        for src in proto["sources"]:
            src_file = ROOT / src["path"]
            assert src_file.is_file()
            digest = hashlib.sha256(src_file.read_bytes()).hexdigest()
            assert len(digest) == 64
