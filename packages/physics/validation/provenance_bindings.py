"""M27.4: cross-link raw hash-checked holdout traces to a frozen evidence ledger.

Every digest is checked against the *supplied* original CSV bytes by M27.2.
Ledger entries are still operator-controlled; this does NOT authenticate a
physical experiment, sensor calibration, preregistration time or custody.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from physics.validation.release_evidence_ledger import index_release_evidence
from physics.validation.source_pinned_holdouts import audit_source_pinned_holdouts


def audit_provenance_bindings(
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    frozen_design_sha256: str,
    channel: str,
    maximum_absolute_error: float,
    minimum_robust_coverage_fraction: float,
    calibration_group_ids: Sequence[str],
    runs: Sequence[Mapping],
    evidence_sources: Sequence[Mapping],
) -> dict:
    """Compare original file bytes and inventory identities without signing them.

    Each run must identify distinct observation_evidence_id and
    prediction_evidence_id entries in an M29.2 source ledger. Those entries
    must be holdout-role, share the run's experiment/group and frozen
    identities, use the selected channel and exact supplied original bytes.
    The observation entry must claim reported physical measurements; the
    prediction entry must identify software verification. Both claims are
    *labels*, never independently trusted measurements.
    """
    # Audit original bytes first, before interpreting any ledger metadata.
    holdouts = audit_source_pinned_holdouts(
        frozen_model_git_sha=frozen_model_git_sha,
        frozen_protocol_sha256=frozen_protocol_sha256,
        channel=channel,
        maximum_absolute_error=maximum_absolute_error,
        minimum_robust_coverage_fraction=minimum_robust_coverage_fraction,
        calibration_group_ids=calibration_group_ids,
        runs=runs,
    )
    ledger = index_release_evidence(
        frozen_model_git_sha=frozen_model_git_sha,
        frozen_protocol_sha256=frozen_protocol_sha256,
        frozen_design_sha256=frozen_design_sha256,
        sources=evidence_sources,
    )
    inventory = {s["evidence_id"]: s for s in ledger["canonical_inventory"]["sources"]}
    seen_evidence_ids: set[str] = set()
    links = []
    for run, original in zip(runs, holdouts["original_source_digest_checks"]):
        run_id = run["run_id"]
        ids = (run.get("observation_evidence_id"), run.get("prediction_evidence_id"))
        if any(not isinstance(key, str) or key not in inventory for key in ids):
            raise ValueError(f"{run_id}: both recorded evidence IDs must exist in source inventory")
        if ids[0] == ids[1] or any(key in seen_evidence_ids for key in ids):
            raise ValueError(f"{run_id}: duplicated evidence reference across original files")
        seen_evidence_ids.update(ids)
        for evidence_id, source_hash, expected_kind in (
            (ids[0], original["original_observations_digest_checked"], "reported_physical_measurements"),
            (ids[1], original["original_predictions_digest_checked"], "software_verification"),
        ):
            entry = inventory[evidence_id]
            if (
                entry["source_sha256_operator_supplied"] != source_hash
                or entry["group_id"] != run.get("group_id")
                or entry["experiment_id"] != run.get("experiment_id")
                or entry["channel"] != channel
                or entry["role"] != "holdout"
                or entry["source_kind"] != expected_kind
            ):
                raise ValueError(f"{run_id}: original bytes/source inventory identity mismatch")
        links.append({
            "run_id": run_id,
            "observations_evidence_id": ids[0],
            "predictions_evidence_id": ids[1],
            "original_byte_digests_cross_linked": True,
        })
    if len(links) != len(holdouts["runs"]):
        raise ValueError("some holdouts lack exact original provenance linkage")
    # A claim of two whole independent experimental groups must be examined
    # alongside the calibration metadata but cannot be *authenticated* here.
    if ledger["calibration_group_count"] < 1 or ledger["holdout_group_count"] < 2:
        raise ValueError("ledger lacks calibration or two holdout groups")
    return {
        "status": (
            "OPERATOR_PROVENANCE_BINDINGS_REJECTED"
            if holdouts["status"] == "REPORTED_HOLDOUT_REJECTED"
            else "ORIGINAL_BYTES_CROSS_LINKED_EXTERNAL_AUTHENTICATION_REQUIRED"
        ),
        "holdout_audit": holdouts,
        "inventory_sha256": ledger["canonical_inventory_sha256"],
        "source_binding_count": len(links) * 2,
        "source_bindings": links,
        "ledger_blockers": ledger["blockers"],
        "original_file_bytes_hashed_against_supplied_digests": True,
        "ledger_relationships_consistent": True,
        "external_physical_source_authenticity_established": False,
        "external_preregistration_or_independence_authenticated": False,
        "simulation_equivalent_to_physical_validation": False,
        "release_authorized": False,
        "limitations": [
            "Source digests and timestamps are operator-controlled; no trusted signing authority is checked",
            "Claimed physical measurement and experiment identities cannot establish actual test occurrence",
            "Exact sample alignment without a calibrated time synchronization budget cannot establish dynamics",
        ],
    }
