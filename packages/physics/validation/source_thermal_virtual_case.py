"""M29.9 directly recomputed original-source + thermal-geometry virtual case.

Runs strict SHA-256 comparison of supplied original ADC/prediction CSV bytes,
uses the M27.9 bounded affine sensor conversion, expands M28.10 rotor
geometry with M28.11 thermal bounds, and invokes M29.8 direct quantitative
critical decision gates. No user-provided pass/fail claims are accepted.
All physical provenance remains *unauthenticated*.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence

from aeroforge_schemas.design import DroneDesign
from physics.structures.thermal_rotor_clearance import apply_thermal_rotor_hard_bounds
from physics.validation.original_adc_sources import load_original_adc_sensor_case
from physics.validation.direct_virtual_case import audit_direct_virtual_case

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def audit_original_source_thermal_virtual_case(
    design: DroneDesign,
    *,
    frozen_model_git_sha: str,
    frozen_protocol_sha256: str,
    operating_envelope_id: str,
    operating_envelope_source: str,
    original_adc_sensor_case: Mapping,
    rotor_pair_motion_case: Mapping,
    thermal_case: Mapping,
    decision_thresholds: Sequence[Mapping],
) -> dict:
    """Re-evaluate original bytes, calibrated residuals, thermal gap and margins.

    Even a fully green software case CANNOT establish a worst-case model-form
    residual over unseen physical regimes without separately qualified data.
    """
    if not isinstance(frozen_model_git_sha, str) or not _SHA1.fullmatch(frozen_model_git_sha):
        raise ValueError("frozen_model_git_sha must be lowercase 40-hex")
    if not isinstance(frozen_protocol_sha256, str) or not _SHA256.fullmatch(frozen_protocol_sha256):
        raise ValueError("frozen_protocol_sha256 must be lowercase SHA-256")
    if not isinstance(original_adc_sensor_case, Mapping):
        raise ValueError("original_adc_sensor_case with primary original sources required")
    if original_adc_sensor_case.get("frozen_model_git_sha") != frozen_model_git_sha:
        raise ValueError("original ADC source and frozen model identity mismatch")
    if original_adc_sensor_case.get("frozen_protocol_sha256") != frozen_protocol_sha256:
        raise ValueError("original ADC source and frozen protocol identity mismatch")
    prepared, paired_digests = load_original_adc_sensor_case(**original_adc_sensor_case)
    expanded, thermal_increments = apply_thermal_rotor_hard_bounds(
        design, rotor_pair_motion_case=rotor_pair_motion_case, thermal_case=thermal_case
    )
    recomputed = audit_direct_virtual_case(
        design,
        frozen_model_git_sha=frozen_model_git_sha,
        frozen_protocol_sha256=frozen_protocol_sha256,
        operating_envelope_id=operating_envelope_id,
        operating_envelope_source=operating_envelope_source,
        sensor_case=prepared,
        rotor_pair_motion_case=expanded,
        decision_thresholds=decision_thresholds,
    )
    passed = recomputed["all_recomputed_operator_analytical_gates_passed"] is True
    source_info = {
        "design_name": design.name,
        "frozen_model_git_sha": frozen_model_git_sha,
        "frozen_protocol_sha256": frozen_protocol_sha256,
        "original_source_digest_links": paired_digests,
        "per_rotor_thermal_hard_error_increments": thermal_increments,
        "temperature_source_operator_supplied": thermal_case["thermal_environment_source"].strip(),
        "material_expansion_source_operator_supplied": thermal_case["material_expansion_source"].strip(),
        "arm_geometry_source_operator_supplied": thermal_case["arm_geometry_source"].strip(),
        "recomputed_case_digest_sha256": recomputed["canonical_operator_case_digest_sha256"],
    }
    digest = hashlib.sha256(json.dumps(
        source_info, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return {
        "status": (
            "DIRECTLY_RECOMPUTED_SOURCE_THERMAL_CASE_CONSISTENT_UNVERIFIED"
            if passed else "DIRECTLY_RECOMPUTED_SOURCE_THERMAL_CASE_BLOCKED"
        ),
        "combined_original_and_thermal_fingerprint_sha256": digest,
        "original_bytes_hashed_against_operator_sha256": True,
        "source_digests_checked": paired_digests,
        "per_rotor_thermal_hard_error_increments": thermal_increments,
        "recomputed_virtual_case": recomputed,
        "all_declared_analytical_gates_passed": passed,
        "independent_instrument_calibration_authenticated": False,
        "actual_measurement_acquisition_custody_authenticated": False,
        "real_thermal_and_dynamic_rotor_geometry_validated": False,
        "physical_simulation_decision_equivalence_established": False,
        "flight_or_manufacturing_release_authorized": False,
        "limitations": [
            "Original file hashes are matched against operator-supplied digests, not external signing authority",
            "Sensor coefficients, errors, material expansion, temperatures and full geometry bounds are not physically certified",
            "Observed holdout residual maximum is not a proven future-model worst-case hard error",
            "Unknown real hardware, independent test provenance and qualified flight safety approvals remain outstanding",
        ],
    }
