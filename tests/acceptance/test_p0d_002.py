"""P0D-002: Versioned component, material, and source ingestion with immutable dated custody records."""

from __future__ import annotations

from pathlib import Path

import pytest

from desktop_worker.source_ingestion import ingest_custody_record

ROOT = Path(__file__).resolve().parents[2]


def test_p0d_002_immutable_custody_ingestion_and_provenance():
    store: dict[str, dict] = {}
    rec = ingest_custody_record(
        store,
        record_id="UIUC-APC-10x4.7",
        dated_version="2026-11-28",
        units="SI",
        rights_scope="academic_reference_preserved",
        raw_bytes=b"sample-prop-bytes",
        experiment_role="benchmark_reference",
        instrument_uncertainty_rel=0.015,
        has_measured_source=True,
    )
    assert rec["provenance_status"] == "SOURCED_MEASUREMENT"
    assert len(rec["raw_sha256"]) == 64

    # Attempting to overwrite the same dated snapshot fails closed
    with pytest.raises(ValueError, match="cannot be overwritten"):
        ingest_custody_record(
            store,
            record_id="UIUC-APC-10x4.7",
            dated_version="2026-11-28",
            units="SI",
            rights_scope="academic_reference_preserved",
            raw_bytes=b"mutated-bytes",
            experiment_role="benchmark_reference",
        )

    # Generic unsourced parameters must stay explicitly UNVERIFIED_ESTIMATE
    est = ingest_custody_record(
        store,
        record_id="GENERIC-MOTOR-KV",
        dated_version="2026-11-28",
        units="SI",
        rights_scope="clean_room_internal",
        raw_bytes=b"generic-estimate",
        experiment_role="component_datasheet",
        has_measured_source=False,
    )
    assert est["provenance_status"] == "UNVERIFIED_ESTIMATE"

    with pytest.raises(ValueError, match="rights_scope is required"):
        ingest_custody_record(
            store, record_id="BAD", dated_version="v1", units="SI", rights_scope="", raw_bytes=b"x", experiment_role="calibration"
        )
