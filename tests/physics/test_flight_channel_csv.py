"""Synthetic M26.3 fixed CSV audit: never asserts acquired physical flight logs."""
from copy import deepcopy
from hashlib import sha256

import pytest

from physics.validation.flight_channel_csv import audit_original_flight_channel_csv


def fixture(tmp_path):
    (tmp_path/"flight01").mkdir()
    original = ("t_s,rotor_rpm,pressure_pa\n"
                + "".join(f"{10+i*.1:.1f},{2500+i},{101325+i}\n" for i in range(5))).encode()
    (tmp_path/"flight01"/"sample.csv").write_bytes(original)
    manifest = {
        "schema_version": "1.0", "archive_id": "synthetic_archive",
        "publication_reference": "synthetic fixture source",
        "archive_record_reference": "fictitious archive, no real aircraft",
        "source_permission": None,
        "declared_vehicle_identity": "claimed unverified P80III airframe",
        "files": [{
            "relative_path": "flight01/sample.csv",
            "flight_id": "flight01", "sensor_family": "rotor_and_wake",
            "declared_channels": ["rotor_rpm", "pressure_pa"],
            "original_sha256": sha256(original).hexdigest(),
            "original_byte_count": len(original),
            "calibration_reference": None, "clock_reference": None,
            "source_notes": "synthetic exact header",
        }],
    }
    return manifest


def audit(root, manifest, **overrides):
    return audit_original_flight_channel_csv(
        root, manifest, relative_path="flight01/sample.csv",
        channels_with_units={"rotor_rpm": "rpm", "pressure_pa": "Pa"},
        maximum_declared_sample_gap_s=0.2, **overrides
    )


def test_raw_csv_preserved_and_physical_source_refused(tmp_path):
    m = fixture(tmp_path)
    old = deepcopy(m)
    out = audit_original_flight_channel_csv(
        tmp_path, m, relative_path="flight01/sample.csv",
        channels_with_units={"rotor_rpm": "rpm", "pressure_pa": "Pa"},
        maximum_declared_sample_gap_s=0.2,
    )
    assert m == old
    assert out["flight_id"] == "flight01"
    assert out["original_csv_sample_count"] == 5
    assert out["first_original_time_s"] == 10.
    assert out["original_value_ranges"]["rotor_rpm"] == [2500, 2504]
    assert out["within_operator_declared_time_gap"]
    assert not out["physical_sensor_measurements_authenticated"]
    assert not out["independent_physical_model_validation_established"]
    assert not out["flight_release_authorized"]


def test_not_make_up_missing_channels(tmp_path):
    m = fixture(tmp_path)
    with pytest.raises(ValueError, match="actual original channels differ"):
        audit_original_flight_channel_csv(
            tmp_path, m, relative_path="flight01/sample.csv",
            channels_with_units={"rotor_rpm": "rpm"},
            maximum_declared_sample_gap_s=0.2,
        )


def test_unit_mismatch_and_unknown_measurement_rejected(tmp_path):
    m = fixture(tmp_path)
    with pytest.raises(ValueError, match="channel/unit"):
        audit_original_flight_channel_csv(
            tmp_path, m, relative_path="flight01/sample.csv",
            channels_with_units={"rotor_rpm": "rad/s", "pressure_pa": "Pa"},
            maximum_declared_sample_gap_s=0.2,
        )
    with pytest.raises(ValueError, match="channel/unit"):
        audit_original_flight_channel_csv(
            tmp_path, m, relative_path="flight01/sample.csv",
            channels_with_units={"unknown_voltage": "V"},
            maximum_declared_sample_gap_s=0.2,
        )


def test_tampered_original_rejected_before_parsing(tmp_path):
    m = fixture(tmp_path)
    p = tmp_path/"flight01"/"sample.csv"
    p.write_bytes(p.read_bytes().replace(b"2500", b"2501"))
    with pytest.raises(ValueError, match="SHA-256"):
        audit_original_flight_channel_csv(
            tmp_path, m, relative_path="flight01/sample.csv",
            channels_with_units={"rotor_rpm": "rpm", "pressure_pa": "Pa"},
            maximum_declared_sample_gap_s=0.2,
        )


def test_sparse_unsynchronized_original_is_not_green(tmp_path):
    m = fixture(tmp_path)
    out = audit_original_flight_channel_csv(
        tmp_path, m, relative_path="flight01/sample.csv",
        channels_with_units={"rotor_rpm": "rpm", "pressure_pa": "Pa"},
        maximum_declared_sample_gap_s=0.05,
    )
    assert not out["within_operator_declared_time_gap"]
    assert out["status"] == "CSV_SOURCE_GAPS_EXCEED_DECLARED_SAMPLE_LIMIT"


def test_unsorted_original_time_is_rejected_not_interpolated(tmp_path):
    m = fixture(tmp_path)
    p = tmp_path/"flight01"/"sample.csv"
    raw = p.read_bytes().replace(b"10.2,2502", b"10.1,2502")
    p.write_bytes(raw)
    m["files"][0]["original_sha256"] = sha256(raw).hexdigest()
    m["files"][0]["original_byte_count"] = len(raw)
    with pytest.raises(ValueError, match="strictly increasing"):
        audit_original_flight_channel_csv(
            tmp_path, m, relative_path="flight01/sample.csv",
            channels_with_units={"rotor_rpm": "rpm", "pressure_pa": "Pa"},
            maximum_declared_sample_gap_s=0.2,
        )


def test_missing_calibration_and_clock_are_transparently_unknown(tmp_path):
    m = fixture(tmp_path)
    out = audit_original_flight_channel_csv(
        tmp_path, m, relative_path="flight01/sample.csv",
        channels_with_units={"rotor_rpm": "rpm", "pressure_pa": "Pa"},
        maximum_declared_sample_gap_s=0.2,
    )
    assert out["clock_reference_operator_supplied"] is None
    assert out["calibration_reference_operator_supplied"] is None
    assert not out["source_clock_calibration_independently_verified"]
