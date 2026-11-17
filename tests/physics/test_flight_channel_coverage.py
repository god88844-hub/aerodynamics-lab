"""M26.4 synthetic whole-flight coverage is NOT a physical validation result."""
from copy import deepcopy
from hashlib import sha256

import pytest

from physics.validation.flight_channel_coverage import audit_original_flight_channel_coverage


def fixture(tmp_path, *, repeated=False):
    rows = []
    for i in range(2):
        directory = tmp_path/f"flight0{i+1}"
        directory.mkdir()
        raw = ("t_s,rotor_rpm,pressure_pa\n" +
               "".join(f"{i*10+j*.1:.1f},{2500+j+i},{101325+j+i}\n" for j in range(5))).encode()
        if repeated and i == 1:
            raw = (tmp_path/"flight01"/"original.csv").read_bytes()
        (directory/"original.csv").write_bytes(raw)
        rows.append({
            "relative_path": f"flight0{i+1}/original.csv",
            "flight_id": f"flight0{i+1}", "sensor_family": "rotor_and_pressure",
            "declared_channels": ["rotor_rpm", "pressure_pa"],
            "original_sha256": sha256(raw).hexdigest(),
            "original_byte_count": len(raw),
            "calibration_reference": "operator says strain/calibration details archived",
            "clock_reference": "operator says instrument PPS source",
            "source_notes": "synthetic not real experiments",
        })
    manifest = {
        "schema_version": "1.0", "archive_id": "synthetic_flight_case",
        "publication_reference": "hypothetical source publication",
        "archive_record_reference": "hypothetical data repository",
        "source_permission": "operator asserts permitted, not independently checked",
        "declared_vehicle_identity": "operator claimed drone configuration",
        "files": rows,
    }
    sources = [
        {"relative_path": item["relative_path"],
         "channels_with_units": {"rotor_rpm": "rpm", "pressure_pa": "Pa"},
         "maximum_declared_sample_gap_s": 0.2} for item in rows
    ]
    return manifest, sources


def audit(tmp_path, manifest, sources, **kwargs):
    return audit_original_flight_channel_coverage(
        tmp_path, manifest, required_channels=["rotor_rpm", "pressure_pa"],
        original_csv_sources=sources, **kwargs
    )


def test_two_distinct_declared_flights_report_coverage_not_physical_accuracy(tmp_path):
    manifest, sources = fixture(tmp_path)
    old = deepcopy(manifest)
    report = audit(tmp_path, manifest, sources)
    assert manifest == old
    assert report["operator_reported_coverage_consistent"]
    assert report["status"] == "OPERATOR_DECLARED_CHANNEL_COVERAGE_COMPLETE_EXTERNAL_EVIDENCE_REVIEW_REQUIRED"
    assert report["required_channel_coverage"]["rotor_rpm"]["reported_whole_flight_count"] == 2
    assert report["required_channel_coverage"]["pressure_pa"]["reported_whole_flight_count"] == 2
    assert not report["independent_original_file_custody_authenticated"]
    assert not report["instrument_calibration_and_clocks_independently_verified"]
    assert not report["flight_or_mission_independence_authenticated"]
    assert not report["full_vehicle_physical_prediction_validated"]
    assert not report["manufacturing_or_flight_release_authorized"]


def test_one_original_source_cannot_be_counted_as_two_independent_flights(tmp_path):
    manifest, sources = fixture(tmp_path)
    result = audit(tmp_path, manifest, sources[:1])
    assert not result["operator_reported_coverage_consistent"]
    assert result["required_channel_coverage"]["rotor_rpm"]["reported_whole_flight_count"] == 1


def test_copied_identical_csv_file_cannot_invent_second_flight(tmp_path):
    manifest, sources = fixture(tmp_path, repeated=True)
    with pytest.raises(ValueError, match="identical original bytes"):
        audit(tmp_path, manifest, sources)


def test_declared_clock_and_calibration_gaps_block_coverage(tmp_path):
    manifest, sources = fixture(tmp_path)
    manifest["files"][1]["clock_reference"] = None
    report = audit(tmp_path, manifest, sources)
    assert not report["operator_reported_coverage_consistent"]
    assert report["required_channel_coverage"]["pressure_pa"]["reported_whole_flight_count"] == 1


def test_empty_rights_or_unverified_license_block_even_reported_coverage(tmp_path):
    manifest, sources = fixture(tmp_path)
    manifest["source_permission"] = None
    report = audit(tmp_path, manifest, sources)
    assert not report["operator_reported_coverage_consistent"]
    assert any("permission" in b for b in report["blockers"])


def test_duplicated_source_and_unknown_files_are_refused(tmp_path):
    manifest, sources = fixture(tmp_path)
    with pytest.raises(ValueError, match="appear exactly once"):
        audit(tmp_path, manifest, sources+[deepcopy(sources[0])])
    sources[0]["relative_path"] = "not_in_manifest.csv"
    with pytest.raises(ValueError, match="present"):
        audit(tmp_path, manifest, sources)


def test_missing_unprovided_channel_remains_inconclusive(tmp_path):
    manifest, sources = fixture(tmp_path)
    report = audit_original_flight_channel_coverage(
        tmp_path, manifest, required_channels=["arm_force_n"],
        original_csv_sources=sources,
    )
    assert report["status"] == "ORIGINAL_FLIGHT_CHANNEL_COVERAGE_GAPS"
    assert report["required_channel_coverage"]["arm_force_n"]["reported_whole_flight_count"] == 0
    assert not report["full_vehicle_physical_prediction_validated"]


def test_absent_original_file_or_corrupted_bytes_refused_even_if_declared_green(tmp_path):
    manifest, sources = fixture(tmp_path)
    (tmp_path/"flight02"/"original.csv").unlink()
    with pytest.raises(ValueError, match="missing|outside"):
        audit(tmp_path, manifest, sources)


def test_unsupported_required_channels_cannot_be_inferred(tmp_path):
    manifest, sources = fixture(tmp_path)
    with pytest.raises(ValueError, match="supported"):
        audit_original_flight_channel_coverage(
            tmp_path, manifest, required_channels=["flight_position_m"],
            original_csv_sources=sources,
        )
