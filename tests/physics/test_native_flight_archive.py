"""Original-source archive custody regression uses synthetic local bytes only."""
from __future__ import annotations

from hashlib import sha256
from copy import deepcopy

import pytest

from physics.validation.native_flight_archive import (
    hash_original_archive_file, audit_native_flight_archive,
)


def specimen(root):
    (root / "flight01").mkdir()
    (root / "flight02").mkdir()
    b1 = b"synthetic TDMS-like binary source bytes, not original flight data"
    b2 = b"synthetic MAT-like binary source bytes, not a measured experiment"
    (root / "flight01" / "pressure.tdms").write_bytes(b1)
    (root / "flight02" / "arm_strain.mat").write_bytes(b2)
    manifest = {
        "schema_version": "1.0",
        "archive_id": "SYNTHETIC_TU_NOT_REAL",
        "publication_reference": "synthetic test of article identifier",
        "archive_record_reference": "hypothetical original source",
        "source_permission": None,
        "declared_vehicle_identity": "claimed P80 III vehicle not authenticated",
        "files": [{
            "relative_path": "flight01/pressure.tdms",
            "flight_id": "flight01",
            "sensor_family": "wake_pressure",
            "declared_channels": ["pressure_pa"],
            "original_sha256": sha256(b1).hexdigest(),
            "original_byte_count": len(b1),
            "calibration_reference": None,
            "clock_reference": None,
            "source_notes": "synthetic bytes and unverified source",
        }, {
            "relative_path": "flight02/arm_strain.mat",
            "flight_id": "flight02",
            "sensor_family": "arm_strain",
            "declared_channels": [],
            "original_sha256": sha256(b2).hexdigest(),
            "original_byte_count": len(b2),
            "calibration_reference": "hypothetical calibration",
            "clock_reference": "hypothetical timebase",
            "source_notes": None,
        }],
    }
    return manifest


def test_original_files_verified_but_never_recognized_as_physical_evidence(tmp_path):
    doc = specimen(tmp_path)
    previous = deepcopy(doc)
    report = audit_native_flight_archive(tmp_path, doc)
    assert doc == previous
    assert report["original_file_count"] == 2
    assert report["flight_ids_declared"] == ["flight01", "flight02"]
    assert report["status"] == "LOCAL_ORIGINAL_BYTES_MATCH_SELF_SUPPLIED_MANIFEST_ONLY"
    assert report["unknown_original_channels"] == ["flight02/arm_strain.mat"]
    assert report["missing_calibration_references"] == ["flight01/pressure.tdms"]
    assert report["missing_clock_references"] == ["flight01/pressure.tdms"]
    assert report["source_rights_need_independent_verification"]
    assert not report["original_recorder_or_file_custody_authenticated"]
    assert not report["actual_channel_contents_decoded_or_verified"]
    assert not report["physical_instrument_calibrations_authenticated"]
    assert not report["full_aircraft_prediction_validated"]
    assert not report["manufacturing_or_flight_release_authorized"]


def test_one_byte_tamper_refused(tmp_path):
    doc = specimen(tmp_path)
    (tmp_path / "flight01" / "pressure.tdms").write_bytes(b"another")
    with pytest.raises(ValueError, match="byte count|SHA-256"):
        audit_native_flight_archive(tmp_path, doc)


def test_original_file_hash_is_computed_from_on_disk_bytes(tmp_path):
    doc = specimen(tmp_path)
    row = hash_original_archive_file(tmp_path, "flight01/pressure.tdms")
    assert row["computed_original_sha256"] == doc["files"][0]["original_sha256"]
    assert row["original_byte_count"] == doc["files"][0]["original_byte_count"]
    assert not row["physical_flight_measurement_origin_authenticated"]


@pytest.mark.parametrize("path", [
    "../private.csv", "/etc/passwd", "flight01/../flight02/arm_strain.mat",
    "flight01/pressure.exe", "flight01/bad:arg.tdms",
])
def test_path_traversal_unsupported_format_and_unknown_names_refused(tmp_path,path):
    specimen(tmp_path)
    with pytest.raises(ValueError, match="relative_path|format"):
        hash_original_archive_file(tmp_path,path)


def test_symlink_escape_refused(tmp_path):
    doc = specimen(tmp_path)
    original = tmp_path / "flight01" / "pressure.tdms"
    original.unlink()
    target = tmp_path / "flight02" / "arm_strain.mat"
    original.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        audit_native_flight_archive(tmp_path,doc)


def test_missing_real_file_fails_closed(tmp_path):
    doc = specimen(tmp_path)
    (tmp_path / "flight02" / "arm_strain.mat").unlink()
    with pytest.raises(ValueError, match="missing|outside"):
        audit_native_flight_archive(tmp_path,doc)


def test_unknown_channels_are_never_inferred_from_native_file_bytes(tmp_path):
    doc = specimen(tmp_path)
    report = audit_native_flight_archive(tmp_path,doc)
    record = next(x for x in report["original_files_checked"] if x["sensor_family"]=="arm_strain")
    assert record["declared_channels_operator_reported"] == []
    assert record["clock_reference_operator_reported"] == "hypothetical timebase"
    assert not report["actual_channel_contents_decoded_or_verified"]


def test_duplicate_original_paths_and_malformed_hash_rejected(tmp_path):
    doc = specimen(tmp_path)
    doc["files"].append(deepcopy(doc["files"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        audit_native_flight_archive(tmp_path,doc)
    doc["files"].pop()
    doc["files"][0]["original_sha256"] = "a"*63
    with pytest.raises(ValueError, match="64-hex"):
        audit_native_flight_archive(tmp_path,doc)


def test_unrecognized_manifest_fields_and_negative_size_rejected(tmp_path):
    doc = specimen(tmp_path)
    doc["physically_certified"] = True
    with pytest.raises(ValueError, match="exact root"):
        audit_native_flight_archive(tmp_path,doc)
    doc.pop("physically_certified")
    doc["files"][0]["original_byte_count"] = -1
    with pytest.raises(ValueError, match="byte count"):
        audit_native_flight_archive(tmp_path,doc)


def test_source_claims_do_not_authenticate_flight(tmp_path):
    doc = specimen(tmp_path)
    doc["source_permission"] = "claimed open access (operator declaration only)"
    doc["files"][0]["calibration_reference"] = "claimed NIST traceable certificate"
    doc["files"][0]["clock_reference"] = "claimed GPS timebase"
    report = audit_native_flight_archive(tmp_path,doc)
    assert not report["original_recorder_or_file_custody_authenticated"]
    assert not report["physical_instrument_calibrations_authenticated"]
    assert not report["measurement_clock_alignment_authenticated"]
    assert not report["whole_flight_independence_or_blinding_authenticated"]


def test_cli_hashes_real_bytes_without_reinterpreting_binary(tmp_path, capsys):
    from importlib import util
    from pathlib import Path
    script = Path(__file__).resolve().parents[2] / "scripts" / "audit_native_flight_archive.py"
    spec = util.spec_from_file_location("aeroforge_native_archive_cli", script)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = specimen(tmp_path)
    assert mod.cli(["--root", str(tmp_path), "--hash-file", "flight01/pressure.tdms"]) == 0
    import json
    result = json.loads(capsys.readouterr().out)
    assert result["computed_original_sha256"] == doc["files"][0]["original_sha256"]
    assert result["physical_flight_measurement_origin_authenticated"] is False


def test_cli_checks_entire_original_bundle_not_a_favorable_single_file(tmp_path, capsys):
    from importlib import util
    from pathlib import Path
    import json
    script = Path(__file__).resolve().parents[2] / "scripts" / "audit_native_flight_archive.py"
    spec = util.spec_from_file_location("aeroforge_native_archive_cli_full", script)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = specimen(tmp_path)
    manifest = tmp_path.parent / "native_source_manifest.json"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    assert mod.cli(["--root", str(tmp_path), "--manifest", str(manifest)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["original_file_count"] == 2
    assert result["full_aircraft_prediction_validated"] is False
    (tmp_path / "flight02" / "arm_strain.mat").unlink()
    assert mod.cli(["--root", str(tmp_path), "--manifest", str(manifest)]) == 2
    assert "FAILED" in capsys.readouterr().err


def test_legitimate_publisher_source_filename_with_spaces_is_not_renamed(tmp_path):
    specimen(tmp_path)
    p = tmp_path / "flight01" / "Flight 01 original TDMS.tdms"
    original = b"synthetic original-file bytes"
    p.write_bytes(original)
    result = hash_original_archive_file(tmp_path, "flight01/Flight 01 original TDMS.tdms")
    assert result["computed_original_sha256"] == sha256(original).hexdigest()
    assert result["relative_path"] == "flight01/Flight 01 original TDMS.tdms"


def test_malformed_channel_lists_fail_with_validation_error(tmp_path):
    doc = specimen(tmp_path)
    doc["files"][0]["declared_channels"] = [["pressure_pa"]]
    with pytest.raises(ValueError, match="declared_channels"):
        audit_native_flight_archive(tmp_path,doc)
