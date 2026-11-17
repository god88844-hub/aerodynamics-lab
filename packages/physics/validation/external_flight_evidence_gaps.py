"""M26.16: explain independent evidence still required before physical acceptance.

Operator-presented reviewer documents and matching hashes prove only local
byte consistency. Their contents, issuers and actual historical truth are
NOT cryptographically or independently authenticated by this tool.
Even eight apparently complete files cannot authorize real flight.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
import re

_REVIEW_KINDS = (
    "original_recorder_custody",
    "source_license_or_permission",
    "installed_hardware_serials_and_revisions",
    "instrument_calibration_and_uncertainty",
    "sensor_clock_synchronization",
    "historical_preregistration_and_blind_holdout",
    "independent_engineering_reviewer",
    "operational_safety_authorization",
)
_DOC_FIELDS = {"evidence_kind", "document_path", "document_sha256", "claimed_issuer"}
_SHA = re.compile(r"^[a-f0-9]{64}$")
_MAX_DOCUMENT_BYTES = 5_000_000


def audit_external_flight_evidence_gaps(
    dossier: Mapping, *, review_documents: Sequence[Mapping],
    original_root: Path | str,
) -> dict:
    """Generate a checklist, never accept a proof claim or change original files."""
    if not isinstance(dossier, Mapping) or dossier.get("unresolved_external_evidence_issue") != 16:
        raise ValueError("recomputed M26 analytical dossier required")
    if not isinstance(dossier.get("status"), str) or dossier.get("decision_equivalent_physical_evidence_established") is not False:
        raise ValueError("physical validation must remain false for unauthenticated evidence")
    if isinstance(review_documents, (str, bytes)) or not isinstance(review_documents, Sequence) or len(review_documents) > len(_REVIEW_KINDS):
        raise ValueError("at most eight external review document records supported")
    base = Path(original_root).resolve(strict=True)
    present, observed = [], set()
    for item in review_documents:
        if not isinstance(item, Mapping) or set(item) != _DOC_FIELDS:
            raise ValueError("each review document must have exact evidence, path, SHA and issuer fields")
        kind = item["evidence_kind"]
        if not isinstance(kind, str) or kind not in _REVIEW_KINDS or kind in observed:
            raise ValueError("unique known evidence_kind required")
        observed.add(kind)
        digest = item["document_sha256"]
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError("external review document needs lowercase 64-hex SHA-256")
        issuer = item["claimed_issuer"]
        if not isinstance(issuer, str) or not 1 <= len(issuer.strip()) <= 200:
            raise ValueError("nonempty claimed_issuer required")
        path = Path(item["document_path"])
        if path.is_symlink() or not path.is_file():
            raise ValueError("review document must exist as a regular non-symlinked file")
        resolved = path.resolve(strict=True)
        if resolved.is_relative_to(base):
            raise ValueError("review document must not be stored in immutable original measurement root")
        size = resolved.stat().st_size
        if not 0 < size <= _MAX_DOCUMENT_BYTES:
            raise ValueError("review document must be 1..5000000 bytes")
        if sha256(resolved.read_bytes()).hexdigest() != digest:
            raise ValueError("review document source SHA-256 mismatch")
        present.append({
            "evidence_kind": kind,
            "document_sha256_checked_against_operator_pin": digest,
            "document_byte_count": size,
            "claimed_issuer_operator_reported": issuer.strip(),
            "document_contents_or_issuer_independently_authenticated": False,
        })
    missing = sorted(set(_REVIEW_KINDS) - observed)
    analytic = dossier["status"]
    if analytic.startswith("FAIL_"):
        status = "FAIL_CRITICAL_ANALYTIC_OR_OPERATING_LIMIT_SCREEN"
    else:
        status = "INCONCLUSIVE_EXTERNAL_PHYSICAL_VALIDATION_NOT_ESTABLISHED"
    return {
        "status": status,
        "dossier_sha256_operator_reported": dossier.get("reproducible_dossier_sha256"),
        "original_evidence_issue": 16,
        "required_external_evidence_kinds": list(_REVIEW_KINDS),
        "review_documents_present_but_unauthenticated": sorted(
            present, key=lambda x: x["evidence_kind"]),
        "review_document_kinds_missing": missing,
        "all_required_document_kinds_declared": not missing,
        "all_review_issuers_and_contents_authenticated": False,
        "original_recording_origin_and_hardware_authenticated": False,
        "instrument_uncertainty_and_clocks_authenticated": False,
        "actual_historical_blinding_authenticated": False,
        "physical_decision_equivalence_established": False,
        "flight_or_manufacturing_release_authorized": False,
    }
