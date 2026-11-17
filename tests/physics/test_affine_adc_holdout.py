"""M27.9 synthetic ADC conversion tests; no actual calibrated physical recordings."""
from copy import deepcopy

import pytest
from physics.validation.affine_adc_holdout import audit_affine_sensor_holdouts


def fixture():
    return {
        "frozen_model_git_sha": "a"*40,
        "frozen_protocol_sha256": "b"*64,
        "channel": "battery_voltage_v",
        "calibration": {
            "scale_per_count": .01, "offset": 0.0,
            "scale_hard_error_per_count": .00001,
            "offset_hard_error": .01,
            "calibration_residual_hard_error": .02,
            "quantization_code_half_width": .5,
            "output_unit": "V",
            "minimum_valid_code": 1, "maximum_valid_code": 4094,
        },
        "calibration_source": "synthetic, not a certified instrument",
        "maximum_conservative_absolute_residual": .2,
        "minimum_interval_coverage_fraction": 1.,
        "holdout_runs": [
            {"run_id": f"synthetic_run_{k}", "group_id": f"synthetic_hardware_{k}",
             "samples": [
                {"sample_id":f"s{j}","time_s":j/10,
                 "raw_code":1000, "prediction":10.05,
                 "lower":9.8, "upper":10.2, "saturated":False}
                for j in range(5)]}
            for k in range(2)
        ],
    }


def run(payload=None):
    return audit_affine_sensor_holdouts(**(fixture() if payload is None else payload))


def test_calibration_hard_budget_includes_scale_offset_quantization_and_residual():
    body = fixture()
    old = deepcopy(body)
    r = run(body)
    assert body == old
    assert r["status"] == "REPORTED_ADC_CALIBRATED_HOLDOUTS_CONSISTENT_UNAUTHENTICATED"
    assert r["all_declared_holdout_analytical_gates_passed"]
    assert len(r["operator_report_digest_sha256"]) == 64
    sample = r["runs"][0]["sample_results"][0]
    u = 1000*.00001 + .01 + .02 + (.01+.00001)*.5
    assert sample["declared_conservative_measurement_hard_error"] == pytest.approx(u)
    assert sample["declared_conservative_prediction_abs_residual_upper"] == pytest.approx(.05+u)
    assert not r["actual_calibration_certificates_authenticated"]
    assert not r["raw_ADC_bytes_or_physical_recording_authenticated"]
    assert not r["independent_real_world_accuracy_validated"]
    assert not r["physical_release_authorized"]


def test_saturation_or_clipping_cannot_be_ignored():
    body = fixture()
    body["holdout_runs"][0]["samples"][0]["saturated"] = True
    r = run(body)
    assert r["status"] == "REPORTED_ADC_CALIBRATED_HOLDOUTS_REJECTED"
    assert not r["all_declared_holdout_analytical_gates_passed"]


def test_raw_adc_outside_declared_operating_range_is_rejected():
    body = fixture()
    body["holdout_runs"][0]["samples"][0]["raw_code"] = 4095
    with pytest.raises(ValueError, match="non-clipped"):
        run(body)


def test_large_declared_calibration_uncertainty_blocks_narrow_prediction_band():
    body = fixture()
    body["calibration"]["scale_hard_error_per_count"] = .001
    r = run(body)
    assert not r["all_declared_holdout_analytical_gates_passed"]


def test_incorrect_prediction_intervals_are_rejected():
    body = fixture()
    body["holdout_runs"][0]["samples"][0]["lower"] = 20
    with pytest.raises(ValueError, match="reversed"):
        run(body)


def test_group_reuse_cannot_count_as_independent_holdout():
    body = fixture()
    body["holdout_runs"][1]["group_id"] = body["holdout_runs"][0]["group_id"]
    with pytest.raises(ValueError, match="duplicate"):
        run(body)


def test_time_grid_and_raw_counts_are_strict():
    body = fixture()
    body["holdout_runs"][0]["samples"][1]["time_s"] = 0
    with pytest.raises(ValueError, match="strictly increase"):
        run(body)
    body = fixture()
    body["holdout_runs"][0]["samples"][1]["raw_code"] = 1000.0
    with pytest.raises(ValueError, match="integer"):
        run(body)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, 10**999])
def test_invalid_affine_hard_error_rejected(value):
    body = fixture()
    body["calibration"]["offset_hard_error"] = value
    with pytest.raises(ValueError, match="finite"):
        run(body)


def test_accumulated_calibration_overflow_refused():
    body = fixture()
    body["calibration"]["scale_hard_error_per_count"] = 1e308
    with pytest.raises(ValueError, match="overflow"):
        run(body)


def test_unauthenticated_source_claim_cannot_be_a_release_approval():
    body = fixture()
    body["calibration_source"] = "claimed external verification with no signature"
    r = run(body)
    assert r["all_declared_holdout_analytical_gates_passed"]
    assert not r["actual_calibration_certificates_authenticated"]
