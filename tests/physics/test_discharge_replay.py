"""M15 battery replay: all input traces are SYNTHETIC numerical fixtures.

No tests constitute independent physical validation of any real battery.
"""
import copy

import pytest
from pydantic import ValidationError

from aeroforge_schemas.component import BatterySpec
from physics.propulsion.battery import BatteryPack
from physics.validation.discharge_replay import DischargeReplayRequest, replay_discharge


def battery():
    return BatterySpec.model_validate({
        "id": "verification_pack_2s",
        "name": "SYNTHETIC mathematical reference battery",
        "chemistry": "LiPo", "cells_series": 2, "capacity_ah": 1.0,
        "internal_resistance_ohm": .05,
        "max_discharge_c": 10,
        "ocv_curve": [
            {"soc_pct": 0, "cell_voltage_v": 3.3},
            {"soc_pct": 100, "cell_voltage_v": 4.2},
        ],
        "warning_cell_voltage_v": 3.5,
        "source": {"source": "Analytic synthetic fixture, not a real battery",
                   "estimated": False},
    })


def payload(kind="synthetic_fixture"):
    pack = BatteryPack(battery())
    points = []
    for i in range(11):
        elapsed = i * 60.
        soc = 100. - 100. * (5. * elapsed / 3600.)
        points.append({
            "t_s": elapsed, "current_a": 5.0,
            "terminal_voltage_v": pack.voltage_under_load(soc, 5.0),
        })
    return {
        "battery_id": "verification_pack_2s",
        "dataset_kind": kind,
        "battery_serial_or_id": "math-fixture-A",
        "run_id": "synthetic-trace-B",
        "data_source": "Generated analytically from OCV-I*R; never measured",
        "model_unused_for_calibration": True,
        "hardware_matches_reference_spec": True,
        "initial_soc_pct": 100,
        "predeclared_max_abs_voltage_error_v": .1,
        "predeclared_max_endpoint_time_error_pct": 2,
        "predeclared_max_sample_gap_s": 65,
        "samples": points,
    }


def run(data=None, spec=None):
    return replay_discharge(
        spec or battery(), DischargeReplayRequest.model_validate(
            payload() if data is None else data)
    )


def test_energy_charge_soc_and_endpoint_are_mathematically_correct():
    result = run()
    assert result["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"
    a, p = result["accounting"], result["prediction"]
    assert a["charge_consumed_ah"] == pytest.approx(5 * 600 / 3600.)
    assert a["modeled_final_soc_pct"] == pytest.approx(100 - (5 * 600 / 3600.) * 100)
    assert a["measured_energy_delivered_wh"] > 0
    assert p["voltage_rmse_v"] == pytest.approx(0, abs=1e-9)
    assert p["measured_warning_crossing_s"] is not None
    assert p["predicted_warning_crossing_s"] == pytest.approx(
        p["measured_warning_crossing_s"])
    assert p["endpoint_time_error_pct"] == pytest.approx(0)
    assert result["existing_component_modified"] is False
    assert result["existing_flight_predictions_modified"] is False


def test_disagreement_rejects_tolerance_no_recalibration():
    data = payload("physical_measurements")
    for point in data["samples"]:
        point["terminal_voltage_v"] -= .3
    out = run(data)
    assert out["prediction"]["voltage_tolerance_met"] is False
    assert out["verdict"] == "REPORTED_DISCHARGE_TOLERANCES_NOT_MET"


def test_user_label_can_only_claim_reported_not_authenticated_match():
    data = payload("physical_measurements")
    out = run(data)
    assert out["verdict"] == "REPORTED_DISCHARGE_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED"
    assert out["provenance"]["identity_instrumentation_and_provenance_not_authenticated"]


def test_low_duration_without_threshold_crossing_blocks_endurance_claim():
    data = payload("physical_measurements")
    data["samples"] = data["samples"][:6]
    out = run(data)
    assert out["prediction"]["measured_warning_crossing_s"] is None
    assert out["verdict"] == "RUNTIME_ENDPOINT_NOT_OBSERVED_IN_BOTH_TRACES"


def test_sparse_samples_and_c_rate_overrating_block_positive_verdict():
    data = payload("physical_measurements")
    data["predeclared_max_sample_gap_s"] = 30
    assert run(data)["verdict"] == "DISCHARGE_SAMPLING_TOO_SPARSE"
    spec = battery()
    spec.max_discharge_c = 4
    assert run(payload("physical_measurements"), spec)["verdict"] == "EXCEEDS_DECLARED_DISCHARGE_C_RATE"
    spec.max_discharge_c = None
    assert run(payload("physical_measurements"), spec)["verdict"] == "UNKNOWN_DISCHARGE_C_RATE_LIMIT"


def test_missing_pack_resistance_and_generic_pack_block_evidence():
    spec = battery()
    spec.internal_resistance_ohm = None
    with pytest.raises(ValueError, match="resistance is unknown"):
        run(spec=spec)
    spec = battery()
    spec.name = "Generic approximate battery"
    assert run(payload("physical_measurements"), spec)["verdict"] == "GENERIC_OR_ESTIMATED_PACK_REFERENCE_NOT_VALIDATED"


def test_data_source_and_trace_never_mutated():
    spec, data = battery(), payload()
    before = copy.deepcopy((spec.model_dump(), data))
    run(data, spec)
    assert (spec.model_dump(), data) == before


def test_no_capacity_or_ocv_extrapolation():
    data = payload()
    data["samples"] = [dict(s) for s in data["samples"]]
    data["samples"][-1]["t_s"] = 3000
    with pytest.raises(ValueError, match="outside|exceeds"):
        run(data)


@pytest.mark.parametrize("mutation", [
    lambda d: d["samples"][1].update({"t_s": 0}),
    lambda d: d["samples"][1].update({"terminal_voltage_v": -10}),
    lambda d: d["samples"][1].update({"current_a": float("nan")}),
    lambda d: d["samples"][1].update({"terminal_voltage_v": float("inf")}),
    lambda d: d.update({"initial_soc_pct": 110}),
    lambda d: d.update({"predeclared_max_abs_voltage_error_v": 0}),
    lambda d: d.update({"predeclared_max_sample_gap_s": -1}),
    lambda d: d.update({"data_source": " "}),
    lambda d: d.update({"battery_id": "../../outside"}),
    lambda d: d.update({"samples": d["samples"][:5]}),
    lambda d: d.update({"samples": [
        {**s, "current_a": 0} for s in d["samples"]
    ]}),
])
def test_bad_trace_declaration_rejected(mutation):
    data = payload()
    mutation(data)
    with pytest.raises(ValidationError):
        DischargeReplayRequest.model_validate(data)
