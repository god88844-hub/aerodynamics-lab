"""M12 battery evidence calibration vs independent declared test run.

All numerical fixture data below are explicitly SYNTHETIC verification data,
not laboratory observations or evidence of pack-specific physical validity.
"""
import math

import pytest
from pydantic import ValidationError

from aeroforge_schemas.component import BatterySpec
from physics.validation.battery_evidence import (
    BatteryEvidenceRequest, evaluate_battery_evidence,
)


def pack_spec():
    return BatterySpec.model_validate({
        "id": "synthetic_pack_2s",
        "name": "SYNTHETIC pack for math verification",
        "chemistry": "LiPo",
        "cells_series": 2,
        "capacity_ah": 10.0,
        "internal_resistance_ohm": 0.08,
        "ocv_curve": [
            {"soc_pct": 0.0, "cell_voltage_v": 4.0},
            {"soc_pct": 100.0, "cell_voltage_v": 4.0},
        ],
        "source": {
            "source": "Synthetic constant-OCV mathematical fixture",
            "estimated": True,
        },
    })


def sample(id, split, soc, current, resistance=.05, voltage=None):
    return {
        "id": id, "split": split, "soc_pct": soc, "current_a": current,
        "terminal_voltage_v": (
            8.0 - resistance * current if voltage is None else voltage
        ),
    }


def payload():
    return {
        "battery_id": "synthetic_pack_2s",
        "dataset_kind": "synthetic_fixture",
        "calibration_run_id": "synthetic_calibration",
        "heldout_run_id": "synthetic_held_out",
        "calibration_source": "Generated analytically for software verification",
        "heldout_source": "Generated analytically for independent-code-path verification",
        "predeclared_max_abs_percentage_error_pct": 1.0,
        "samples": [
            sample("c1", "calibration", 40, 1),
            sample("c2", "calibration", 50, 2),
            sample("c3", "calibration", 60, 3),
            sample("h1", "held_out", 45, 1.5),
            sample("h2", "held_out", 55, 2.5),
        ],
    }


def calculate(data=None, spec=None):
    spec = spec or pack_spec()
    body = BatteryEvidenceRequest.model_validate(data or payload())
    return evaluate_battery_evidence(spec, body)


def test_fit_recovers_known_ohmic_resistance_and_holdout_accuracy():
    result = calculate()
    assert result["fit"]["fitted_pack_resistance_ohm"] == pytest.approx(.05)
    assert result["heldout"]["metrics"]["mape_pct"] == pytest.approx(0, abs=1e-12)
    assert result["heldout"]["metrics"]["max_abs_percentage_error_pct"] == pytest.approx(0, abs=1e-12)
    assert result["heldout"]["within_calibration_envelope"] is True
    assert result["heldout"]["meets_predeclared_error_tolerance"] is True
    assert result["heldout"]["nominal_model_metrics"]["mae_v"] > 0
    assert result["simulation_battery_modified"] is False
    assert result["verdict"] == "SYNTHETIC_VERIFICATION_ONLY"


def test_report_does_not_rewrite_sourced_battery_resistance():
    spec = pack_spec()
    before = spec.model_dump_json()
    result = calculate(spec=spec)
    assert spec.model_dump_json() == before
    assert result["fit"]["declared_pack_resistance_ohm"] == .08
    assert result["fit"]["fitted_pack_resistance_ohm"] != .08


def test_user_reported_physical_label_is_not_authenticated():
    data = payload()
    data["dataset_kind"] = "physical_measurements"
    result = calculate(data)
    assert result["verdict"] == "REPORTED_HOLDOUT_TOLERANCE_MET_NOT_PHYSICALLY_VERIFIED"
    assert result["sources"]["self_reported_not_authenticated"] is True


def test_high_error_is_reported_even_with_valid_calibration():
    data = payload()
    data["dataset_kind"] = "physical_measurements"
    data["samples"][-1]["terminal_voltage_v"] += .5
    result = calculate(data)
    assert result["heldout"]["meets_predeclared_error_tolerance"] is False
    assert result["verdict"] == "REPORTED_HOLDOUT_TOLERANCE_NOT_MET"


def test_extrapolation_never_counts_as_heldout_in_envelope():
    data = payload()
    data["dataset_kind"] = "physical_measurements"
    data["samples"][-1] = sample("h2", "held_out", 55, 7)
    result = calculate(data)
    assert result["heldout"]["within_calibration_envelope"] is False
    assert result["verdict"] == "OUTSIDE_CALIBRATION_ENVELOPE"


@pytest.mark.parametrize("change", [
    lambda d: d.update({"calibration_run_id": d["heldout_run_id"]}),
    lambda d: d.update({"calibration_source": "  "}),
    lambda d: d.update({"predeclared_max_abs_percentage_error_pct": 0}),
    lambda d: d["samples"][-1].update({"id": "c1"}),
    lambda d: d["samples"][-1].update({"current_a": float("nan")}),
    lambda d: d["samples"][-1].update({"terminal_voltage_v": -1}),
    lambda d: d["samples"][-1].update({"split": "training_guess"}),
    lambda d: d["samples"].pop(),
    lambda d: (d["samples"][1].update({"current_a": 1}),
               d["samples"][2].update({"current_a": 1})),
])
def test_malformed_measurement_or_evidence_metadata_rejected(change):
    data = payload()
    change(data)
    if all(x["current_a"] == 1 for x in data["samples"][:3]):
        assert len({x["current_a"] for x in data["samples"][:3]}) == 1
    with pytest.raises(ValidationError):
        BatteryEvidenceRequest.model_validate(data)


def test_negative_fitted_resistance_is_refused_instead_of_clamped_to_zero():
    data = payload()
    for row in data["samples"][:3]:
        row["terminal_voltage_v"] = 9.0
    with pytest.raises(ValueError, match="nonphysical"):
        calculate(data)


def test_unknown_nominal_resistance_is_explicitly_unscored():
    spec = pack_spec()
    spec.internal_resistance_ohm = None
    result = calculate(spec=spec)
    assert result["heldout"]["nominal_model_metrics"] is None
    assert result["heldout"]["nominal_model_status"] == "UNKNOWN_RESISTANCE"


def test_too_high_current_refused_consistent_with_pack_voltage_sag_guard():
    data = payload()
    data["samples"][-1] = sample("h2", "held_out", 55, 200, voltage=7.0)
    with pytest.raises(ValueError, match="excessive voltage sag"):
        calculate(data)


def test_battery_id_mismatch_refused():
    data = payload()
    data["battery_id"] = "some_other_pack"
    with pytest.raises(ValueError, match="does not match"):
        calculate(data)


def test_actual_battery_ocv_curve_support_is_respected():
    spec = pack_spec()
    spec.ocv_curve[0].soc_pct = 20
    data = payload()
    data["samples"][0]["soc_pct"] = 5
    with pytest.raises(ValueError, match="OCV curve support"):
        calculate(data, spec)


def test_high_c_rate_stays_flagged_not_called_validated():
    spec = pack_spec()
    spec.max_discharge_c = .2
    data = payload()
    data["dataset_kind"] = "physical_measurements"
    result = calculate(data, spec)
    assert result["heldout"]["above_declared_c_rate_limit"] is True
    assert result["verdict"] == "EXCEEDS_DECLARED_C_RATE"


def test_temperature_is_only_metadata_and_never_implicitly_modeled():
    data = payload()
    data["samples"][-1]["temperature_c"] = 24
    result = calculate(data)
    assert result["temperature"]["recorded_count"] == 1
    assert result["temperature"]["missing_count"] == 4
    assert result["temperature"]["modeled"] is False


def test_missing_nominal_c_rating_is_unknown_not_safe():
    spec = pack_spec()
    spec.max_discharge_c = None
    result = calculate(spec=spec)
    assert result["heldout"]["above_declared_c_rate_limit"] is None
