"""M26.29: review what a sourced DJI M300 flight dataset can and cannot prove.

A recorded DJI Matrice 300 flight cannot be promoted to exact-hardware
60 kg hexacopter validation. Source metadata and bytes can support *parser
testing* and limited source-specific exploration only after rights review.
"""
from __future__ import annotations

from collections.abc import Mapping

from physics.validation.zenodo_flight_candidate import DOI


def classify_m300_evidence_suitability(
    metadata_report: Mapping, *, acquisition_receipt: Mapping | None = None,
    source_csv_report: Mapping | None = None,
    reference_aircraft_type: str = "60 kg hexacopter",
) -> dict:
    if not isinstance(metadata_report, Mapping) or metadata_report.get("doi") != DOI:
        raise ValueError("known M300 source metadata preflight required")
    if not isinstance(reference_aircraft_type, str) or not reference_aircraft_type.strip():
        raise ValueError("explicit AeroForge reference vehicle identity required")
    actual_bytes = bool(
        isinstance(acquisition_receipt, Mapping)
        and acquisition_receipt.get("source_doi") == DOI
        and acquisition_receipt.get("provider_md5_matched") is True
        and isinstance(acquisition_receipt.get("computed_original_sha256"), str)
    )
    actual_csv = bool(
        actual_bytes and isinstance(source_csv_report, Mapping)
        and source_csv_report.get("source_doi") == DOI
        and source_csv_report.get("computed_original_sha256")
        == acquisition_receipt["computed_original_sha256"]
        and isinstance(source_csv_report.get("actual_original_column_names"), list)
        and source_csv_report.get("original_csv_record_count", 0) >= 5
    )
    published_aircraft = "DJI Matrice 300"
    name_matched = reference_aircraft_type.strip() == published_aircraft
    # Even a matching model string never authenticates serials, propulsion,
    # battery, controller, experiment conditions or independent blinding.
    incompatibilities = []
    if not name_matched:
        incompatibilities.append("aircraft_model")
    incompatibilities.extend([
        "installed_motor_propeller_esc_battery_revisions_not_verified",
        "propulsion_mount_and_mass_envelope_not_verified",
        "instrument_calibration_clock_and_conditions_not_verified",
        "original_physical_source_custody_not_independently_authenticated",
        "blind_frozen_model_and_holdout_not_verified",
    ])
    return {
        "status": (
            "M300_DATA_INSPECTED_FULL_VEHICLE_VALIDATION_INELIGIBLE"
            if actual_csv else "M300_SOURCE_METADATA_ONLY_PHYSICAL_VALIDATION_INELIGIBLE"
        ),
        "source_doi": DOI,
        "published_aircraft_type": published_aircraft,
        "aeroforge_reference_aircraft_type": reference_aircraft_type,
        "published_dataset_original_bytes_acquired_locally": actual_bytes,
        "published_source_csv_header_inspected": actual_csv,
        "known_hardware_and_experiment_evidence_gaps": incompatibilities,
        "eligible_for_source_specific_schema_test_if_rights_permit": actual_csv,
        "eligible_as_exact_60kg_reference_hexacopter_holdout": False,
        "eligible_for_unqualified_battery_motor_or_esc_model_validation": False,
        "independent_physical_evidence_decision_equivalence_established": False,
        "source_permission_and_license_independently_authenticated": False,
        "applicable_physical_flight_release_authorized": False,
    }
