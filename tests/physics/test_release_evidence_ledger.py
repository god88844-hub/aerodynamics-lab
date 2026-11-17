"""M29.2 release evidence accounting, not actual physical flight validation."""
from copy import deepcopy

import pytest

from physics.validation.release_evidence_ledger import index_release_evidence


def request():
    model, protocol, design = "a" * 40, "b" * 64, "c" * 64
    records = []
    for n in range(3):
        role = "calibration" if n == 0 else "holdout"
        records.append({
            "evidence_id": f"evidence_{n}",
            "experiment_id": f"experiment_{n}",
            "group_id": f"independent_group_{n}",
            "channel": "terminal_voltage_v",
            "role": role,
            "source_kind": "reported_physical_measurements",
            "source_sha256": str(n + 1) * 64,
            "source_reference": "operator-supplied, synthetic bytes test only",
            "frozen_model_git_sha": model,
            "frozen_protocol_sha256": protocol,
            "frozen_design_sha256": design,
        })
    return {
        "frozen_model_git_sha": model, "frozen_protocol_sha256": protocol,
        "frozen_design_sha256": design, "sources": records,
    }


def test_complete_self_reported_inventory_is_never_physical_release():
    input_data = request()
    original = deepcopy(input_data)
    result = index_release_evidence(**input_data)
    assert input_data == original
    assert result["status"] == "OPERATOR_EVIDENCE_INDEX_COMPLETE_NOT_VALIDATED"
    assert result["source_bytes_cryptographically_checked"] is False
    assert result["external_measurement_origin_authenticated"] is False
    assert result["release_physical_decision_equivalence_established"] is False
    assert result["flightworthiness_established"] is False
    assert result["release_authorized"] is False
    assert result["holdout_group_count"] == 2
    assert len(result["canonical_inventory_sha256"]) == 64


def test_deterministic_index_ignores_input_entry_order():
    data = request()
    first = index_release_evidence(**data)
    data["sources"].reverse()
    second = index_release_evidence(**data)
    assert first["canonical_inventory_sha256"] == second["canonical_inventory_sha256"]
    assert first["canonical_inventory"] == second["canonical_inventory"]


def test_duplicate_original_source_bytes_do_not_count_as_independent():
    data = request()
    data["sources"][2]["source_sha256"] = data["sources"][1]["source_sha256"]
    with pytest.raises(ValueError, match="reused original"):
        index_release_evidence(**data)


def test_cross_partition_group_overlap_blocks_positive_inventory():
    data = request()
    data["sources"][1]["group_id"] = data["sources"][0]["group_id"]
    result = index_release_evidence(**data)
    assert result["status"] == "OPERATOR_EVIDENCE_INVENTORY_HAS_GAPS"
    assert any("overlap" in b for b in result["blockers"])
    assert not result["release_authorized"]


def test_missing_independent_holdout_group_fails():
    data = request()
    data["sources"] = data["sources"][:2]
    result = index_release_evidence(**data)
    assert result["status"] == "OPERATOR_EVIDENCE_INVENTORY_HAS_GAPS"
    assert any("fewer than" in b for b in result["blockers"])


def test_synthetic_disguised_as_complete_physical_evidence_not_accepted():
    data = request()
    data["sources"][1]["source_kind"] = "synthetic_fixture"
    result = index_release_evidence(**data)
    assert result["status"] == "OPERATOR_EVIDENCE_INVENTORY_HAS_GAPS"
    assert not result["release_physical_decision_equivalence_established"]


def test_exact_frozen_ids_must_match():
    data = request()
    data["sources"][1]["frozen_model_git_sha"] = "d" * 40
    with pytest.raises(ValueError, match="different frozen"):
        index_release_evidence(**data)


def test_unexpected_validation_claim_rejected():
    data = request()
    data["sources"][1]["physically_validated"] = True
    with pytest.raises(ValueError, match="exact required fields"):
        index_release_evidence(**data)


def test_all_required_identifiers_and_source_sha_format_strict():
    data = request()
    data["sources"][0]["source_sha256"] = "not-a-real-digest"
    with pytest.raises(ValueError, match="invalid lowercase digest"):
        index_release_evidence(**data)
    data = request()
    data["sources"][0]["evidence_id"] = ""
    with pytest.raises(ValueError, match="identifier"):
        index_release_evidence(**data)
