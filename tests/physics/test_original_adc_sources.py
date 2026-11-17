"""M27.10 exact-byte original ADC source tests are synthetic, not real data."""
from copy import deepcopy
from hashlib import sha256
import pytest

from physics.validation.original_adc_sources import audit_original_adc_holdout_sources, load_original_adc_sensor_case


def fixture():
    runs = []
    for k in range(2):
        obs = ["sample_id,t_s,raw_code,saturated"]
        pred = ["sample_id,t_s,prediction,lower,upper"]
        for j in range(5):
            t = j / 10
            obs.append(f"s{j},{t:.1f},{1000+k},0")
            pred.append(f"s{j},{t:.1f},{10.05 + k*.01:.2f},9.7,10.3")
        o, p = "\n".join(obs) + "\n", "\n".join(pred) + "\n"
        runs.append({
            "run_id": f"run{k}", "group_id": f"synthetic_group{k}",
            "original_adc_csv": o,
            "original_adc_sha256": sha256(o.encode()).hexdigest(),
            "frozen_prediction_csv": p,
            "frozen_prediction_sha256": sha256(p.encode()).hexdigest(),
        })
    return dict(
        frozen_model_git_sha="a"*40, frozen_protocol_sha256="b"*64,
        channel="battery_voltage_v", calibration={
            "scale_per_count": .01, "offset": 0.,
            "scale_hard_error_per_count": .00001, "offset_hard_error": .01,
            "calibration_residual_hard_error": .02, "quantization_code_half_width": .5,
            "minimum_valid_code": 1, "maximum_valid_code": 4094, "output_unit": "V",
        },
        calibration_source="synthetic coefficients, not independently calibrated",
        maximum_conservative_absolute_residual=.2,
        minimum_interval_coverage_fraction=1.,
        source_runs=runs,
    )


def run(payload=None):
    return audit_original_adc_holdout_sources(**(fixture() if payload is None else payload))


def test_original_hashes_and_heldouts_numerically_consistent_not_real():
    req = fixture()
    old = deepcopy(req)
    result = run(req)
    assert req == old
    assert result["status"] == "ORIGINAL_ADC_SOURCES_MATCH_OPERATOR_HASHES_NUMERICALLY_CONSISTENT_UNAUTHENTICATED"
    assert result["original_bytes_hashed_against_supplied_sha256"]
    assert len(result["source_digests_checked"]) == 2
    assert result["calibrated_holdout_report"]["all_declared_holdout_analytical_gates_passed"]
    assert not result["independent_source_custody_authenticated"]
    assert not result["physical_instrument_calibration_authenticated"]
    assert not result["independent_real_world_prediction_validated"]
    assert not result["manufacturing_or_flight_release_authorized"]


def test_parsed_case_is_compatible_with_source_verification_engine():
    prepared, digests = load_original_adc_sensor_case(**fixture())
    assert len(digests) == 2
    assert prepared["holdout_runs"][0]["samples"][0]["raw_code"] == 1000
    assert prepared["holdout_runs"][0]["samples"][0]["time_s"] == 0.
    assert prepared["calibration"]["output_unit"] == "V"


def test_single_byte_tamper_rejected():
    req = fixture()
    req["source_runs"][0]["original_adc_csv"] += " "
    with pytest.raises(ValueError, match="digest mismatch"):
        run(req)


def test_changed_predictor_bytes_must_match_original_sha():
    req = fixture()
    req["source_runs"][0]["frozen_prediction_csv"] = req["source_runs"][0]["frozen_prediction_csv"].replace("10.05", "10.06", 1)
    with pytest.raises(ValueError, match="digest mismatch"):
        run(req)


def test_source_time_grid_requires_exact_original_ids_and_times():
    req = fixture()
    entry = req["source_runs"][0]
    entry["frozen_prediction_csv"] = entry["frozen_prediction_csv"].replace("s1,0.1", "s1,0.15")
    entry["frozen_prediction_sha256"] = sha256(entry["frozen_prediction_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="time grids differ"):
        run(req)


def test_raw_adc_does_not_accept_fraction_or_scientific_notation():
    req = fixture()
    entry = req["source_runs"][0]
    entry["original_adc_csv"] = entry["original_adc_csv"].replace("1000,0", "1e3,0", 1)
    entry["original_adc_sha256"] = sha256(entry["original_adc_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="unsigned integer"):
        run(req)


def test_saturated_original_sample_blocks_positive_gate():
    req = fixture()
    entry = req["source_runs"][0]
    entry["original_adc_csv"] = entry["original_adc_csv"].replace("1000,0", "1000,1", 1)
    entry["original_adc_sha256"] = sha256(entry["original_adc_csv"].encode()).hexdigest()
    r = run(req)
    assert r["status"] == "ORIGINAL_ADC_SOURCE_NUMERIC_GATE_FAILED"


def test_reused_original_files_cannot_count_as_another_run():
    req = fixture()
    req["source_runs"][1]["original_adc_csv"] = req["source_runs"][0]["original_adc_csv"]
    req["source_runs"][1]["original_adc_sha256"] = req["source_runs"][0]["original_adc_sha256"]
    with pytest.raises(ValueError, match="duplicate or reused"):
        run(req)


def test_unknown_fields_and_invalid_original_headers_rejected():
    req = fixture()
    req["source_runs"][0]["claimed_physical_proof"] = True
    with pytest.raises(ValueError, match="exact IDs"):
        run(req)
    req = fixture()
    entry = req["source_runs"][0]
    entry["original_adc_csv"] = entry["original_adc_csv"].replace("raw_code", "current_code", 1)
    entry["original_adc_sha256"] = sha256(entry["original_adc_csv"].encode()).hexdigest()
    with pytest.raises(ValueError, match="exact CSV header"):
        run(req)
