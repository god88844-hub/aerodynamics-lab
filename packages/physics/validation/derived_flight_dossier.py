"""M26.24: consolidated derived-observation decision with hardware gate.

FAIL dominates missing samples. This is a conditional software dossier; the
origin, installation, clocks, instrument calibration and legal flight are
externally unresolved even when all claimed numeric and hardware gates pass.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from physics.validation.derived_hardware_screen import screen_declared_hardware_match
from physics.validation.derived_holdout_coverage import audit_derived_holdout_group_coverage


def build_derived_flight_dossier(root, manifest, *, holdout_case: Mapping,
                                 comparison_cases: Sequence[Mapping],
                                 reference_hardware: Mapping,
                                 measured_hardware: Mapping,
                                 maximum_predeclared_mass_fraction_difference: float,
                                 declared_ambient_min_c: float, declared_ambient_max_c: float,
                                 required_regime: str, required_channel: str,
                                 minimum_distinct_holdout_groups: int = 2) -> dict:
    hardware = screen_declared_hardware_match(
        reference_hardware, measured_hardware,
        maximum_predeclared_mass_fraction_difference=maximum_predeclared_mass_fraction_difference,
        declared_ambient_min_c=declared_ambient_min_c,
        declared_ambient_max_c=declared_ambient_max_c,
    )
    # Incompatible actual hardware is not a numerically "passing" validation,
    # but still recompute every provided comparison to reveal hard failures.
    coverage = audit_derived_holdout_group_coverage(
        root, manifest, holdout_case=holdout_case,
        comparison_cases=comparison_cases,
        required_regime=required_regime, required_channel=required_channel,
        minimum_distinct_holdout_groups=minimum_distinct_holdout_groups,
    )
    failed = coverage["status"].startswith("FAIL_")
    if failed:
        status = "FAIL_RECOMPUTED_DERIVED_CRITICAL_METRIC"
    elif not hardware["eligible_for_conditional_numerical_screen"]:
        status = "INCONCLUSIVE_INCOMPATIBLE_DECLARED_HARDWARE"
    elif not coverage["all_numeric_checks_passed"]:
        status = "INCONCLUSIVE_DERIVED_HOLDOUT_COVERAGE"
    else:
        status = "CONDITIONAL_DERIVED_NUMERICAL_CONSISTENCY_EXTERNAL_EVIDENCE_MISSING"
    canonical = {
        "regime": required_regime,
        "channel": required_channel,
        "hardware_mismatch": hardware["operator_declared_hardware_fields_mismatched"],
        "relative_mass_error": hardware["relative_takeoff_mass_difference"],
        "declared_mass_tolerance": hardware["declared_mass_tolerance_fraction"],
        "ambient_range": hardware["declared_ambient_range_c"],
        "ambient_value": hardware["operator_measured_ambient_c"],
        "split": coverage["canonical_split_sha256"],
        "comparisons": [
            {k: row[k] for k in (
                "flight_id", "original_source_sha256", "conversion_spec_sha256",
                "derived_csv_sha256", "frozen_prediction_sha256",
                "operator_declared_numerical_gate_passed", "max_conservative_residual",
            )}
            for row in coverage["comparison_reports"]
        ],
        "status": status,
    }
    return {
        "status": status,
        "recomputed_dossier_sha256": sha256(json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest(),
        "hardware_compatibility_screen": hardware,
        "whole_flight_derived_coverage": coverage,
        "source_data_classification": "derived_from_vendor_original_not_original_instrument_bytes",
        "critical_metric_failure_overrides_missing_hardware_evidence": failed,
        "source_license_and_original_custody_authenticated": False,
        "installed_hardware_serials_and_calibration_authenticated": False,
        "historical_blind_holdout_authenticated": False,
        "decision_equivalent_physical_evidence_established": False,
        "manufacturing_or_flight_release_authorized": False,
        "unresolved_physical_evidence_issue": 16,
    }
