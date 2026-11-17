"""M29.8 synthetic direct recomputation is not actual aircraft validation."""
from copy import deepcopy
from pathlib import Path

import pytest
from aeroforge_schemas.design import DroneDesign
from physics.validation.direct_virtual_case import audit_direct_virtual_case

ROOT=Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT/"data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def fixture():
    centers=[list(r.position_m) for r in reference().rotors]
    sensor={
        "frozen_model_git_sha":"a"*40,"frozen_protocol_sha256":"b"*64,
        "channel":"battery_voltage_v",
        "calibration":{
            "scale_per_count":.01,"offset":0.,
            "scale_hard_error_per_count":.00001,
            "offset_hard_error":.01,
            "calibration_residual_hard_error":.02,
            "quantization_code_half_width":.5,
            "output_unit":"V",
            "minimum_valid_code":1,
            "maximum_valid_code":4094,
        },
        "calibration_source":"unverified hypothetical ADC calibration",
        "maximum_conservative_absolute_residual":.2,
        "minimum_interval_coverage_fraction":1.,
        "holdout_runs":[
            {"run_id":f"run{k}","group_id":f"separate_group{k}",
             "samples":[
                 {"sample_id":f"s{j}","time_s":j/10,
                  "raw_code":1000,"prediction":10.05,
                  "lower":9.8,"upper":10.2,"saturated":False}
                 for j in range(5)]}
            for k in range(2)
        ],
    }
    rotor={
        "installed_rotor_diameters_m":[.381]*4,
        "maximum_swept_heights_m":[.02]*4,
        "diameter_hard_bounds_m":[0]*4,
        "center_position_hard_bounds_m":[0]*4,
        "center_speed_hard_bounds_m_per_s":[0]*4,
        "time_samples":[
            {"time_s":0,"rotor_centers_m":deepcopy(centers)},
            {"time_s":1,"rotor_centers_m":deepcopy(centers)},
        ],
        "minimum_declared_pair_gap_m":.01,
        "trajectory_source":"synthetic unmeasured rotor trajectory",
        "geometry_hard_bound_source":"hypothetical worst case swept shape",
        "rotor_center_speed_source":"unverified zero center motion",
    }
    return {
        "frozen_model_git_sha":"a"*40,
        "frozen_protocol_sha256":"b"*64,
        "operating_envelope_id":"synthetic_hover_envelope",
        "operating_envelope_source":"unverified synthetic fixture",
        "sensor_case":sensor,
        "rotor_pair_motion_case":rotor,
        "decision_thresholds":[
            {
                "decision_id":"maximum_voltage",
                "failure_direction":"exceed_max",
                "predicted_value":10.05,"failure_limit":11.,
                "additional_model_form_hard_bound":.05,
                "numerical_hard_bound":.02,
                "input_hard_bound":.01,
                "geometry_hard_bound":.01,
                "threshold_source":"synthetic limit, not physical rating",
            },
            {
                "decision_id":"minimum_voltage",
                "failure_direction":"fall_below_min",
                "predicted_value":10.05,"failure_limit":9.,
                "additional_model_form_hard_bound":.05,
                "numerical_hard_bound":.02,
                "input_hard_bound":.01,
                "geometry_hard_bound":.01,
                "threshold_source":"synthetic limit, not physical rating",
            },
        ],
    }


def audit(payload=None):
    return audit_direct_virtual_case(reference(), **(fixture() if payload is None else payload))


def test_all_three_engines_recomputed_and_no_physical_release_claim():
    req=fixture()
    old=deepcopy(req)
    report=audit(req)
    assert req==old
    assert report["status"]=="DIRECTLY_RECOMPUTED_VIRTUAL_CASE_CONSISTENT_UNVERIFIED"
    assert report["all_recomputed_operator_analytical_gates_passed"]
    assert report["calibration_inclusive_holdout_report"]["all_declared_holdout_analytical_gates_passed"]
    assert report["continuous_rotor_pair_geometry_report"]["analytical_screen_passed"]
    assert all(x["declared_analytical_decision_margin_passed"] for x in report["decision_margins"])
    assert len(report["canonical_operator_case_digest_sha256"])==64
    assert not report["physical_sensor_and_calibration_sources_authenticated"]
    assert not report["real_as_built_dynamic_geometry_validated"]
    assert not report["unseen_scenarios_decision_equivalence_established"]
    assert not report["flight_or_manufacturing_release_authorized"]


def test_hardware_saturation_blocks_green_sensor_gate():
    req=fixture()
    req["sensor_case"]["holdout_runs"][0]["samples"][0]["saturated"]=True
    report=audit(req)
    assert report["status"]=="DIRECTLY_RECOMPUTED_VIRTUAL_CASE_BLOCKED"


def test_large_rotor_motion_bound_blocks_continuous_3d_clearance():
    req=fixture()
    req["rotor_pair_motion_case"]["center_speed_hard_bounds_m_per_s"]=[1]*4
    report=audit(req)
    assert not report["all_recomputed_operator_analytical_gates_passed"]


def test_insufficient_threshold_margin_blocks_all_software_conclusions():
    req=fixture()
    req["decision_thresholds"][0]["failure_limit"]=10.05
    report=audit(req)
    assert report["status"]=="DIRECTLY_RECOMPUTED_VIRTUAL_CASE_BLOCKED"
    assert not next(x for x in report["decision_margins"] if x["decision_id"]=="maximum_voltage")["declared_analytical_decision_margin_passed"]


def test_frozen_protocol_identity_mismatch_is_an_error():
    req=fixture()
    req["sensor_case"]["frozen_protocol_sha256"]="c"*64
    with pytest.raises(ValueError,match="identity mismatch"):
        audit(req)


def test_duplicate_threshold_or_unbounded_error_rejected():
    req=fixture()
    req["decision_thresholds"][1]["decision_id"]="maximum_voltage"
    with pytest.raises(ValueError,match="duplicated decision"):
        audit(req)
    req=fixture()
    req["decision_thresholds"][0]["numerical_hard_bound"]=float("nan")
    with pytest.raises(ValueError,match="finite"):
        audit(req)


def test_hard_error_budget_overflow_cannot_silently_authorize():
    req=fixture()
    for key in (
        "additional_model_form_hard_bound","numerical_hard_bound",
        "input_hard_bound","geometry_hard_bound",
    ):
        req["decision_thresholds"][0][key]=1e308
    with pytest.raises(ValueError,match="overflow"):
        audit(req)


def test_fabricated_release_approval_as_extra_field_fails_closed():
    req=fixture()
    req["decision_thresholds"][0]["physically_certified"]=True
    with pytest.raises(ValueError,match="exact failure threshold"):
        audit(req)
