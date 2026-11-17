"""M29.9 primary-source-to-thermal-to-decision tests, synthetic only."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.validation.source_thermal_virtual_case import audit_original_source_thermal_virtual_case

ROOT = Path(__file__).resolve().parents[2]


def design():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def fixture():
    records = []
    for k in range(2):
        obs = ["sample_id,t_s,raw_code,saturated"]
        pred = ["sample_id,t_s,prediction,lower,upper"]
        for j in range(5):
            obs.append(f"s{j},{j/10:.1f},{1000+k},0")
            pred.append(f"s{j},{j/10:.1f},{10.05 + k*.01:.2f},9.7,10.3")
        raw = "\n".join(obs) + "\n"
        frozen = "\n".join(pred) + "\n"
        records.append({
            "run_id": f"run{k}", "group_id": f"distinct_synthetic_group{k}",
            "original_adc_csv": raw, "original_adc_sha256": sha256(raw.encode()).hexdigest(),
            "frozen_prediction_csv": frozen,
            "frozen_prediction_sha256": sha256(frozen.encode()).hexdigest(),
        })
    centers = [list(rotor.position_m) for rotor in design().rotors]
    return {
        "frozen_model_git_sha": "a"*40,
        "frozen_protocol_sha256": "b"*64,
        "operating_envelope_id": "synthetic_hover",
        "operating_envelope_source": "hypothetical test envelope, not real flight",
        "original_adc_sensor_case": {
            "frozen_model_git_sha": "a"*40,
            "frozen_protocol_sha256": "b"*64,
            "channel": "battery_voltage_v",
            "calibration": {
                "scale_per_count": .01, "offset": 0.,
                "scale_hard_error_per_count": .00001, "offset_hard_error": .01,
                "calibration_residual_hard_error": .02,
                "quantization_code_half_width": .5,
                "minimum_valid_code": 1, "maximum_valid_code": 4094,
                "output_unit": "V",
            },
            "calibration_source": "synthetic ADC calibration not verified",
            "maximum_conservative_absolute_residual": .2,
            "minimum_interval_coverage_fraction": 1.,
            "source_runs": records,
        },
        "rotor_pair_motion_case": {
            "installed_rotor_diameters_m": [.381]*4,
            "maximum_swept_heights_m": [.02]*4,
            "diameter_hard_bounds_m": [0]*4,
            "center_position_hard_bounds_m": [0]*4,
            "center_speed_hard_bounds_m_per_s": [0]*4,
            "time_samples": [
                {"time_s": 0, "rotor_centers_m": deepcopy(centers)},
                {"time_s": 1, "rotor_centers_m": deepcopy(centers)},
            ],
            "minimum_declared_pair_gap_m": .01,
            "trajectory_source": "synthetic fixed rotor test",
            "geometry_hard_bound_source": "synthetic unmeasured rotor dimensions",
            "rotor_center_speed_source": "hypothetical bounded rotor center motion",
        },
        "thermal_case": {
            "temperature_excursion_hard_bounds_k": [20]*4,
            "diameter_abs_expansion_coeff_upper_per_k": [.0001]*4,
            "height_abs_expansion_coeff_upper_per_k": [.0001]*4,
            "arm_length_m": [.25]*4,
            "arm_abs_expansion_coeff_upper_per_k": [.0001]*4,
            "thermal_environment_source": "unverified max temperature excursion",
            "material_expansion_source": "unverified material CTE",
            "arm_geometry_source": "nominal unmeasured arm lengths",
        },
        "decision_thresholds": [{
            "decision_id": "battery_voltage_maximum",
            "channel": "battery_voltage_v", "metric_unit": "V",
            "failure_direction": "exceed_max", "predicted_value": 10.05,
            "failure_limit": 11.,
            "additional_model_form_hard_bound": .05,
            "numerical_hard_bound": .02, "input_hard_bound": .01,
            "geometry_hard_bound": .01,
            "threshold_source": "synthetic threshold, not certified physical limit",
        }],
    }


def run(payload=None):
    return audit_original_source_thermal_virtual_case(
        design(), **(fixture() if payload is None else payload)
    )


def test_recomputed_original_hashes_thermal_bounds_and_margins_not_real_evidence():
    payload = fixture()
    original = deepcopy(payload)
    result = run(payload)
    assert payload == original
    assert result["status"] == "DIRECTLY_RECOMPUTED_SOURCE_THERMAL_CASE_CONSISTENT_UNVERIFIED"
    assert result["all_declared_analytical_gates_passed"]
    assert result["original_bytes_hashed_against_operator_sha256"]
    assert len(result["source_digests_checked"]) == 2
    assert len(result["per_rotor_thermal_hard_error_increments"]) == 4
    assert result["recomputed_virtual_case"]["calibration_inclusive_holdout_report"]["all_declared_holdout_analytical_gates_passed"]
    assert result["recomputed_virtual_case"]["continuous_rotor_pair_geometry_report"]["analytical_screen_passed"]
    assert len(result["combined_original_and_thermal_fingerprint_sha256"]) == 64
    assert not result["independent_instrument_calibration_authenticated"]
    assert not result["actual_measurement_acquisition_custody_authenticated"]
    assert not result["real_thermal_and_dynamic_rotor_geometry_validated"]
    assert not result["physical_simulation_decision_equivalence_established"]
    assert not result["flight_or_manufacturing_release_authorized"]


def test_original_adc_tampering_fails_before_any_approvals():
    data = fixture()
    data["original_adc_sensor_case"]["source_runs"][0]["original_adc_csv"] += " "
    with pytest.raises(ValueError, match="digest mismatch"):
        run(data)


def test_original_reported_saturation_blocks_cross_domain_analytic_verdict():
    data = fixture()
    file = data["original_adc_sensor_case"]["source_runs"][0]
    file["original_adc_csv"] = file["original_adc_csv"].replace("1000,0", "1000,1", 1)
    file["original_adc_sha256"] = sha256(file["original_adc_csv"].encode()).hexdigest()
    result = run(data)
    assert result["status"] == "DIRECTLY_RECOMPUTED_SOURCE_THERMAL_CASE_BLOCKED"


def test_large_declared_heat_expansion_blocks_rotor_separation():
    data = fixture()
    data["thermal_case"]["diameter_abs_expansion_coeff_upper_per_k"] = [.1]*4
    result = run(data)
    assert not result["all_declared_analytical_gates_passed"]
    assert not result["recomputed_virtual_case"]["continuous_rotor_pair_geometry_report"]["analytical_screen_passed"]


def test_hard_decision_margin_failure_cannot_be_hidden_by_sensor_geometry_passes():
    data = fixture()
    data["decision_thresholds"][0]["failure_limit"] = 10.05
    result = run(data)
    assert result["status"] == "DIRECTLY_RECOMPUTED_SOURCE_THERMAL_CASE_BLOCKED"
    assert not result["recomputed_virtual_case"]["decision_margins"][0]["declared_analytical_decision_margin_passed"]


def test_unit_mismatch_between_adc_output_and_failure_threshold_rejected():
    data = fixture()
    data["decision_thresholds"][0]["metric_unit"] = "A"
    with pytest.raises(ValueError, match="channel/unit"):
        run(data)


def test_model_or_protocol_identifier_drift_is_rejected():
    data = fixture()
    data["original_adc_sensor_case"]["frozen_protocol_sha256"] = "c"*64
    with pytest.raises(ValueError, match="frozen protocol identity mismatch"):
        run(data)


def test_changing_thermal_source_changes_canonical_evidence_fingerprint():
    data = fixture()
    first = run(data)
    data["thermal_case"]["material_expansion_source"] = "another unverified material reference"
    second = run(data)
    assert first["combined_original_and_thermal_fingerprint_sha256"] != second["combined_original_and_thermal_fingerprint_sha256"]


def test_unknown_thermal_approval_claim_is_rejected():
    data = fixture()
    data["thermal_case"]["independent_flight_certification"] = True
    with pytest.raises(ValueError, match="exact independent thermal"):
        run(data)
