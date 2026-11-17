"""Synthetic timeline fixtures: chronology checks do not prove physical timestamps."""
from copy import deepcopy

import pytest

from physics.validation.preregistration_timeline import audit_declared_preregistration_sequence


def fixture():
    return {
        "freeze_manifest": {
            "frozen_model_git_sha": "a"*40,
            "frozen_protocol_sha256": "b"*64,
            "protocol_archived_at_utc": "2026-10-01T00:00:00Z",
            "model_frozen_at_utc": "2026-10-02T00:00:00Z",
            "predictions_frozen_at_utc": "2026-10-03T00:00:00Z",
            "claimed_archive_reference": "synthetic archive, no external attestation",
        },
        "provenance_report": {
            "status": "ORIGINAL_BYTES_CROSS_LINKED_EXTERNAL_AUTHENTICATION_REQUIRED",
            "holdout_audit": {
                "frozen_model_git_sha": "a"*40,
                "frozen_protocol_sha256_operator_supplied": "b"*64,
            },
            "source_bindings": [{"run_id": "holdout_a"}, {"run_id": "holdout_b"}],
        },
        "calibration_records": [
            {"run_id": "cal_a", "group_id": "cal_group",
             "started_at_utc": "2026-09-28T10:00:00Z",
             "completed_at_utc": "2026-09-28T12:00:00Z"},
        ],
        "holdout_records": [
            {"run_id": "holdout_a", "group_id": "hold_group_a",
             "started_at_utc": "2026-10-04T00:00:00Z",
             "completed_at_utc": "2026-10-04T01:00:00Z"},
            {"run_id": "holdout_b", "group_id": "hold_group_b",
             "started_at_utc": "2026-10-05T00:00:00Z",
             "completed_at_utc": "2026-10-05T01:00:00Z"},
        ],
    }


def test_declared_temporal_sequence_is_never_evidence_of_physical_origin():
    req = fixture()
    original = deepcopy(req)
    r = audit_declared_preregistration_sequence(**req)
    assert req == original
    assert r["status"] == "DECLARED_SEQUENCE_CONSISTENT_UNAUTHENTICATED"
    assert r["reported_temporal_order_consistent"]
    assert r["holdout_group_count"] == 2
    assert not r["archive_timestamp_authenticated"]
    assert not r["blind_holdout_independence_authenticated"]
    assert not r["actual_physical_validation_established"]
    assert not r["release_authorized"]


def test_predictions_reportedly_frozen_after_holdout_starts_fail():
    req = fixture()
    req["freeze_manifest"]["predictions_frozen_at_utc"] = "2026-10-04T00:00:01Z"
    r = audit_declared_preregistration_sequence(**req)
    assert r["status"] == "DECLARED_SEQUENCE_REJECTED"
    assert any("holdout" in b.lower() for b in r["blockers"])


def test_late_calibration_and_archive_order_fail():
    req = fixture()
    req["calibration_records"][0]["completed_at_utc"] = "2026-10-02T00:00:01Z"
    assert audit_declared_preregistration_sequence(**req)["status"] == "DECLARED_SEQUENCE_REJECTED"
    req = fixture()
    req["freeze_manifest"]["protocol_archived_at_utc"] = "2026-10-03T00:00:00Z"
    assert audit_declared_preregistration_sequence(**req)["status"] == "DECLARED_SEQUENCE_REJECTED"


def test_manifest_model_or_protocol_hash_mismatch_fails_closed():
    req = fixture()
    req["freeze_manifest"]["frozen_model_git_sha"] = "c"*40
    with pytest.raises(ValueError, match="identifiers differ"):
        audit_declared_preregistration_sequence(**req)
    req = fixture()
    req["freeze_manifest"]["frozen_protocol_sha256"] = "d"*64
    with pytest.raises(ValueError, match="identifiers differ"):
        audit_declared_preregistration_sequence(**req)


@pytest.mark.parametrize("bad", [
    "2026-10-04T00:00:00+00:00", "2026-10-04 00:00:00Z",
    "2026-02-30T00:00:00Z", "2026-10-04T00:00Z", "",
])
def test_noncanonical_or_invalid_timestamp_rejected(bad):
    req = fixture()
    req["holdout_records"][0]["started_at_utc"] = bad
    with pytest.raises(ValueError, match="UTC"):
        audit_declared_preregistration_sequence(**req)


def test_duplicate_run_ids_and_cross_group_reuse_rejected():
    req = fixture()
    req["holdout_records"][1]["run_id"] = "holdout_a"
    with pytest.raises(ValueError, match="duplicate"):
        audit_declared_preregistration_sequence(**req)
    req = fixture()
    req["holdout_records"][1]["group_id"] = "cal_group"
    with pytest.raises(ValueError, match="overlap"):
        audit_declared_preregistration_sequence(**req)


def test_missing_cross_link_and_synthetic_bad_source_gate():
    req = fixture()
    req["provenance_report"]["source_bindings"][1]["run_id"] = "unmatched"
    with pytest.raises(ValueError, match="differ from frozen"):
        audit_declared_preregistration_sequence(**req)
    req = fixture()
    req["provenance_report"]["status"] = "OPERATOR_PROVENANCE_BINDINGS_REJECTED"
    assert audit_declared_preregistration_sequence(**req)["status"] == "DECLARED_SEQUENCE_REJECTED"
