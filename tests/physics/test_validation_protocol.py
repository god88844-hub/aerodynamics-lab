"""All M20 fixtures are synthetic metadata, never physical-test evidence."""
import copy
import pytest
from pydantic import ValidationError
from physics.validation.validation_protocol import (
    ProtocolAuditRequest, ValidationProtocol, audit_protocol, protocol_sha256,
)
from physics.validation.telemetry_ingestion import TelemetryManifest


def plan():
    return {
        "schema_version": "1.0", "protocol_id": "synthetic_validation_fixture",
        "intended_engineering_decision": "Predict an unmanned reference multirotor hover inside a measured envelope",
        "frozen_model_git_sha": "a" * 40,
        "frozen_design_sha256": "b" * 64,
        "frozen_controller_configuration_sha256": "c" * 64,
        "preregistration_record_reference": "synthetic://archive",
        "numerical_convergence_report_reference": "synthetic://convergence",
        "independent_reviewer_reference": "synthetic://review",
        "approved_test_safety_plan_reference": "synthetic://safety-not-an-actual-permit",
        "envelope": {
            "ambient_temperature_c": [10, 35], "air_density_kg_m3": [1, 1.3],
            "wind_speed_m_s": [0, 5], "payload_kg": [0, 2], "altitude_m": [0, 50],
        },
        "hardware": [
            {"role": role, "model": f"synthetic_{role}", "quantity": 1,
             "serial_or_lot": f"fixture_{role}",
             "geometry_or_firmware_revision": "rev1"}
            for role in ("airframe", "motor", "propeller", "esc", "battery", "controller")
        ],
        "instruments": [
            {"channel": ch, "manufacturer_model": f"synthetic_{ch}_meter",
             "serial": f"fixture_{ch}", "calibration_reference": "synthetic://calibration",
             "calibration_date_utc": "2026-11-17", "bandwidth_hz": 50,
             "clock_alignment_bound_s": .01}
            for ch in ("current_a", "terminal_voltage_v")
        ],
        "uncertainties": [
            {"channel": ch, "name": "fixture_meter_bound", "absolute_value": .01,
             "type": "hard_absolute_bound", "source_reference": "synthetic://instrument-spec"}
            for ch in ("current_a", "terminal_voltage_v")
        ],
        "acceptance_metrics": [
            {"channel": ch, "maximum_absolute_prediction_error": .2,
             "minimum_holdout_samples": 6, "maximum_sampling_gap_s": 1}
            for ch in ("current_a", "terminal_voltage_v")
        ],
        "experiments": [
            {"experiment_id": f"exp_{k}", "recording_id": f"recording_{k}",
             "vehicle_id": f"vehicle_{k}", "battery_id": f"battery_{k}",
             "role": "calibration" if k == 0 else "holdout",
             "scenario": "synthetic hover"}
            for k in range(3)
        ],
    }


def manifest(k):
    return {
        "schema_version": "1.0", "dataset_id": f"fixture_{k}",
        "dataset_kind": "reported_physical_measurements",
        "partition_role": "holdout", "experiment_id": f"exp_{k}",
        "recording_id": f"recording_{k}", "vehicle_id": f"vehicle_{k}",
        "battery_id": f"battery_{k}", "source_reference": "synthetic://fake-physical-source",
        "license_or_permission": "self generated fixture", "filename": "trace.csv",
        "raw_sha256": str(k) * 64, "expected_samples": 10,
        "predeclared_max_sample_gap_s": .5,
        "columns": ["t_s", "terminal_voltage_v", "current_a"],
    }


def score(p=None, ms=None, frozen=True):
    registered = ValidationProtocol.model_validate(p if p is not None else plan())
    return audit_protocol(ProtocolAuditRequest(
        protocol=registered,
        expected_frozen_sha256=protocol_sha256(registered) if frozen else None,
        imported_manifests=[TelemetryManifest.model_validate(m) for m in (
            ms if ms is not None else [manifest(1), manifest(2)
        ])],
    ))


def test_operator_declared_complete_still_is_not_physical_evidence():
    report = score()
    assert report["blockers"] == []
    assert report["readiness_status"] == "OPERATOR_DECLARED_PROTOCOL_COMPLETE_EXTERNAL_REVIEW_REQUIRED"
    assert report["matches_supplied_frozen_sha256"] is True
    assert report["frozen_sha256_externally_authenticated"] is False
    assert report["independently_approved"] is False
    assert report["independent_physical_accuracy_demonstrated"] is False
    assert report["validated_operating_envelope"] is None
    assert report["decision_equivalent_to_physical_testing"] is False
    assert report["uncertainty_budget"]["current_a"]["worst_case_hard_absolute_measurement_bound"] == .01


def test_hash_canonical_sorted_keys_and_source_change_fail_closed():
    p = plan()
    q = dict(reversed(list(copy.deepcopy(p).items())))
    assert protocol_sha256(ValidationProtocol.model_validate(p)) == protocol_sha256(
        ValidationProtocol.model_validate(q))
    q["acceptance_metrics"][0]["maximum_absolute_prediction_error"] = 5
    assert protocol_sha256(ValidationProtocol.model_validate(p)) != protocol_sha256(
        ValidationProtocol.model_validate(q))
    report = audit_protocol(ProtocolAuditRequest(
        protocol=ValidationProtocol.model_validate(q),
        expected_frozen_sha256=protocol_sha256(ValidationProtocol.model_validate(p)),
    ))
    assert report["readiness_status"] == "FROZEN_PROTOCOL_TAMPERED"


def test_unfrozen_protocol_cannot_claim_readiness():
    assert score(frozen=False)["readiness_status"] == "PREREGISTRATION_GAPS"


@pytest.mark.parametrize("mutate,expected", [
    (lambda p: p.update({"preregistration_record_reference": None}), "preregistration record"),
    (lambda p: p.update({"independent_reviewer_reference": None}), "independent reviewer"),
    (lambda p: p.update({"approved_test_safety_plan_reference": None}), "safety plan"),
    (lambda p: p.update({"numerical_convergence_report_reference": None}), "convergence"),
    (lambda p: p["hardware"][0].update({"serial_or_lot": None}), "serial/revision"),
    (lambda p: p["hardware"].pop(), "actual hardware registration"),
    (lambda p: p["instruments"][0].update({"calibration_reference": None}), "calibration"),
    (lambda p: p["instruments"][0].update({"clock_alignment_bound_s": None}), "clock"),
    (lambda p: p["instruments"][0].update({"bandwidth_hz": .1}), "bandwidth"),
    (lambda p: p["uncertainties"][0].update({"source_reference": None}), "Untraceable"),
    (lambda p: p["uncertainties"][0].update({"absolute_value": .2}), "exhausts"),
    (lambda p: p["uncertainties"][0].update({"type": "standard_uncertainty"}), "standard uncertainties"),
    (lambda p: p["experiments"].pop(), "two entire blind"),
    (lambda p: p["experiments"][1].update({"battery_id": "battery_0"}), "groups overlap"),
])
def test_protocol_readiness_missing_or_refuted_evidence(mutate, expected):
    p = plan()
    mutate(p)
    report = score(p)
    assert report["readiness_status"] == "PREREGISTRATION_GAPS"
    assert any(expected in b for b in report["blockers"])
    assert report["independent_physical_accuracy_demonstrated"] is False


@pytest.mark.parametrize("mutate,expected", [
    (lambda m: m.update({"recording_id": "unregistered"}), "not preregistered"),
    (lambda m: m.update({"battery_id": "wrong_pack"}), "differs"),
    (lambda m: m.update({"partition_role": "calibration"}), "differs"),
    (lambda m: m.update({"dataset_kind": "synthetic_fixture"}), "not reported physical"),
    (lambda m: m.update({"predeclared_max_sample_gap_s": 5}), "Looser sampling"),
])
def test_changed_manifest_does_not_override_frozen_test_plan(mutate, expected):
    changed = manifest(1)
    mutate(changed)
    result = score(ms=[changed, manifest(2)])
    assert any(expected in b for b in result["blockers"])
    assert result["decision_equivalent_to_physical_testing"] is False


def test_missing_holdout_and_duplicate_source_block_readiness():
    r = score(ms=[manifest(1)])
    assert any("No evidence for preregistered holdout" in b for b in r["blockers"])
    r = score(ms=[manifest(1), manifest(1), manifest(2)])
    assert any("Duplicated imported dataset" in b for b in r["blockers"])


@pytest.mark.parametrize("mutate", [
    lambda p: p.update({"frozen_model_git_sha": "fake"}),
    lambda p: p.update({"frozen_design_sha256": "b" * 63}),
    lambda p: p["envelope"].update({"payload_kg": [3, 1]}),
    lambda p: p["envelope"].update({"air_density_kg_m3": [0, 1]}),
    lambda p: p["uncertainties"][0].update({"absolute_value": float("nan")}),
    lambda p: p["acceptance_metrics"].append(copy.deepcopy(p["acceptance_metrics"][0])),
    lambda p: p["experiments"][1].update({"recording_id": "recording_0"}),
    lambda p: p["instruments"].append(copy.deepcopy(p["instruments"][0])),
    lambda p: p["instruments"][0].update({"calibration_date_utc": "not-a-date"}),
    lambda p: p.update({"untrusted_approval": True}),
])
def test_invalid_schema_fails_closed(mutate):
    p = plan()
    mutate(p)
    with pytest.raises(ValidationError):
        ValidationProtocol.model_validate(p)


def test_read_only_fixture_not_mutated():
    p = plan()
    original = copy.deepcopy(p)
    score(p)
    assert p == original
