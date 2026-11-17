"""M17 physical-source test: real published table, unmatched motor and installation.

No published thrust is treated as an AeroForge reference-airframe prediction.
"""
from pathlib import Path
import json

import pytest

from physics.validation.g30_installation import SOURCE, compare_g30_public_bench


def test_nine_published_real_points_and_power_anomaly_are_visible():
    report = compare_g30_public_bench()
    assert report["data_quality"]["published_measurement_count"] == 9
    assert report["data_quality"]["reported_power_inconsistency_count"] == 1
    anomalous = report["data_quality"]["reported_power_anomalies"][0]
    assert anomalous["case"] == 2
    assert anomalous["source_reported_power_w"] == 3234
    assert anomalous["voltage_times_current_w"] == pytest.approx(32.34)
    assert report["comparison"]["in_envelope_count"] == 3
    assert report["comparison"]["out_of_envelope_count"] == 6
    assert report["reference"]["same_propeller_geometry"] is True
    assert report["reference"]["same_motor"] is False


def test_only_inside_rpm_envelope_is_compared_never_extrapolated():
    report = compare_g30_public_bench()
    for row in report["comparison"]["rows"]:
        if row["rpm"] >= 1719:
            assert row["within_aeroforge_reference_rpm_range"] is True
            assert row["aeroforge_reference_thrust_n"] > 0
            assert row["relative_difference_pct_vs_reference"] is not None
        else:
            assert row["aeroforge_reference_thrust_n"] is None
            assert row["relative_difference_pct_vs_reference"] is None
        assert row["difference_is_a_physically_valid_prediction_error"] is False
    assert report["comparison"]["mean_absolute_relative_difference_pct_descriptive_only"] > 0


def test_different_motor_and_mount_can_never_mark_aeroforge_validated():
    report = compare_g30_public_bench()
    assert report["verdict"] == "REAL_EXPERIMENTAL_PROP_DATA_BUT_INSTALLATION_AND_MOTOR_MISMATCH"
    assert report["independent_physical_validation_of_aeroforge_reference"] is False
    assert report["supports_automatic_ground_effect_correction"] is False
    assert report["supports_aeroforge_electrical_power_comparison"] is False
    assert report["physical_equivalence_established"] is False


@pytest.mark.parametrize("change,expected", [
    (lambda d: d.update({"motor_match": True}), "mismatch"),
    (lambda d: d.update({"bench_installation_match_verified": True}), "mismatch"),
    (lambda d: d.update({"propeller_geometry_match": False}), "propeller geometry"),
    (lambda d: d["measurements"][0].update({"rpm": 2000}), "operating point"),
    (lambda d: d["measurements"][1].update({"force_n": float("nan")}), "nonfinite"),
    (lambda d: d.update({"doi": "unverifiable DOI"}), "DOI"),
    (lambda d: d["measurements"].pop(), "nine published"),
])
def test_unverified_changes_cannot_silently_promote_validation(tmp_path: Path, change, expected):
    dataset = json.loads(SOURCE.read_text(encoding="utf-8"))
    change(dataset)
    new = tmp_path / "changed.json"
    new.write_text(json.dumps(dataset))
    with pytest.raises(ValueError, match=expected):
        compare_g30_public_bench(source=new)


def test_published_power_typo_cannot_be_edited_into_a_clean_measurement(tmp_path: Path):
    original = json.loads(SOURCE.read_text(encoding="utf-8"))
    original["measurements"][1]["reported_power_w"] = 32.34
    # A user-modified source must no longer claim it is the original table.
    altered = tmp_path / "corrected.json"
    altered.write_text(json.dumps(original))
    report = compare_g30_public_bench(source=altered)
    assert report["data_quality"]["reported_power_inconsistency_count"] == 0
    assert report["independent_physical_validation_of_aeroforge_reference"] is False
