"""M26.11–M26.13 synthetic evidence regression: NOT actual flight data."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from physics.validation.flight_envelope_limits import screen_flight_hard_limits
from physics.validation.flight_uncertainty_stress import audit_frozen_uncertainty_sensitivity
from physics.validation.flight_evidence_dossier import build_flight_evidence_dossier


def case(tmp_path):
    root = tmp_path / "originals"
    root.mkdir()
    files, partitions, comparisons = [], [], []
    for i in range(3):
        d = root / f"flight{i}"
        d.mkdir()
        original = ("t_s,rotor_rpm\n" + "".join(
            f"{j/10:.1f},{2500+i*10+j}\n" for j in range(6)
        )).encode("utf-8")
        (d / "rotor.csv").write_bytes(original)
        f = {
            "relative_path": f"flight{i}/rotor.csv",
            "flight_id": f"flight{i}",
            "sensor_family": "rotor",
            "declared_channels": ["rotor_rpm"],
            "original_sha256": sha256(original).hexdigest(),
            "original_byte_count": len(original),
            "calibration_reference": "operator declared instrument, not checked",
            "clock_reference": "operator declared timebase, not checked",
            "source_notes": "entirely synthetic fixture",
        }
        files.append(f)
        partitions.append({
            "flight_id": f"flight{i}",
            "experimental_group_id": f"group{i}",
            "partition": "calibration" if i == 0 else "holdout",
            "source_file_sha256": f["original_sha256"],
            "operating_regime_id": "hover",
            "first_revealed_utc": "2026-01-01T00:00:00Z" if i == 0 else "2026-01-05T00:00:00Z",
        })
        if i:
            pred = ("t_s,prediction,lower,upper\n" + "".join(
                f"{j/10:.1f},{2500+i*10+j},{2499+i*10+j},{2501+i*10+j}\n"
                for j in range(6)
            )).encode()
            prediction_path = tmp_path / f"flight{i}-prediction.csv"
            prediction_path.write_bytes(pred)
            comparisons.append({
                "observed_relative_path": f["relative_path"],
                "channel": "rotor_rpm",
                "frozen_prediction_csv_path": str(prediction_path),
                "frozen_prediction_sha256": sha256(pred).hexdigest(),
                "maximum_original_time_gap_s": .2,
            })
    manifest = {
        "schema_version": "1.0", "archive_id": "synthetic_archive",
        "publication_reference": "synthetic fictitious laboratory",
        "archive_record_reference": "not original physical observations",
        "source_permission": "operator claimed permission",
        "declared_vehicle_identity": "unverified hypothetical drone",
        "files": files,
    }
    split = {
        "frozen_model_git_sha": "a"*40,
        "frozen_protocol_sha256": "b"*64,
        "preregistered_utc": "2026-01-02T00:00:00Z",
        "frozen_model_utc": "2026-01-03T00:00:00Z",
        "partitions": partitions,
        "minimum_holdout_groups": 2,
    }
    metric = {
        "operating_regime_id": "hover", "channel": "rotor_rpm",
        "minimum_distinct_holdout_groups": 2,
        "measurement_hard_error": .1,
        "numerical_hard_error": .1,
        "additional_model_discrepancy_hard_error": .1,
        "predeclared_max_conservative_error": 1.,
        "predeclared_min_robust_interval_coverage": .95,
    }
    hard = {
        "operating_regime_id": "hover", "channel": "rotor_rpm",
        "envelope_min": 2400., "envelope_max": 2600.,
        "hard_limit_min": 100., "hard_limit_max": 5000.,
        "maximum_original_time_gap_s": .2,
        "limit_source": "synthetic reference rating, NOT a real part specification",
    }
    stressed = [{
        "observed_relative_path": c["observed_relative_path"],
        "widened_error_scenarios": [
            {"scenario_id": "modest", "measurement_hard_error": .2,
             "numerical_hard_error": .2,
             "additional_model_discrepancy_hard_error": .2},
        ],
    } for c in comparisons]
    return root, manifest, split, metric, hard, comparisons, stressed


def dossier(root, manifest, split, metric, hard, comparisons, stressed):
    return build_flight_evidence_dossier(
        root, manifest, holdout_case=split,
        required_metrics=[metric], comparison_cases=comparisons,
        required_limits=[hard], stress_cases=stressed,
    )


def test_m2611_hard_envelope_screen_is_not_physical_certification(tmp_path):
    root, manifest, split, metric, hard, comparisons, _ = case(tmp_path)
    old = deepcopy(manifest)
    x = screen_flight_hard_limits(
        root, manifest, holdout_case=split, required_limits=[hard],
        observed_source_paths=[c["observed_relative_path"] for c in comparisons],
    )
    assert manifest == old
    assert x["status"] == "WITHIN_OPERATOR_DECLARED_LIMITS_UNAUTHENTICATED"
    assert x["all_screened_cases_within_declared_envelope"]
    assert not x["any_declared_hard_limit_exceeded"]
    assert not x["original_physical_measurements_authenticated"]
    assert not x["airworthiness_or_flight_release_authorized"]


def test_m2611_actual_numeric_hard_limit_exceedance_is_fail(tmp_path):
    root, manifest, split, _, hard, comparisons, _ = case(tmp_path)
    p = root / "flight1" / "rotor.csv"
    raw = p.read_bytes().replace(b"2510", b"6000", 1)
    p.write_bytes(raw)
    row = next(f for f in manifest["files"] if f["flight_id"] == "flight1")
    row["original_sha256"] = sha256(raw).hexdigest()
    split["partitions"][1]["source_file_sha256"] = row["original_sha256"]
    x = screen_flight_hard_limits(
        root, manifest, holdout_case=split, required_limits=[hard],
        observed_source_paths=[c["observed_relative_path"] for c in comparisons],
    )
    assert x["status"] == "FAIL_DECLARED_PHYSICAL_HARD_LIMIT_EXCEEDED"
    assert x["any_declared_hard_limit_exceeded"]


def test_m2611_exceed_validity_envelope_but_not_hard_limit_is_inconclusive(tmp_path):
    root, manifest, split, _, hard, comparisons, _ = case(tmp_path)
    hard["envelope_max"] = 2505.
    x = screen_flight_hard_limits(
        root, manifest, holdout_case=split, required_limits=[hard],
        observed_source_paths=[c["observed_relative_path"] for c in comparisons],
    )
    assert x["status"] == "INCONCLUSIVE_OUT_OF_DECLARED_OPERATING_ENVELOPE_OR_MISSING"
    assert not x["any_declared_hard_limit_exceeded"]


def test_m2611_missing_required_channel_cannot_be_declared_green(tmp_path):
    root, manifest, split, _, hard, _, _ = case(tmp_path)
    extra = dict(hard, channel="pressure_pa")
    result = screen_flight_hard_limits(
        root, manifest, holdout_case=split,
        required_limits=[hard, extra], observed_source_paths=["flight1/rotor.csv"],
    )
    assert result["missing_declared_regime_channels"] == ["hover/pressure_pa"]
    assert result["status"].startswith("INCONCLUSIVE")


def test_m2612_widening_recomputes_real_bytes_and_preserves_frozen_limits(tmp_path):
    root, manifest, split, metric, _, comparisons, _ = case(tmp_path)
    x = audit_frozen_uncertainty_sensitivity(
        root, manifest, holdout_case=split, original_case=comparisons[0],
        baseline_limits={k: v for k, v in metric.items() if k in {
            "measurement_hard_error", "numerical_hard_error",
            "additional_model_discrepancy_hard_error",
            "predeclared_max_conservative_error",
            "predeclared_min_robust_interval_coverage",
        }},
        widened_error_scenarios=[{
            "scenario_id": "modest",
            "measurement_hard_error": .2,
            "numerical_hard_error": .2,
            "additional_model_discrepancy_hard_error": .2,
        }],
    )
    assert x["status"] == "ALL_SUBMITTED_UNCERTAINTY_STRESSES_CONDITIONALLY_PASS_UNAUTHENTICATED"
    assert x["baseline_recomputed_report"]["maximum_conservative_absolute_residual"] == pytest.approx(.3)
    assert x["stress_scenario_reports"][0]["maximum_conservative_absolute_residual"] == pytest.approx(.6)
    assert not x["true_hard_uncertainty_bounds_independently_established"]


def test_m2612_large_hard_error_stress_refuses_robust_decision(tmp_path):
    root, manifest, split, metric, _, comparisons, _ = case(tmp_path)
    base = {k: metric[k] for k in (
        "measurement_hard_error", "numerical_hard_error",
        "additional_model_discrepancy_hard_error",
        "predeclared_max_conservative_error",
        "predeclared_min_robust_interval_coverage",
    )}
    x = audit_frozen_uncertainty_sensitivity(
        root, manifest, holdout_case=split, original_case=comparisons[0],
        baseline_limits=base,
        widened_error_scenarios=[{
            "scenario_id": "unbounded_error", "measurement_hard_error": 2.,
            "numerical_hard_error": .1,
            "additional_model_discrepancy_hard_error": .1,
        }],
    )
    assert x["status"] == "INCONCLUSIVE_UNCERTAINTY_STRESS_LOSES_DECLARED_PASS"
    assert x["stress_scenario_reports"][0]["robust_measurement_interval_coverage_fraction"] == 0


def test_m2612_cannot_improve_result_by_shrinking_errors(tmp_path):
    root, manifest, split, metric, _, comparisons, _ = case(tmp_path)
    base = {k: metric[k] for k in (
        "measurement_hard_error", "numerical_hard_error",
        "additional_model_discrepancy_hard_error",
        "predeclared_max_conservative_error",
        "predeclared_min_robust_interval_coverage",
    )}
    with pytest.raises(ValueError, match="cannot reduce"):
        audit_frozen_uncertainty_sensitivity(
            root, manifest, holdout_case=split, original_case=comparisons[0],
            baseline_limits=base, widened_error_scenarios=[{
                "scenario_id": "optimistic", "measurement_hard_error": 0.,
                "numerical_hard_error": .1,
                "additional_model_discrepancy_hard_error": .1,
            }],
        )


def test_m2613_dossier_recomputes_and_fingerprints_all_three_gates(tmp_path):
    root, manifest, split, metric, hard, comparisons, stressed = case(tmp_path)
    initial = deepcopy((manifest, split, metric, hard, comparisons, stressed))
    x = dossier(root, manifest, split, metric, hard, comparisons, stressed)
    assert (manifest, split, metric, hard, comparisons, stressed) == initial
    assert x["status"] == "CONDITIONAL_ANALYTICAL_SCREEN_ONLY_EXTERNAL_PHYSICAL_REVIEW_REQUIRED"
    assert x["all_declared_analytical_gates_passed"]
    assert len(x["reproducible_dossier_sha256"]) == 64
    assert len(x["per_original_holdout_uncertainty_stress_reports"]) == 2
    assert not x["decision_equivalent_physical_evidence_established"]
    assert not x["manufacturing_or_flight_release_authorized"]
    y = dossier(root, manifest, split, metric, hard,
                list(reversed(comparisons)), list(reversed(stressed)))
    assert y["reproducible_dossier_sha256"] == x["reproducible_dossier_sha256"]


def test_m2613_missing_distinct_holdout_is_inconclusive(tmp_path):
    root, manifest, split, metric, hard, comparisons, stressed = case(tmp_path)
    x = dossier(root, manifest, split, metric, hard,
                comparisons[:1], stressed[:1])
    assert x["status"] == "INCONCLUSIVE_SOURCE_ENVELOPE_COVERAGE_OR_ERROR_SENSITIVITY"
    assert not x["all_declared_analytical_gates_passed"]


def test_m2613_hard_limit_exceedance_overrides_other_results(tmp_path):
    root, manifest, split, metric, hard, comparisons, stressed = case(tmp_path)
    hard["hard_limit_max"] = 2510.
    hard["envelope_max"] = 2509.
    x = dossier(root, manifest, split, metric, hard, comparisons, stressed)
    assert x["status"] == "FAIL_CRITICAL_RECOMPUTED_LIMIT_OR_PREDICTION"
    assert x["operating_envelope_and_hard_limit_report"]["any_declared_hard_limit_exceeded"]


def test_m2613_uncertainty_fragility_blocks_conditional_pass(tmp_path):
    root, manifest, split, metric, hard, comparisons, stressed = case(tmp_path)
    stressed[0]["widened_error_scenarios"][0]["measurement_hard_error"] = 2.
    x = dossier(root, manifest, split, metric, hard, comparisons, stressed)
    assert x["status"] == "INCONCLUSIVE_SOURCE_ENVELOPE_COVERAGE_OR_ERROR_SENSITIVITY"


def test_m2613_absent_critical_safety_gate_not_silently_ignored(tmp_path):
    root, manifest, split, metric, hard, comparisons, stressed = case(tmp_path)
    with pytest.raises(ValueError, match="scope must exactly match"):
        build_flight_evidence_dossier(
            root, manifest, holdout_case=split, required_metrics=[metric],
            comparison_cases=comparisons, required_limits=[], stress_cases=stressed,
        )


def test_m2613_missing_stress_case_must_not_count_as_pass(tmp_path):
    root, manifest, split, metric, hard, comparisons, stressed = case(tmp_path)
    with pytest.raises(ValueError, match="every original comparison"):
        dossier(root, manifest, split, metric, hard, comparisons, stressed[:1])


def test_m2613_original_file_tampering_blocked_before_report(tmp_path):
    root, manifest, split, metric, hard, comparisons, stressed = case(tmp_path)
    p = root / "flight2" / "rotor.csv"
    p.write_bytes(p.read_bytes() + b"altered")
    with pytest.raises(ValueError, match="byte count|SHA-256|original"):
        dossier(root, manifest, split, metric, hard, comparisons, stressed)
