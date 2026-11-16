"""M13 telemetry evidence: all input traces in these tests are SYNTHETIC.
They establish software correctness, NOT physical predictive accuracy.
"""
import copy
import pytest
from pydantic import ValidationError
from physics.validation.flight_evidence import FlightEvidenceRequest, evaluate_flight_evidence


def sim():
    return {
        "status": "completed",
        "mission": {"aborted": False},
        "success": {"reached_5m": True, "gentle_landing": True},
        "telemetry": {
            "t": [0.5 * i for i in range(21)],
            "z": [-1.0 * i for i in range(21)],
            "vz": [-2.0] * 21,
            "v_bus_v": [24.0 - .05 * i for i in range(21)],
            "motor_current_a": [[2.0, 3.0]] * 21,
        },
    }


def payload(kind="synthetic_fixture"):
    return {
        "dataset_kind": kind, "vehicle_id": "fixture_quad", "flight_log_id": "run-B",
        "log_source": "synthetic equations, not real measurements",
        "hardware_matches_simulated_design": True,
        "unused_for_model_calibration": True,
        "measurement_to_sim_time_offset_s": 0,
        "tolerances": {"altitude_m": 0.2, "bus_voltage_v": 0.1, "battery_current_a": 0.1},
        "observations": [
            {"t_s": t, "altitude_m": 2*t, "bus_voltage_v": 24-.1*t,
             "battery_current_a": 5.0}
            for t in (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)
        ],
    }


def compute(data=None, record=None, scenario="flight"):
    return evaluate_flight_evidence(record if record is not None else sim(),
                                   FlightEvidenceRequest.model_validate(data or payload()),
                                   simulation_id=7, design_id=3, scenario=scenario,
                                   saved_result_json='{"sealed":"prediction"}')


def test_exact_synthetic_flight_matches_including_ned_sign_and_battery_sum():
    out = compute()
    assert out["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
    assert out["all_predeclared_tolerances_met"] is True
    assert out["coverage"]["mission_fraction"] == pytest.approx(1)
    assert out["channels"]["altitude_m"]["metrics"]["rmse"] == pytest.approx(0)
    assert out["channels"]["battery_current_a"]["rows"][0]["predicted"] == pytest.approx(5)
    assert len(out["stored_prediction_sha256"]) == 64
    assert out["simulation_modified"] is False


def test_interpolation_and_explicit_time_offset():
    data = payload()
    data["measurement_to_sim_time_offset_s"] = .25
    data["observations"] = [
        {"t_s": t, "altitude_m": 2*(t+.25),
         "bus_voltage_v": 24-.1*(t+.25), "battery_current_a": 5}
        for t in (0, 1.5, 3.5, 5.5, 7.5, 9.5)
    ]
    record = sim()
    # Source prediction samples 0.5 s apart, enough for interpolation gate.
    record["telemetry"]["t"] = [i * .5 for i in range(21)]
    record["telemetry"]["z"] = [-i for i in range(21)]
    record["telemetry"]["vz"] = [-2.0] * 21
    record["telemetry"]["v_bus_v"] = [24 - .05 * i for i in range(21)]
    record["telemetry"]["motor_current_a"] = [[2, 3]] * 21
    out = compute(data, record)
    assert out["channels"]["altitude_m"]["metrics"]["rmse"] == pytest.approx(0)
    assert out["coverage"]["interpolation_supported"] is True


def test_physical_report_requires_declared_independence_and_hardware_match():
    data = payload("physical_measurements")
    assert compute(data)["verdict"] == "REPORTED_FLIGHT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"
    data["hardware_matches_simulated_design"] = False
    assert compute(data)["verdict"] == "UNCONFIRMED_HARDWARE_CONFIGURATION"
    data["hardware_matches_simulated_design"] = True
    data["unused_for_model_calibration"] = False
    assert compute(data)["verdict"] == "CALIBRATION_DATA_NOT_INDEPENDENT_VALIDATION"


def test_failure_and_mission_coverage_not_silently_passed():
    data = payload("physical_measurements")
    data["observations"] = data["observations"][:5]
    data["observations"][-1]["t_s"] = 7
    assert compute(data)["verdict"] == "INSUFFICIENT_FLIGHT_COVERAGE"
    data = payload("physical_measurements")
    data["observations"][0]["altitude_m"] += 1
    out = compute(data)
    assert out["verdict"] == "REPORTED_FLIGHT_ERROR_TOLERANCE_NOT_MET"
    assert not out["channels"]["altitude_m"]["metrics"]["meets_predeclared_tolerance"]


def test_interpolation_spacing_outside_limit_is_flagged():
    data = payload("physical_measurements")
    data["observations"] = [
        {"t_s": t + .1, "altitude_m": 2*(t+.1), "bus_voltage_v": 24-.1*(t+.1),
         "battery_current_a": 5} for t in (0., 1.5, 3.5, 5.5, 7.5, 9.5)
    ]
    record = sim()
    record["telemetry"]["t"] = [float(i) for i in range(11)]
    record["telemetry"]["z"] = [-2.0 * i for i in range(11)]
    record["telemetry"]["vz"] = [-2.0] * 11
    record["telemetry"]["v_bus_v"] = [24 - .1 * i for i in range(11)]
    record["telemetry"]["motor_current_a"] = [[2, 3]] * 11
    out = compute(data, record)
    assert out["verdict"] == "UNSUPPORTED_PREDICTION_SAMPLING_GAP"


def test_refuse_missing_channels_failed_run_and_times_outside_envelope():
    data = payload()
    data["observations"][-1]["t_s"] = 11.0
    with pytest.raises(ValueError, match="outside stored simulation"):
        compute(data)
    record = sim()
    record["status"] = "failed"
    with pytest.raises(ValueError, match="successful stored flight"):
        compute(record=record)
    record = sim()
    record["telemetry"].pop("motor_current_a")
    with pytest.raises(ValueError, match="lacks a consistent"):
        compute(record=record)
    with pytest.raises(ValueError, match="successful stored flight"):
        compute(scenario="hover-ideal")


@pytest.mark.parametrize("mutation", [
    lambda d: d.update({"vehicle_id": "   "}),
    lambda d: d.update({"flight_log_id": ""}),
    lambda d: d.update({"measurement_to_sim_time_offset_s": float("nan")}),
    lambda d: d["observations"][1].update({"t_s": 0}),
    lambda d: d["observations"][1].update({"altitude_m": float("inf")}),
    lambda d: d["observations"][1].update({"bus_voltage_v": -1}),
    lambda d: d["observations"][1].update({"battery_current_a": -1}),
    lambda d: d["tolerances"].update({"altitude_m": 0}),
    lambda d: d["tolerances"].update({"altitude_m": -1}),
    lambda d: d["tolerances"].update({"strange_channel": 1}),
    lambda d: d["tolerances"].pop("battery_current_a"),
    lambda d: (d["observations"].pop(), d["observations"].pop()),
    lambda d: d["observations"][0].update({"altitude_m": None,
                                            "bus_voltage_v": None,
                                            "battery_current_a": None}),
])
def test_invalid_log_rejected(mutation):
    data = payload()
    mutation(data)
    with pytest.raises(ValidationError):
        FlightEvidenceRequest.model_validate(data)


def test_request_never_mutates_original_simulation_or_observations():
    record = sim()
    data = payload()
    prior = copy.deepcopy((record, data))
    compute(data, record)
    assert (record, data) == prior


def test_abort_or_failed_mission_never_gets_positive_physical_verdict():
    data = payload("physical_measurements")
    record = sim()
    record["mission"]["aborted"] = True
    out = compute(data, record)
    assert out["verdict"] == "SIMULATED_MISSION_FAILED_OR_ABORTED"
    assert out["simulated_mission_succeeded"] is False
    record = sim()
    record["success"]["gentle_landing"] = False
    assert compute(data, record)["verdict"] == "SIMULATED_MISSION_FAILED_OR_ABORTED"
    record = sim()
    record.pop("success")
    with pytest.raises(ValueError, match="lacks mission outcome"):
        compute(data, record)
