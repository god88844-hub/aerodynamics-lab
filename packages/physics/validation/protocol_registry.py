"""P0A-026: Fail-closed registration of frozen component and multirotor validation protocols."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from physics.validation.validation_protocol import (
    ProtocolAuditRequest,
    ValidationProtocol,
    audit_protocol,
    protocol_sha256,
)

REQUIRED_TOLERANCE_FAMILIES = ("M21", "M22", "M23", "M24", "M25", "M26", "M27")


def register_validation_protocol(
    protocol_payload: dict[str, Any],
    *,
    tolerance_bindings: dict[str, Any],
    frozen_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate, freeze, and register a validation protocol.

    Refuses (fail closed) when calibration groups, held-out whole experiments (< 2),
    or M21-M27 tolerance bindings are missing or collide.
    """
    missing_families = [fam for fam in REQUIRED_TOLERANCE_FAMILIES if not tolerance_bindings.get(fam)]
    if missing_families:
        raise ValueError(f"Missing required tolerance bindings for: {', '.join(missing_families)}")

    protocol = ValidationProtocol.model_validate(protocol_payload)
    calibration = [exp for exp in protocol.experiments if exp.role == "calibration"]
    holdouts = [exp for exp in protocol.experiments if exp.role == "holdout"]
    if not calibration:
        raise ValueError("Protocol registration refused: missing calibration experiment group")
    if len(holdouts) < 2:
        raise ValueError("Protocol registration refused: at least two held-out whole experiments are required")

    for cal in calibration:
        for hold in holdouts:
            if (
                cal.recording_id == hold.recording_id
                or cal.experiment_id == hold.experiment_id
                or cal.vehicle_id == hold.vehicle_id
                or cal.battery_id == hold.battery_id
            ):
                raise ValueError("Protocol registration refused: calibration and holdout groups collide")

    digest = protocol_sha256(protocol)
    expected_sha = frozen_sha256 or digest
    audit = audit_protocol(ProtocolAuditRequest(protocol=protocol, expected_frozen_sha256=expected_sha))

    return {
        "schema_version": "1.0",
        "protocol_id": protocol.protocol_id,
        "frozen_protocol_sha256": expected_sha,
        "computed_protocol_sha256": digest,
        "tolerance_bindings": {fam: tolerance_bindings[fam] for fam in REQUIRED_TOLERANCE_FAMILIES},
        "calibration_experiments": [e.recording_id for e in calibration],
        "holdout_experiments": [e.recording_id for e in holdouts],
        "audit_status": audit["readiness_status"],
        "blockers": audit["blockers"],
        "independently_approved": False,
        "decision_equivalent_to_physical_testing": False,
    }


def load_frozen_protocol_catalog(catalog_path: Path) -> dict[str, Any]:
    import json

    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    records = raw.get("protocols", [])
    if not records:
        raise ValueError("Frozen protocol catalog contains no protocols")
    verified = []
    for entry in records:
        reg = register_validation_protocol(
            entry["protocol"],
            tolerance_bindings=entry["tolerance_bindings"],
            frozen_sha256=entry.get("frozen_protocol_sha256"),
        )
        if entry.get("frozen_protocol_sha256") and reg["computed_protocol_sha256"] != entry["frozen_protocol_sha256"]:
            raise ValueError(f"Frozen protocol digest mismatch for {reg['protocol_id']}")
        verified.append(reg)
    return {"schema_version": raw.get("schema_version", "1.0"), "protocols": verified}
