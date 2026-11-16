"""All numerical observations in this file are SYNTHETIC software fixtures.

They are not independent measured flight-test or dyno validation evidence.
"""
import math

import pytest
from pydantic import ValidationError

from aeroforge_schemas.component import MotorSpec
from physics.propulsion.dataset import PowertrainDataset
from physics.validation.propulsion_evidence import (
    PropulsionEvidenceRequest, evaluate_propulsion_evidence,
)


def dataset():
    rows = []
    for voltage, rpms in [(10.0, [1000, 1200, 1400, 1600, 1800]),
                          (12.0, [1100, 1300, 1500, 1700, 1900])]:
        for index, rpm in enumerate(rpms):
            current = rpm / 1000.0 + voltage / 20.0
            rows.append({
                "throttle_pct": 50 + 12.5 * index, "voltage_v": voltage,
                "current_a": current, "power_w": current * voltage,
                "thrust_gf": rpm / 2.0, "rpm": rpm,
                "prop": "SYNTHETIC_PROP",
                "source": {"source": "synthetic mathematical bench fixture", "estimated": True},
            })
    m = MotorSpec.model_validate({
        "id": "fixture_motor", "name": "Synthetic motor", "source": {
            "source": "generated solely for numerical verification", "estimated": True},
        "test_data": rows,
    })
    return PowertrainDataset(m, "SYNTHETIC_PROP")


def payload(d=None):
    d = d or dataset()
    observations = []
    # Midpoint RPMs ensure these are NOT the calibrating knots, but still
    # synthetic: not a physical independent validation.
    for i, rpm in enumerate([1150, 1250, 1350, 1450, 1550, 1650]):
        v = 11.0
        observations.append({
            "id": f"synthetic_{i}", "rpm": rpm, "voltage_v": v,
            "thrust_gf": d.thrust_gf(rpm).value,
            "current_a": d.current_a(rpm, v).value,
        })
    return {
        "motor_id": "fixture_motor", "propeller_id": "fixture_prop", 
        "dataset_kind": "synthetic_fixture", "independent_run_id": "synthetic_run_B",
        "evidence_source": "synthetically generated from existing interpolator",
        "hardware_matches_selected_components": True, "unused_for_model_calibration": True,
        "predeclared_max_thrust_error_pct": 5,
        "predeclared_max_current_error_pct": 5,
        "observations": observations,
    }


def run(data=None,d=None):
    d = d or dataset()
    return evaluate_propulsion_evidence(d, PropulsionEvidenceRequest.model_validate(data or payload(d)))


def test_mathematics_recovers_synthetic_data_and_does_not_modify_bench_model():
    d = dataset()
    before = d.motor.model_dump_json()
    out = run(d=d)
    assert out["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
    assert out["evidence"]["all_samples_scored_and_tolerances_met"] is True
    assert out["evidence"]["thrust_metrics"]["mape_pct"] == pytest.approx(0)
    assert out["evidence"]["current_metrics"]["rmse_pct"] == pytest.approx(0)
    assert out["evidence"]["calibration_knot_operating_point_overlap_count"] == 0
    assert not out["simulation_modified"]
    assert d.motor.model_dump_json() == before


def test_fake_physical_label_cannot_authenticate_measurements():
    data = payload()
    data.update(dataset_kind="physical_measurements",
                test_fixture_description="user declared static thrust stand and instruments")
    assert run(data)["verdict"] == "REPORTED_HOLDOUT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"


def test_physical_measurements_require_fixture_provenance():
    data = payload()
    data["dataset_kind"] = "physical_measurements"
    with pytest.raises(ValueError, match="fixture"):
        run(data)


def test_calibration_data_is_not_independent_even_if_error_is_zero():
    data = payload()
    data.update(dataset_kind="physical_measurements",unused_for_model_calibration=False,
                test_fixture_description="bench A")
    assert run(data)["verdict"] == "CALIBRATION_DATA_NOT_INDEPENDENT_VALIDATION"


def test_hardware_mismatch_is_not_positive_evidence():
    data = payload()
    data.update(dataset_kind="physical_measurements",hardware_matches_selected_components=False,
                test_fixture_description="bench A")
    assert run(data)["verdict"] == "HARDWARE_MATCH_UNCONFIRMED"


def test_one_unsupported_row_invalidates_whole_run():
    data = payload()
    data.update(dataset_kind="physical_measurements",test_fixture_description="bench A")
    data["observations"][0]["rpm"] = 20000
    out = run(data)
    assert out["verdict"] == "OUTSIDE_SUPPORTED_MODEL_ENVELOPE"
    assert out["evidence"]["unsupported_count"] == 1
    assert out["evidence"]["scored_count"] == 5
    assert not out["evidence"]["all_samples_scored_and_tolerances_met"]


def test_biased_current_and_thrust_fail_predeclared_threshold():
    data = payload()
    data.update(dataset_kind="physical_measurements",test_fixture_description="bench A")
    data["observations"][4]["thrust_gf"] *= 1.30
    data["observations"][4]["current_a"] *= 1.30
    out = run(data)
    assert out["verdict"] == "REPORTED_HOLDOUT_TOLERANCES_NOT_MET"
    assert not out["evidence"]["current_metrics"]["threshold_met"]
    assert not out["evidence"]["thrust_metrics"]["threshold_met"]


def test_voltage_extrapolation_cannot_validate_physical_generalization():
    data = payload()
    data.update(dataset_kind="physical_measurements",test_fixture_description="bench A")
    for row in data["observations"]:
        row["voltage_v"] = 9.5
        row["current_a"] = dataset().current_a(row["rpm"], 9.5).value
    out = run(data)
    assert out["verdict"] == "VOLTAGE_EXTRAPOLATED_UNVALIDATED"


@pytest.mark.parametrize("change", [
    lambda v: v["observations"][0].update({"rpm": -2}),
    lambda v: v["observations"][0].update({"current_a": math.inf}),
    lambda v: v["observations"][0].update({"thrust_gf": 0}),
    lambda v: v["observations"][0].update({"id": v["observations"][1]["id"]}),
    lambda v: v["observations"].pop(),
    lambda v: v.update({"predeclared_max_current_error_pct": -5}),
    lambda v: v.update({"independent_run_id": "  "}),
    lambda v: v.update({"unknown_field": "ignored"}),
])
def test_bad_input_rejected(change):
    v = payload()
    change(v)
    with pytest.raises(ValidationError):
        PropulsionEvidenceRequest.model_validate(v)


def test_wrong_motor_id_refused():
    v = payload()
    v["motor_id"] = "different_motor"
    with pytest.raises(ValueError, match="motor ID"):
        run(v)


def test_outside_voltage_support_refused_without_extrapolation():
    v = payload()
    v.update(dataset_kind="physical_measurements", test_fixture_description="bench A")
    v["observations"][0]["voltage_v"] = 999
    out = run(v)
    assert out["evidence"]["unsupported_count"] == 1
    assert out["verdict"] == "OUTSIDE_SUPPORTED_MODEL_ENVELOPE"
