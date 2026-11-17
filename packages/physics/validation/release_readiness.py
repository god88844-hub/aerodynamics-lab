"""M29.3 cross-domain release gate for operator-supplied audit snapshots.

This read-only gate never authenticates GitHub checks, hardware measurements
or physical safety approval. It cannot authorize flight or production.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_CI = frozenset(("python-tests", "web-build"))


def assess_release_readiness(
    *,
    frozen_model_git_sha: str,
    expected_inventory_sha256: str,
    provenance_report: Mapping,
    geometry_report: Mapping,
    reported_ci_jobs: Mapping,
    engineering_review_reference: str,
) -> dict:
    """Assess *reported* software consistency; physical release always blocked.

    The provided provenance/geometry snapshots and CI reports are not trusted
    external attestations. This function never opens original files or GitHub
    CI, so a software consistency result is NOT a CI or physical certificate.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be lowercase 40-hex")
    if not isinstance(expected_inventory_sha256, str) or not _SHA256.fullmatch(expected_inventory_sha256):
        raise ValueError("expected_inventory_sha256 must be lowercase SHA-256")
    if not isinstance(engineering_review_reference, str) or not 1 <= len(engineering_review_reference.strip()) <= 500:
        raise ValueError("engineering_review_reference required")
    if any(not isinstance(v, Mapping) for v in (provenance_report, geometry_report, reported_ci_jobs)):
        raise ValueError("provenance, geometry and CI reports must be mapping objects")
    if set(reported_ci_jobs) != _REQUIRED_CI:
        raise ValueError("both exact CI job names are required")
    if any(type(reported_ci_jobs[job]) is not bool for job in _REQUIRED_CI):
        raise ValueError("CI states must be booleans, not labels")
    report_model = provenance_report.get("holdout_audit")
    if not isinstance(report_model, Mapping):
        raise ValueError("complete provenance holdout audit required")
    if report_model.get("frozen_model_git_sha") != frozen_model_git_sha:
        raise ValueError("provenance model identity differs from requested frozen model")
    if provenance_report.get("inventory_sha256") != expected_inventory_sha256:
        raise ValueError("source inventory SHA-256 differs from expected frozen ledger")
    if not isinstance(geometry_report.get("pairs"), list):
        raise ValueError("complete geometry pair report required")
    if geometry_report.get("design_name") in (None, ""):
        raise ValueError("geometry design identity required")
    # These booleans are informational only; even a maliciously supplied True
    # flag cannot turn this software audit into physical release authority.
    provenance_ok = (
        provenance_report.get("status") == "ORIGINAL_BYTES_CROSS_LINKED_EXTERNAL_AUTHENTICATION_REQUIRED"
        and provenance_report.get("ledger_relationships_consistent") is True
        and provenance_report.get("original_file_bytes_hashed_against_supplied_digests") is True
        and report_model.get("status") == "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    )
    geometry_ok = (
        geometry_report.get("status") == "ANALYTICAL_ASSUMED_3D_CYLINDER_NONINTERSECTION_ONLY"
        and geometry_report.get("analytical_screen_passed") is True
        and len(geometry_report["pairs"]) >= 1
    )
    ci_ok = all(reported_ci_jobs[job] for job in _REQUIRED_CI)
    blockers = []
    if not provenance_ok:
        blockers.append("Reported original-source and whole-holdout comparison gates incomplete")
    if not geometry_ok:
        blockers.append("Conservative assumed rotor swept-envelope nonintersection not established")
    if not ci_ok:
        blockers.append("Reported Python/frontend CI check missing or failing")
    blockers.extend([
        "GitHub CI/job identity and source code commit not authenticated by this offline gate",
        "Actual hardware provenance, calibration and source custody unauthenticated",
        "Independent physical model-prediction holdouts and preregistration timing unverified",
        "Rotor axes, blade flex and installed geometry uncertainty bounds not independently measured",
        "Qualified external engineering approvals and real-aircraft validation absent",
    ])
    consistency_ok = bool(provenance_ok and geometry_ok and ci_ok)
    snapshot = {
        "frozen_model_git_sha": frozen_model_git_sha,
        "inventory_sha256": expected_inventory_sha256,
        "geometry_design_name": geometry_report["design_name"],
        "reported_ci_jobs": {k: reported_ci_jobs[k] for k in sorted(_REQUIRED_CI)},
        "provenance_consistent_operator_reported": provenance_ok,
        "geometry_screen_operator_reported": geometry_ok,
        "engineering_review_reference_operator_supplied": engineering_review_reference.strip(),
    }
    serialized = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {
        "status": (
            "REPORTED_SOFTWARE_GATES_CONSISTENT_EXTERNAL_VERIFICATION_REQUIRED"
            if consistency_ok else "REPORTED_RELEASE_PREFLIGHT_BLOCKED"
        ),
        "software_preflight_consistency_operator_reported": consistency_ok,
        "snapshot_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "snapshot": snapshot,
        "blockers": blockers,
        "ci_status_cryptographically_authenticated": False,
        "physical_source_authenticity_established": False,
        "independent_flight_prediction_validated": False,
        "design_decision_equivalent_to_physical_validation": False,
        "manufacturing_or_flight_release_authorized": False,
        "release_authorized": False,
    }
