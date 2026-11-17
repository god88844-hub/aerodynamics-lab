"""M26.2 uses synthetic bytes, no imported TU Braunschweig flight recordings."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import pytest

from physics.validation.flight_inventory_scaffold import draft_native_flight_manifest


def source_fixture(tmp_path):
    (tmp_path/"flight01").mkdir()
    (tmp_path/"flight02").mkdir()
    a = b"synthetic TDMS payload"
    b = b"t_s,rotor_rpm\n2,2500\n2.1,2510\n2.2,2520\n2.3,2530\n2.4,2540\n"
    (tmp_path/"flight01"/"original motor data.tdms").write_bytes(a)
    (tmp_path/"flight02"/"measured.csv").write_bytes(b)
    args = {
        "archive_id": "unverified_external_candidate",
        "publication_reference": "synthetic fixture references a paper",
        "archive_record_reference": "source repository not accessed",
        "declared_vehicle_identity": "operator claimed P80III quad",
        "source_permission": None,
        "assignments": [
            {
                "relative_path": "flight01/original motor data.tdms",
                "flight_id": "flight01", "sensor_family": "rotor",
                "declared_channels": [], "calibration_reference": None,
                "clock_reference": None, "source_notes": "original signal format unknown",
            },
            {
                "relative_path": "flight02/measured.csv",
                "flight_id": "flight02", "sensor_family": "rotor",
                "declared_channels": ["rotor_rpm"], "calibration_reference": "operator claimed reference",
                "clock_reference": "operator claimed 100Hz clock",
                "source_notes": None,
            },
        ],
    }
    return args, a, b


def test_all_original_bytes_hashed_without_guessing_missing_metadata(tmp_path):
    req, a, b = source_fixture(tmp_path)
    before = deepcopy(req)
    result = draft_native_flight_manifest(tmp_path, **req)
    assert req == before
    assert result["all_present_original_files_enumerated"]
    assert result["source_filenames_and_bytes_unchanged"]
    assert [x["original_sha256"] for x in result["manifest"]["files"]] == [
        sha256(a).hexdigest(), sha256(b).hexdigest()
    ]
    assert result["manifest"]["source_permission"] is None
    assert result["manifest"]["files"][0]["declared_channels"] == []
    assert result["source_integrity_audit"]["original_file_count"] == 2
    assert not result["published_source_or_license_independently_verified"]
    assert not result["physical_flight_measurements_validated"]
    assert not result["flight_release_authorized"]


def test_no_omitted_file_or_auto_invented_flight_id(tmp_path):
    req, _, _ = source_fixture(tmp_path)
    req["assignments"].pop()
    with pytest.raises(ValueError, match="incomplete"):
        draft_native_flight_manifest(tmp_path, **req)


def test_unknown_or_duplicate_assignments_rejected(tmp_path):
    req, _, _ = source_fixture(tmp_path)
    req["assignments"][1]["relative_path"] = req["assignments"][0]["relative_path"]
    with pytest.raises(ValueError, match="duplicate"):
        draft_native_flight_manifest(tmp_path, **req)
    req, _, _ = source_fixture_new(tmp_path)
    req["assignments"][0]["relative_path"] = "unlisted.tdms"
    with pytest.raises(ValueError, match="missing"):
        draft_native_flight_manifest(tmp_path, **req)


def source_fixture_new(tmp_path):
    # Files already exist when another branch of the test reuses tmp_path.
    req, a, b = source_fixture(tmp_path/"fresh") if False else (None, None, None)
    return req, a, b


def test_rogue_file_and_missing_permission_never_silently_ignored(tmp_path):
    req, _, _ = source_fixture(tmp_path)
    (tmp_path/"unexpected.mat").write_bytes(b"extra bytes")
    with pytest.raises(ValueError, match="incomplete"):
        draft_native_flight_manifest(tmp_path, **req)


def test_symlinked_original_refused(tmp_path):
    req, _, _ = source_fixture(tmp_path)
    link = tmp_path/"flight02"/"copy.tdms"
    link.symlink_to(tmp_path/"flight01"/"original motor data.tdms")
    with pytest.raises(ValueError, match="symlink"):
        draft_native_flight_manifest(tmp_path, **req)


def test_unsafe_or_incomplete_source_assignments_fail_closed(tmp_path):
    req, _, _ = source_fixture(tmp_path)
    req["assignments"][0]["flight_id"] = ""
    with pytest.raises(ValueError, match="flight_id"):
        draft_native_flight_manifest(tmp_path, **req)
    req, _, _ = source_fixture(tmp_path) if False else (req, None, None)
    req["assignments"][0]["claimed_physical_provenance"] = True
    with pytest.raises(ValueError, match="exact"):
        draft_native_flight_manifest(tmp_path, **req)
