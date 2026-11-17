"""M26.30–34 synthetic-only integration regression for source-specific M300 energy."""
from __future__ import annotations

from hashlib import md5, sha256
from pathlib import Path
from importlib import util
from copy import deepcopy
import json

import pytest

from physics.validation import zenodo_original_csv_schema as schema_mod
from physics.validation.m300_original_energy import (
    analyse_m300_original_energy, validate_explicit_m300_mapping,
)
from physics.validation.m300_energy_holdout import score_frozen_m300_energy


def sample(tmp_path, monkeypatch):
    records = []
    for j in range(6):
        for uid in ("training", "held_a", "held_b"):
            records.append(f"{uid},{1000+j*1000},24,2,HOVER\n")
    original = ("uid,elapsed_ms,voltage_v,battery_current_a,state\n"
                + "".join(records)).encode()
    path = tmp_path / "provider_original.csv"
    path.write_bytes(original)
    monkeypatch.setattr(schema_mod, "EXPECTED_MD5", md5(original).hexdigest())
    receipt = {
        "source_doi": "10.5281/zenodo.7643456",
        "provider_md5_matched": True,
        "actual_source_bytes": len(original),
        "computed_original_sha256": sha256(original).hexdigest(),
    }
    mapping = {
        "uid_column": "uid", "timestamp_column": "elapsed_ms",
        "timestamp_unit": "elapsed_ms", "voltage_column": "voltage_v",
        "voltage_unit": "V", "current_column": "battery_current_a",
        "current_unit": "A", "discharge_current_sign": "positive",
        "state_column": "state", "maximum_accepted_sample_gap_s": 1.1,
        "upper_voltage_v": 60, "upper_discharge_current_a": 200,
        "unit_source_document_reference": "synthetic fixture only, not calibrated",
    }
    protocol = {
        "frozen_model_git_sha": "a"*40,
        "frozen_protocol_sha256": "b"*64,
        "preregistered_utc": "2026-11-01T00:00:00Z",
        "frozen_model_utc": "2026-11-02T00:00:00Z",
        "partitions": [
            {"uid": "training", "group_id": "group0", "partition": "calibration",
             "first_revealed_utc": "2026-10-31T00:00:00Z"},
            {"uid": "held_a", "group_id": "group1", "partition": "holdout",
             "first_revealed_utc": "2026-11-03T00:00:00Z"},
            {"uid": "held_b", "group_id": "group2", "partition": "holdout",
             "first_revealed_utc": "2026-11-03T00:00:00Z"},
        ],
        "maximum_abs_energy_error_wh": .01,
        "measurement_hard_error_wh": .001,
        "minimum_robust_interval_coverage_fraction": 1,
        "minimum_distinct_holdout_groups": 2,
    }
    original_predictions = {
        "predictions": [
            {"uid": uid, "predicted_wh": 1/15, "lower_wh": .04, "upper_wh": .09}
            for uid in ("held_a", "held_b")
        ]
    }
    prediction = tmp_path / "frozen_energy_predictions.json"
    prediction.write_text(json.dumps(original_predictions, sort_keys=True))
    return path, receipt, mapping, protocol, prediction


def score(path, receipt, mapping, protocol, prediction):
    return score_frozen_m300_energy(
        path, receipt, mapping=mapping, protocol=protocol,
        frozen_prediction_json_path=prediction,
        frozen_prediction_sha256=sha256(prediction.read_bytes()).hexdigest(),
    )


def test_m2630_exact_published_provider_source_hash_gate(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    before = path.read_bytes()
    report = analyse_m300_original_energy(path, receipt, mapping=mapping)
    assert path.read_bytes() == before
    assert report["original_source_sha256"] == sha256(before).hexdigest()
    assert report["original_csv_record_count"] == 18
    assert report["flight_uid_count"] == 3
    assert not report["exact_aeroforge_60kg_hexacopter_hardware_matched"]
    assert not report["flight_release_authorized"]
    receipt["computed_original_sha256"] = "f"*64
    with pytest.raises(ValueError, match="changed|MD5"):
        analyse_m300_original_energy(path, receipt, mapping=mapping)


def test_m2631_exact_columns_units_sign_reference_required(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    header = ["uid", "elapsed_ms", "voltage_v", "battery_current_a", "state"]
    checked = validate_explicit_m300_mapping(mapping, header)
    assert len(checked["mapping_sha256"]) == 64
    mapping["voltage_unit"] = "mV"
    with pytest.raises(ValueError, match="V/A"):
        validate_explicit_m300_mapping(mapping, header)
    mapping["voltage_unit"] = "V"
    mapping["current_column"] = "not_in_original"
    with pytest.raises(ValueError, match="absent"):
        validate_explicit_m300_mapping(mapping, header)
    mapping["current_column"] = "battery_current_a"
    mapping["unit_source_document_reference"] = ""
    with pytest.raises(ValueError, match="reference"):
        validate_explicit_m300_mapping(mapping, header)


def test_m2632_no_time_reversal_per_original_flight_uid(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    changed = path.read_bytes().replace(b"held_a,3000", b"held_a,1000")
    path.write_bytes(changed)
    monkeypatch.setattr(schema_mod, "EXPECTED_MD5", md5(changed).hexdigest())
    receipt["actual_source_bytes"] = len(changed)
    receipt["computed_original_sha256"] = sha256(changed).hexdigest()
    with pytest.raises(ValueError, match="strictly increase"):
        analyse_m300_original_energy(path, receipt, mapping=mapping)


def test_m2632_gaps_are_unbridged_not_fabricated(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    mapping["maximum_accepted_sample_gap_s"] = .5
    result = analyse_m300_original_energy(path, receipt, mapping=mapping)
    for row in result["recordings"]:
        assert row["unbridged_gaps"] == 5
        assert row["usable_adjacent_intervals"] == 0
        assert not row["complete_covered_recording_for_numeric_holdout"]
        assert row["battery_terminal_discharge_wh_over_observed_coverage"] == 0
    result = score(path, receipt, mapping, protocol, prediction)
    assert result["status"].startswith("INCONCLUSIVE")
    assert len(result["missing_or_gapped_holdout_uids"]) == 2


def test_m2633_instrument_battery_terminal_energy_and_ah_integration(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    report = analyse_m300_original_energy(path, receipt, mapping=mapping)
    for r in report["recordings"]:
        assert r["sample_count"] == 6
        assert r["observed_elapsed_s"] == 5
        assert r["battery_terminal_discharge_wh_over_observed_coverage"] == pytest.approx(1/15)
        assert r["battery_terminal_discharge_ah_over_observed_coverage"] == pytest.approx(1/360)
        assert r["original_state_label_counts_not_interpreted"] == {"HOVER": 6}
    mapping["discharge_current_sign"] = "negative"
    with pytest.raises(ValueError, match="sign"):
        analyse_m300_original_energy(path, receipt, mapping=mapping)


def test_m2634_frozen_source_specific_holdout_conditional_only(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    protocol_original = deepcopy(protocol)
    result = score(path, receipt, mapping, protocol, prediction)
    assert protocol == protocol_original
    assert result["status"] == "CONDITIONAL_M300_DATASET_ENERGY_AGREEMENT_UNAUTHENTICATED"
    assert result["source_specific_numeric_gates_passed"]
    assert len(result["per_flight_evaluations"]) == 2
    assert len(result["canonical_analytical_fingerprint_sha256"]) == 64
    assert not result["hardware_compatible_with_60kg_hexacopter"]
    assert not result["aeroforge_full_vehicle_accuracy_validated"]


def test_m2634_failure_dominates_missing_holdout(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    pred = json.loads(prediction.read_text())
    pred["predictions"] = [{"uid": "held_a", "predicted_wh": 5,
                            "lower_wh": 4, "upper_wh": 6}]
    prediction.write_text(json.dumps(pred))
    result = score(path, receipt, mapping, protocol, prediction)
    assert result["status"] == "FAIL_FROZEN_M300_SOURCE_SPECIFIC_ENERGY_GATE"
    assert result["failed_holdout_uids"] == ["held_a"]
    assert any("held_b" in missing for missing in result["missing_or_gapped_holdout_uids"])


def test_m2634_refuse_calibration_leakage_and_postfreeze_fabrication(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    pred = json.loads(prediction.read_text())
    pred["predictions"].append({"uid": "training", "predicted_wh": .06,
                                "lower_wh": .03, "upper_wh": .09})
    prediction.write_text(json.dumps(pred))
    with pytest.raises(ValueError, match="heldout"):
        score(path, receipt, mapping, protocol, prediction)
    protocol["partitions"][1]["first_revealed_utc"] = "2026-11-01T00:00:00Z"
    pred["predictions"].pop()
    prediction.write_text(json.dumps(pred))
    with pytest.raises(ValueError, match="postdate"):
        score(path, receipt, mapping, protocol, prediction)


def test_m2634_changed_frozen_predictions_hash_refused(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        score_frozen_m300_energy(
            path, receipt, mapping=mapping, protocol=protocol,
            frozen_prediction_json_path=prediction,
            frozen_prediction_sha256="f"*64,
        )


def test_m2634_reject_duplicate_prediction_uids(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    pred = json.loads(prediction.read_text())
    pred["predictions"][1]["uid"] = "held_a"
    prediction.write_text(json.dumps(pred))
    with pytest.raises(ValueError, match="uniquely"):
        score(path, receipt, mapping, protocol, prediction)


def _cli():
    path = Path(__file__).resolve().parents[2] / "scripts" / "audit_m300_flight_energy.py"
    spec = util.spec_from_file_location("m300_flight_energy_cli", path)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.cli


def test_offline_m300_energy_cli_and_inconclusive_exit(tmp_path, monkeypatch, capsys):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    paths = {}
    for name, obj in (("receipt", receipt), ("mapping", mapping), ("protocol", protocol)):
        p = tmp_path / (name + ".json")
        p.write_text(json.dumps(obj))
        paths[name] = str(p)
    common = ["--original-csv", str(path),
              "--acquisition-receipt-json", paths["receipt"],
              "--explicit-mapping-json", paths["mapping"]]
    assert _cli()(common + ["account"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["flight_uid_count"] == 3
    assert _cli()(common + ["holdout",
             "--protocol-json", paths["protocol"],
             "--predictions-json", str(prediction),
             "--predictions-sha256", sha256(prediction.read_bytes()).hexdigest()]) == 4
    holdout = json.loads(capsys.readouterr().out)
    assert holdout["status"].startswith("CONDITIONAL")
    assert not holdout["aeroforge_full_vehicle_accuracy_validated"]


def test_m2634_robust_interval_coverage_respects_frozen_fraction(tmp_path, monkeypatch):
    path, receipt, mapping, protocol, prediction = sample(tmp_path, monkeypatch)
    payload = json.loads(prediction.read_text())
    payload["predictions"][0]["lower_wh"] = payload["predictions"][0]["predicted_wh"]
    payload["predictions"][0]["upper_wh"] = payload["predictions"][0]["predicted_wh"]
    prediction.write_text(json.dumps(payload))
    strict = score(path, receipt, mapping, protocol, prediction)
    assert strict["status"] == "FAIL_FROZEN_M300_SOURCE_SPECIFIC_ENERGY_GATE"
    assert strict["robust_interval_coverage_fraction"] == .5
    protocol["minimum_robust_interval_coverage_fraction"] = .5
    permissive = score(path, receipt, mapping, protocol, prediction)
    assert permissive["status"] == "CONDITIONAL_M300_DATASET_ENERGY_AGREEMENT_UNAUTHENTICATED"
    assert permissive["robust_interval_coverage_fraction"] == .5
