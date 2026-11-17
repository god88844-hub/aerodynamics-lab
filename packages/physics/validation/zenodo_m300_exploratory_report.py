"""M26.39: reproducible source-bound M300 preliminary evidence report.

All underlying numerical work is recomputed against the original pinned file.
Never counts data gaps as completed flights or treats nonmatching DJI hardware
as validation of AeroForge's 60-kg reference hexacopter.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json

from physics.validation.zenodo_original_quality import audit_original_m300_field_quality
from physics.validation.zenodo_original_time_segments import audit_original_m300_time_segments
from physics.validation.zenodo_original_channel_probe import inspect_declared_original_m300_channel
from physics.validation.zenodo_flight_candidate import DOI

def build_original_m300_exploratory_report(
    path, receipt: Mapping, *,
    original_time_column: str, original_time_unit: str,
    declared_max_sample_gap_s: float,
    channel_mappings: Sequence[Mapping],
    reference_aircraft: str = "60 kg hexacopter",
) -> dict:
    if (not isinstance(channel_mappings, Sequence) or isinstance(channel_mappings, (str, bytes))
            or not 1 <= len(channel_mappings) <= 32):
        raise ValueError("1..32 documented source channel mappings required")
    if not isinstance(reference_aircraft, str) or not reference_aircraft.strip():
        raise ValueError("reference airframe identity required")
    quality = audit_original_m300_field_quality(path, receipt)
    timing = audit_original_m300_time_segments(
        path, receipt, original_time_column=original_time_column,
        original_time_unit=original_time_unit,
        declared_max_sample_gap_s=declared_max_sample_gap_s,
    )
    seen = set()
    channels = []
    required = {"original_column", "claimed_channel", "claimed_original_unit",
                "instrument_unit_document_reference"}
    for row in channel_mappings:
        if not isinstance(row, Mapping) or set(row) != required:
            raise ValueError("exact original-source channel mapping keys required")
        if row["original_column"] in seen:
            raise ValueError("cannot duplicate original source column in one evidence report")
        seen.add(row["original_column"])
        channels.append(inspect_declared_original_m300_channel(path, receipt, **row))
    if quality["has_missing_cells"]:
        source = "INCONCLUSIVE_SOURCE_HAS_UNRESOLVED_MISSINGNESS"
    elif timing["blocks_with_sufficient_rows"] == 0:
        source = "INCONCLUSIVE_NO_CONTIGUOUS_SAMPLING_BLOCK"
    else:
        source = "SOURCE_BYTES_CONSISTENT_FOR_EXPLORATION_HARDWARE_UNMATCHED"
    canonical = {
        "source_sha256": quality["source_sha256"],
        "source_doi": DOI, "original_bytes": quality["original_bytes"],
        "reference_aircraft": reference_aircraft,
        "original_aircraft": "DJI Matrice 300",
        "columns": quality["columns"],
        "timing": {k: v for k, v in timing.items() if k not in (
            "distinct_flights_or_original_clock_authenticated",
            "independent_holdout_blinding_authenticated",
            "flight_validation_authorized",
        )},
        "channels": sorted(channels, key=lambda x: x["original_column"]),
        "status": source,
    }
    digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                               allow_nan=False).encode("utf-8")).hexdigest()
    return {
        "status": source,
        "reproducible_exploratory_report_sha256": digest,
        "original_quality": quality,
        "original_timestamp_segments": timing,
        "operator_mapped_original_channels": canonical["channels"],
        "reference_aircraft": reference_aircraft,
        "actual_published_aircraft": "DJI Matrice 300",
        "source_classification": "original_provider_md5_matched_if_real_local_file",
        "separate_segments_prove_independent_flights": False,
        "sensor_units_and_calibration_authenticated": False,
        "full_vehicle_hardware_match_authenticated": False,
        "true_historical_blind_model_freeze_authenticated": False,
        "eligible_for_full_60kg_hexacopter_physical_validation": False,
        "flight_release_authorized": False,
        "external_evidence_issue": 16,
    }
