"""M29.3 synthetic release-preflight checks, never true flight certification."""
from copy import deepcopy

import pytest

from physics.validation.release_readiness import assess_release_readiness


def fixture():
    return {
        "frozen_model_git_sha": "a"*40,
        "expected_inventory_sha256": "b"*64,
        "engineering_review_reference": "hypothetical reviewer, no authentic approval",
        "provenance_report": {
            "status": "ORIGINAL_BYTES_CROSS_LINKED_EXTERNAL_AUTHENTICATION_REQUIRED",
            "inventory_sha256": "b"*64,
            "ledger_relationships_consistent": True,
            "original_file_bytes_hashed_against_supplied_digests": True,
            "holdout_audit": {
                "frozen_model_git_sha": "a"*40,
                "status": "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED",
            },
        },
        "geometry_report": {
            "status": "ANALYTICAL_ASSUMED_3D_CYLINDER_NONINTERSECTION_ONLY",
            "analytical_screen_passed": True,
            "design_name": "synthetic_quad",
            "pairs": [{"rotor_a": 0, "rotor_b": 1}],
        },
        "reported_ci_jobs": {"python-tests": True, "web-build": True},
    }


def test_self_reported_all_green_never_authorizes_flight():
    data = fixture()
    original = deepcopy(data)
    r = assess_release_readiness(**data)
    assert data == original
    assert r["status"] == "REPORTED_SOFTWARE_GATES_CONSISTENT_EXTERNAL_VERIFICATION_REQUIRED"
    assert r["software_preflight_consistency_operator_reported"]
    assert not r["ci_status_cryptographically_authenticated"]
    assert not r["physical_source_authenticity_established"]
    assert not r["independent_flight_prediction_validated"]
    assert not r["design_decision_equivalent_to_physical_validation"]
    assert not r["manufacturing_or_flight_release_authorized"]
    assert not r["release_authorized"]
    assert len(r["snapshot_sha256"]) == 64


def test_reported_failing_ci_blocks_software_preflight():
    data = fixture()
    data["reported_ci_jobs"]["python-tests"] = False
    r = assess_release_readiness(**data)
    assert r["status"] == "REPORTED_RELEASE_PREFLIGHT_BLOCKED"
    assert any("CI" in blocker for blocker in r["blockers"])


def test_failed_holdout_or_geometry_gate_fails_closed():
    data = fixture()
    data["provenance_report"]["holdout_audit"]["status"] = "REPORTED_HOLDOUT_REJECTED"
    assert not assess_release_readiness(**data)["software_preflight_consistency_operator_reported"]
    data = fixture()
    data["geometry_report"]["analytical_screen_passed"] = False
    assert not assess_release_readiness(**data)["software_preflight_consistency_operator_reported"]


def test_mutually_inconsistent_model_or_inventory_refused():
    data = fixture()
    data["provenance_report"]["inventory_sha256"] = "c"*64
    with pytest.raises(ValueError, match="inventory SHA-256"):
        assess_release_readiness(**data)
    data = fixture()
    data["provenance_report"]["holdout_audit"]["frozen_model_git_sha"] = "d"*40
    with pytest.raises(ValueError, match="model identity"):
        assess_release_readiness(**data)


def test_forged_physical_approval_flag_does_not_change_result():
    data = fixture()
    data["geometry_report"]["flightworthiness_established"] = True
    data["provenance_report"]["external_physical_source_authenticity_established"] = True
    data["provenance_report"]["release_authorized"] = True
    r = assess_release_readiness(**data)
    assert r["software_preflight_consistency_operator_reported"]
    assert not r["release_authorized"]


@pytest.mark.parametrize("ci", [
    {"python-tests": True},
    {"python-tests": "success", "web-build": True},
    {"python-tests": True, "web-build": True, "release": True},
])
def test_unverified_ci_status_shapes_rejected(ci):
    data = fixture()
    data["reported_ci_jobs"] = ci
    with pytest.raises(ValueError, match="CI"):
        assess_release_readiness(**data)


def test_snapshot_independent_of_python_dict_order():
    a = fixture()
    b = fixture()
    b["reported_ci_jobs"] = {"web-build": True, "python-tests": True}
    assert assess_release_readiness(**a)["snapshot_sha256"] == assess_release_readiness(**b)["snapshot_sha256"]
