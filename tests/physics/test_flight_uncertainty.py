"""M14 conservative observation/clock uncertainty: SYNTHETIC verification only."""
import copy

import pytest
from pydantic import ValidationError

from physics.validation.flight_evidence import FlightEvidenceRequest, evaluate_flight_evidence


def _simulation():
    return {
        "status": "completed", "mission": {"aborted": False},
        "success": {"mission_completed": True},
        "telemetry": {
            "t": [i * .25 for i in range(41)],
            "z": [-2 * (i * .25) for i in range(41)],
            "vz": [-2.] * 41,
            "v_bus_v": [24 - .1 * (i * .25) for i in range(41)],
            "motor_current_a": [[3., 2.]] * 41,
        },
    }


def _request(physical=True, error=0., tolerance=.3, clock=0.):
    return {
        "dataset_kind": "physical_measurements" if physical else "synthetic_fixture",
        "vehicle_id": "synthetic_quad", "flight_log_id": "held_out_B",
        "log_source": "synthetic equations only, NOT physical measurements",
        "hardware_matches_simulated_design": True,
        "unused_for_model_calibration": True,
        "measurement_to_sim_time_offset_s": 0,
        "tolerances": {"altitude_m": tolerance},
        "observations": [
            {"t_s": t, "altitude_m": 2*t + error}
            for t in (0., 2., 4., 6., 8., 10.)
        ],
        "measurement_error_bounds": {"altitude_m": .1},
        "clock_error_bound_s": clock,
    }


def _evaluate(req, sim=None):
    return evaluate_flight_evidence(
        sim or _simulation(), FlightEvidenceRequest.model_validate(req),
        simulation_id=13, design_id=4, scenario="flight",
        saved_result_json='{"immutable":true}',
    )


def test_within_declared_hard_bounds_passes_but_is_not_certification():
    data = _request(error=.03)
    outcome = _evaluate(data)
    a = outcome["uncertainty_assessment"]
    assert a["status"] == "ROBUST_PASS_UNDER_DECLARED_BOUNDS"
    assert a["independently_authenticated"] is False
    assert outcome["verdict"] == "REPORTED_FLIGHT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"
    assert a["channels"]["altitude_m"]["rows"][0]["maximum_possible_absolute_error"] == pytest.approx(.13)


def test_declaration_can_make_pointwise_pass_indeterminate():
    data = _request(error=.2, tolerance=.25)
    result = _evaluate(data)
    assert result["all_predeclared_tolerances_met"] is True
    assert result["uncertainty_assessment"]["status"] == "INDETERMINATE_UNDER_DECLARED_BOUNDS"
    assert result["verdict"] == "UNCERTAINTY_AWARE_TOLERANCE_NOT_DEMONSTRATED"


def test_definite_failure_when_lower_bound_exceeds_tolerance():
    data = _request(error=1., tolerance=.2)
    result = _evaluate(data)
    assert result["uncertainty_assessment"]["status"] == "ROBUST_FAIL_UNDER_DECLARED_BOUNDS"
    assert result["uncertainty_assessment"]["channels"]["altitude_m"]["any_robust_failure"]


def test_clock_error_near_endpoint_never_clips_to_fake_pass():
    data = _request(error=0., tolerance=1., clock=.1)
    out = _evaluate(data)
    assert out["uncertainty_assessment"]["status"] == "INDETERMINATE_UNDER_DECLARED_BOUNDS"
    assert out["uncertainty_assessment"]["channels"]["altitude_m"]["rows"][0]["disposition"] == "CLOCK_ENVELOPE_UNSUPPORTED"
    assert out["verdict"] == "UNCERTAINTY_AWARE_TOLERANCE_NOT_DEMONSTRATED"


def test_clock_error_accounts_for_actual_prediction_slope():
    data = _request(error=0., tolerance=.35, clock=.1)
    data["observations"] = [
        {"t_s": t, "altitude_m": 2*t} for t in (1., 2., 4., 6., 8., 9.)
    ]
    out = _evaluate(data)
    assert out["uncertainty_assessment"]["status"] == "ROBUST_PASS_UNDER_DECLARED_BOUNDS"
    row = out["uncertainty_assessment"]["channels"]["altitude_m"]["rows"][0]
    assert row["conservative_error_bound"] == pytest.approx(.3)
    assert row["maximum_possible_absolute_error"] == pytest.approx(.3)


def test_legacy_request_without_uncertainty_preserved():
    data = _request()
    del data["measurement_error_bounds"]
    del data["clock_error_bound_s"]
    result = _evaluate(data)
    assert result["uncertainty_assessment"]["status"] == "NOT_REQUESTED"
    assert result["verdict"] == "REPORTED_FLIGHT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"


@pytest.mark.parametrize("change", [
    lambda d: d.update({"measurement_error_bounds": {"altitude_m": -1}}),
    lambda d: d.update({"measurement_error_bounds": {"altitude_m": float("nan")}}),
    lambda d: d.update({"measurement_error_bounds": {"other": 1}}),
    lambda d: d.update({"measurement_error_bounds": {}}),
    lambda d: d.update({"clock_error_bound_s": -1}),
    lambda d: d.update({"clock_error_bound_s": float("inf")}),
    lambda d: (d.update({"measurement_error_bounds": None}),
               d.update({"clock_error_bound_s": .1})),
])
def test_bad_uncertainty_declarations_rejected(change):
    data = _request()
    change(data)
    with pytest.raises(ValidationError):
        FlightEvidenceRequest.model_validate(data)


def test_comparison_is_read_only():
    data = _request()
    sim = _simulation()
    baseline = copy.deepcopy((data, sim))
    _evaluate(data, sim)
    assert (data, sim) == baseline


def test_synthetic_inputs_never_count_as_physical_validation_even_with_bounds():
    result = _evaluate(_request(physical=False))
    assert result["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
