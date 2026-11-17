"""M27.6 clock uncertainty tests use synthetic numbers, not independent recordings."""
from copy import deepcopy

import pytest

from physics.validation.clock_residual_bounds import audit_clock_bounded_residuals


def fixture():
    return {
        "model_git_sha": "a"*40,
        "protocol_sha256": "b"*64,
        "channel": "voltage_v",
        "absolute_error_tolerance": .3,
        "minimum_coverage_fraction": 1.,
        "measurement_source": "synthetic",
        "clock_bound_source": "hypothetical absolute clock error",
        "slew_bound_source": "hypothetical maximum voltage rate",
        "samples": [
            {
                "sample_id": f"s{i}", "time_s": i*.1,
                "prediction": 10., "observed": 10.1,
                "measurement_hard_bound": .05,
                "clock_time_hard_bound_s": .02,
                "signal_slew_hard_bound_per_s": 2.,
            } for i in range(5)
        ],
    }


def test_slew_times_clock_plus_sensor_bound_and_no_physical_certification():
    req = fixture()
    old = deepcopy(req)
    r = audit_clock_bounded_residuals(**req)
    assert req == old
    assert r["sample_count"] == 5
    assert r["worst_conservative_absolute_residual_upper"] == pytest.approx(.19)
    assert r["metric_analytical_gate_passed"]
    assert r["conservative_coverage_fraction"] == 1
    assert not r["clock_hard_bounds_independently_verified"]
    assert not r["signal_slew_bounds_independently_verified"]
    assert not r["independent_real_world_prediction_validated"]
    assert not r["flight_release_authorized"]


def test_large_clock_uncertainty_blocks_declared_error_gate():
    req = fixture()
    for item in req["samples"]:
        item["clock_time_hard_bound_s"] = .2
    r = audit_clock_bounded_residuals(**req)
    assert r["status"] == "REPORTED_CLOCK_BOUNDED_RESIDUAL_GATE_FAILED"
    assert not r["metric_analytical_gate_passed"]


def test_coverage_is_per_sample_not_reused_as_future_success_probability():
    req = fixture()
    req["samples"][0]["observed"] = 10.5
    req["minimum_coverage_fraction"] = .8
    r = audit_clock_bounded_residuals(**req)
    assert r["conservative_coverage_fraction"] == .8
    assert r["metric_analytical_gate_passed"]
    assert not r["independent_real_world_prediction_validated"]


@pytest.mark.parametrize("key,bad", [
    ("clock_time_hard_bound_s", -1), ("measurement_hard_bound", float("nan")),
    ("signal_slew_hard_bound_per_s", float("inf")),
    ("clock_time_hard_bound_s", True),
])
def test_nonfinite_or_unknown_hard_limits_refused(key, bad):
    req = fixture()
    req["samples"][0][key] = bad
    with pytest.raises(ValueError, match="finite"):
        audit_clock_bounded_residuals(**req)


def test_time_grid_must_be_strictly_ordered():
    req = fixture()
    req["samples"][1]["time_s"] = 0.
    with pytest.raises(ValueError, match="strictly increase"):
        audit_clock_bounded_residuals(**req)


def test_overflow_cannot_become_success():
    req = fixture()
    req["samples"][0]["clock_time_hard_bound_s"] = 1e308
    req["samples"][0]["signal_slew_hard_bound_per_s"] = 1e308
    with pytest.raises(ValueError, match="overflow"):
        audit_clock_bounded_residuals(**req)


def test_missing_sources_and_sample_fields_refused():
    req = fixture()
    req["slew_bound_source"] = ""
    with pytest.raises(ValueError, match="source required"):
        audit_clock_bounded_residuals(**req)
    req = fixture()
    del req["samples"][0]["clock_time_hard_bound_s"]
    with pytest.raises(ValueError, match="exact"):
        audit_clock_bounded_residuals(**req)
