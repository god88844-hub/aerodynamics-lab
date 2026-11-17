"""M26.8–M26.10 synthetic byte-linked comparisons. NO real flight recordings."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from physics.validation.flight_regime_coverage import audit_regime_holdout_coverage
from physics.validation.frozen_flight_comparison import compare_frozen_flight_channel
from physics.validation.flight_decision_reports import assess_original_flight_decisions


def fixtures(tmp_path):
    originals = tmp_path / "originals"
    originals.mkdir()
    files, source_cases, prediction_cases, parts = [], [], [], []
    for index in range(3):
        flight = f"flight{index}"
        folder = originals / flight
        folder.mkdir()
        raw = ("t_s,rotor_rpm\n" + "".join(
            f"{1 + j / 10:.1f},{2500 + 10 * index + j}\n"
            for j in range(6)
        )).encode()
        (folder / "rotor_rpm.csv").write_bytes(raw)
        source_file = {
            "relative_path": f"{flight}/rotor_rpm.csv",
            "flight_id": flight, "sensor_family": "rotor",
            "declared_channels": ["rotor_rpm"],
            "original_sha256": sha256(raw).hexdigest(),
            "original_byte_count": len(raw),
            "calibration_reference": "claimed instrument calibration not verified",
            "clock_reference": "claimed instrument clock not verified",
            "source_notes": "synthetic values, no actual flight",
        }
        files.append(source_file)
        source_cases.append({
            "relative_path": source_file["relative_path"],
            "channels_with_units": {"rotor_rpm": "rpm"},
            "maximum_declared_sample_gap_s": 0.2,
        })
        parts.append({
            "flight_id": flight,
            "experimental_group_id": f"test_group{index}",
            "partition": "calibration" if index == 0 else "holdout",
            "source_file_sha256": source_file["original_sha256"],
            "operating_regime_id": "hover",
            "first_revealed_utc": (
                "2026-01-01T00:00:00Z" if index == 0 else "2026-01-04T00:00:00Z"
            ),
        })
        pred_csv = ("t_s,prediction,lower,upper\n" + "".join(
            f"{1 + j / 10:.1f},{2500 + 10 * index + j},"
            f"{2499 + 10 * index + j},{2501 + 10 * index + j}\n"
            for j in range(6)
        )).encode()
        pred_file = tmp_path / f"{flight}_frozen_prediction.csv"
        pred_file.write_bytes(pred_csv)
        if index != 0:
            prediction_cases.append({
                "observed_relative_path": source_file["relative_path"],
                "channel": "rotor_rpm",
                "frozen_prediction_csv_path": str(pred_file),
                "frozen_prediction_sha256": sha256(pred_csv).hexdigest(),
                "maximum_original_time_gap_s": 0.2,
            })
    manifest = {
        "schema_version": "1.0", "archive_id": "synthetic_heldout_cases",
        "publication_reference": "fake test source",
        "archive_record_reference": "not a physical data repository",
        "source_permission": "claimed rights, not independently verified",
        "declared_vehicle_identity": "fictional matched vehicle",
        "files": files,
    }
    holdout_case = {
        "frozen_model_git_sha": "a" * 40,
        "frozen_protocol_sha256": "b" * 64,
        "preregistered_utc": "2026-01-02T00:00:00Z",
        "frozen_model_utc": "2026-01-03T00:00:00Z",
        "partitions": parts,
        "minimum_holdout_groups": 2,
    }
    requirement = {
        "operating_regime_id": "hover",
        "channel": "rotor_rpm",
        "minimum_distinct_holdout_groups": 2,
        "measurement_hard_error": .1,
        "numerical_hard_error": .1,
        "additional_model_discrepancy_hard_error": .1,
        "predeclared_max_conservative_error": 1.,
        "predeclared_min_robust_interval_coverage": .95,
    }
    return originals, manifest, holdout_case, source_cases, prediction_cases, requirement


def compare(root, manifest, holdout, case, **kwargs):
    opts = {
        "measurement_hard_error": .1,
        "numerical_hard_error": .1,
        "additional_model_discrepancy_hard_error": .1,
        "predeclared_max_conservative_error": 1.,
        "predeclared_min_robust_interval_coverage": .95,
    }
    opts.update(kwargs)
    return compare_frozen_flight_channel(
        root, manifest, holdout_case=holdout, **case, **opts,
    )


def test_m268_only_distinct_heldout_groups_in_same_regime_count(tmp_path):
    root, manifest, holdout, sources, _, _ = fixtures(tmp_path)
    original = deepcopy(manifest)
    r = audit_regime_holdout_coverage(
        root, manifest, holdout_case=holdout,
        original_csv_sources=sources,
        required_regime_channels=[{"operating_regime_id": "hover", "channel": "rotor_rpm"}],
    )
    assert manifest == original
    assert r["operator_reported_coverage_sufficient"]
    assert r["regime_channel_coverage"]["hover/rotor_rpm"][
        "declared_holdout_groups_with_supported_original_csv"
    ] == ["test_group1", "test_group2"]
    assert not r["real_holdout_flights_and_sensor_calibration_authenticated"]
    assert not r["flight_release_authorized"]


def test_m268_different_regime_or_missing_channel_must_be_inconclusive(tmp_path):
    root, manifest, holdout, sources, _, _ = fixtures(tmp_path)
    holdout["partitions"][2]["operating_regime_id"] = "climb"
    r = audit_regime_holdout_coverage(
        root, manifest, holdout_case=holdout, original_csv_sources=sources,
        required_regime_channels=[{"operating_regime_id": "hover", "channel": "rotor_rpm"}],
    )
    assert not r["operator_reported_coverage_sufficient"]
    assert r["regime_channel_coverage"]["hover/rotor_rpm"]["declared_distinct_holdout_group_count"] == 1
    r2 = audit_regime_holdout_coverage(
        root, manifest, holdout_case=holdout, original_csv_sources=sources,
        required_regime_channels=[{"operating_regime_id": "hover", "channel": "pressure_pa"}],
    )
    assert r2["status"] == "REGIME_HOLDOUT_CHANNEL_COVERAGE_INCOMPLETE"


def test_m269_exact_byte_linked_holdout_residuals(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    r = compare(root, manifest, holdout, cases[0])
    assert r["samples_compared_without_interpolation"] == 6
    assert r["nominal_rmse"] == 0
    assert r["maximum_conservative_absolute_residual"] == pytest.approx(.3)
    assert r["robust_measurement_interval_coverage_fraction"] == 1
    assert r["analytical_gates_passed"]
    assert not r["physical_flight_validation_established"]
    assert not r["flight_release_authorized"]


def test_m269_frozen_prediction_tamper_detected(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    p = Path(cases[0]["frozen_prediction_csv_path"])
    p.write_bytes(p.read_bytes().replace(b"2510", b"2511", 1))
    with pytest.raises(ValueError, match="SHA-256"):
        compare(root, manifest, holdout, cases[0])


def test_m269_original_time_grid_difference_rejected_without_interpolation(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    p = Path(cases[0]["frozen_prediction_csv_path"])
    data = p.read_bytes().replace(b"1.1,2511", b"1.15,2511", 1)
    p.write_bytes(data)
    cases[0]["frozen_prediction_sha256"] = sha256(data).hexdigest()
    with pytest.raises(ValueError, match="time grids differ"):
        compare(root, manifest, holdout, cases[0])


def test_m269_original_source_tamper_detected(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    p = root / "flight1" / "rotor_rpm.csv"
    p.write_bytes(p.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="byte count|SHA-256"):
        compare(root, manifest, holdout, cases[0])


def test_m269_calibration_partition_cannot_be_used_as_holdout(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    attempt = {**cases[0], "observed_relative_path": "flight0/rotor_rpm.csv"}
    with pytest.raises(ValueError, match="declared frozen whole-flight holdout"):
        compare(root, manifest, holdout, attempt)


def test_m269_robust_interval_coverage_and_tight_limit_fail(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    r = compare(root, manifest, holdout, cases[0],
                predeclared_max_conservative_error=.05)
    assert not r["analytical_gates_passed"]
    assert r["status"] == "FROZEN_HOLDOUT_NUMERIC_GATE_FAILED"
    p = Path(cases[0]["frozen_prediction_csv_path"])
    narrowed = p.read_bytes()
    for j in range(6):
        value = 2510 + j
        narrowed = narrowed.replace(f",{value-1},{value+1}\n".encode(),
                                    f",{value-.01},{value+.01}\n".encode())
    p.write_bytes(narrowed)
    cases[0]["frozen_prediction_sha256"] = sha256(narrowed).hexdigest()
    r = compare(root, manifest, holdout, cases[0])
    assert not r["analytical_gates_passed"]
    assert r["robust_measurement_interval_coverage_fraction"] == 0


def test_m269_unknown_clock_or_prediction_in_source_root_rejected(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    manifest["files"][1]["clock_reference"] = None
    with pytest.raises(ValueError, match="calibration and clock"):
        compare(root, manifest, holdout, cases[0])


def test_m269_frozen_prediction_cannot_live_inside_original_source_root(tmp_path):
    root, manifest, holdout, _, cases, _ = fixtures(tmp_path)
    src = root / "flight1" / "rotor_rpm.csv"
    cases[0]["frozen_prediction_csv_path"] = str(src)
    cases[0]["frozen_prediction_sha256"] = sha256(src.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="outside immutable original measurement root"):
        compare(root, manifest, holdout, cases[0])


def test_m2610_same_fixed_metric_requirements_across_holdouts(tmp_path):
    root, manifest, holdout, _, cases, requirement = fixtures(tmp_path)
    r = assess_original_flight_decisions(
        root, manifest, holdout_case=holdout,
        required_metrics=[requirement], comparison_cases=cases,
    )
    assert r["all_operator_declared_analytical_gates_passed"]
    assert r["status"] == "ANALYTICALLY_CONSISTENT_NOT_PHYSICALLY_AUTHENTICATED"
    assert len(r["canonical_recomputed_decision_sha256"]) == 64
    assert r["critical_metric_verdicts"][0]["reported_passing_groups"] == ["test_group1", "test_group2"]
    assert not r["physical_decision_equivalence_established"]


def test_m2610_missing_second_holdout_group_is_inconclusive(tmp_path):
    root, manifest, holdout, _, cases, requirement = fixtures(tmp_path)
    r = assess_original_flight_decisions(
        root, manifest, holdout_case=holdout,
        required_metrics=[requirement], comparison_cases=cases[:1],
    )
    assert r["status"] == "INCONCLUSIVE_ORIGINAL_HOLDOUT_COVERAGE_MISSING"
    assert not r["all_operator_declared_analytical_gates_passed"]


def test_m2610_failure_overrides_missing_coverage(tmp_path):
    root, manifest, holdout, _, cases, requirement = fixtures(tmp_path)
    p = Path(cases[0]["frozen_prediction_csv_path"])
    pred = p.read_text().replace("2510,2509,2511", "2600,2599,2601")
    p.write_text(pred)
    cases[0]["frozen_prediction_sha256"] = sha256(pred.encode()).hexdigest()
    r = assess_original_flight_decisions(
        root, manifest, holdout_case=holdout,
        required_metrics=[requirement], comparison_cases=cases[:1],
    )
    assert r["status"] == "FAIL_DECLARED_CRITICAL_NUMERIC_LIMIT_VIOLATION"
    assert not r["all_operator_declared_analytical_gates_passed"]


def test_m2610_duplicate_measurement_case_and_extra_metric_rejected(tmp_path):
    root, manifest, holdout, _, cases, requirement = fixtures(tmp_path)
    with pytest.raises(ValueError, match="exactly once"):
        assess_original_flight_decisions(
            root, manifest, holdout_case=holdout,
            required_metrics=[requirement], comparison_cases=cases + [deepcopy(cases[0])],
        )
    cases[0]["channel"] = "pressure_pa"
    with pytest.raises(ValueError, match="undeclared regime-channel"):
        assess_original_flight_decisions(
            root, manifest, holdout_case=holdout,
            required_metrics=[requirement], comparison_cases=cases,
        )


def test_m2610_nonfinite_predeclared_threshold_refused(tmp_path):
    root, manifest, holdout, _, cases, requirement = fixtures(tmp_path)
    requirement["predeclared_max_conservative_error"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        assess_original_flight_decisions(
            root, manifest, holdout_case=holdout,
            required_metrics=[requirement], comparison_cases=cases,
        )
