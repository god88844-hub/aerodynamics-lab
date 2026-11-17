"""All fixtures are fabricated metadata/bytes; no Dataverse original dataset imported."""
from __future__ import annotations

from copy import deepcopy
from hashlib import md5
import json
from importlib import util
from pathlib import Path

import pytest

from physics.validation.dataverse_candidate import (
    EXPECTED_PID, inspect_dataverse_candidate,
    inspect_original_local_file, assess_setup_three_hardware_match,
)


def payload(data=b"rpm,voltage_v,thrust_n,current_a\n1000,44,50,10\n"):
    return {"status": "OK", "data": {
        "protocol": "doi", "authority": "10.7910", "identifier": "DVN/J5L2P4",
        "latestVersion": {
            "versionNumber": 1, "versionMinorNumber": 1, "versionState": "RELEASED",
            "files": [{"dataFile": {
                "id": 123, "filename": "setup3.csv",
                "filesize": len(data), "restricted": False,
                "checksum": {"type": "MD5", "value": md5(data).hexdigest()},
            }}],
        },
    }}


def test_metadata_enumeration_never_physically_validates_model():
    x = payload()
    old = deepcopy(x)
    r = inspect_dataverse_candidate(x)
    assert x == old
    assert r["metadata_file_count"] == 1
    assert r["source_doi"] == EXPECTED_PID
    assert r["file_inventory"][0]["file_id"] == 123
    assert r["metadata_discovery_status"] == "PUBLISHED_FILE_METADATA_FOUND_RAW_BYTES_AND_RIGHTS_PENDING"
    for key in (
        "source_license_or_permission_verified", "specific_setup_3_files_identified",
        "original_file_custody_authenticated", "physical_propulsion_model_validated",
        "flight_release_authorized",
    ):
        assert r[key] is False


def test_wrong_doi_and_duplicate_file_id_are_rejected():
    x = payload()
    x["data"]["identifier"] = "DVN/OTHER"
    with pytest.raises(ValueError, match="persistent ID"):
        inspect_dataverse_candidate(x)
    x = payload()
    x["data"]["latestVersion"]["files"] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        inspect_dataverse_candidate(x)


def test_original_file_hash_and_provider_md5_do_not_certify_physical_origin(tmp_path):
    b = b"rpm,voltage_v,thrust_n,current_a\n1000,44,50,10\n"
    report = inspect_dataverse_candidate(payload(b))
    path = tmp_path / "original.csv"
    path.write_bytes(b)
    r = inspect_original_local_file(report, file_id=123, local_path=path)
    assert r["original_byte_count"] == len(b)
    assert r["provider_checksum_matched_if_provided"]
    assert len(r["computed_original_sha256"]) == 64
    assert not r["provider_download_chain_or_author_authenticated"]
    assert not r["source_use_permission_independently_verified"]
    assert not r["flight_release_authorized"]
    assert path.read_bytes() == b


def test_provider_checksum_mismatch_is_rejected(tmp_path):
    b = b"rpm,voltage_v,thrust_n,current_a\n1000,44,50,10\n"
    x = payload(b)
    x["data"]["latestVersion"]["files"][0]["dataFile"]["checksum"]["value"] = "a" * 32
    p = tmp_path / "raw.csv"
    p.write_bytes(b)
    with pytest.raises(ValueError, match="provider checksum"):
        inspect_original_local_file(inspect_dataverse_candidate(x), file_id=123, local_path=p)


def test_bad_local_file_size_and_restricted_source_rejected(tmp_path):
    report = inspect_dataverse_candidate(payload(b"hi"))
    p = tmp_path / "raw"
    p.write_bytes(b"wrong")
    with pytest.raises(ValueError, match="byte count"):
        inspect_original_local_file(report, file_id=123, local_path=p)
    x = payload()
    x["data"]["latestVersion"]["files"][0]["dataFile"]["restricted"] = True
    with pytest.raises(ValueError, match="Restricted"):
        inspect_original_local_file(inspect_dataverse_candidate(x), file_id=123, local_path=p)


def test_published_motor_name_or_esc_cannot_be_assumed_identical():
    published = {
        "motor_name": "P80 100 Kv", "motor_revision": None,
        "esc_name": "Alpha 80 A", "propeller_name": "G30 x 10.5",
        "mount_revision": None,
    }
    reference = {
        "motor_name": "P80 III KV100", "motor_revision": "III",
        "esc_name": None, "propeller_name": "G30 x 10.5",
        "mount_revision": None,
    }
    report = assess_setup_three_hardware_match(published=published, reference=reference)
    assert report["status"] == "EXACT_INSTALLED_HARDWARE_MATCH_NOT_ESTABLISHED"
    assert report["per_attribute_reported_string_match"]["motor_revision"] is None
    assert not report["physical_validation_eligible"]


def test_matching_fabricated_strings_never_authenticate_real_equivalence():
    names = {k: "same" for k in (
        "motor_name", "motor_revision", "esc_name",
        "propeller_name", "mount_revision",
    )}
    r = assess_setup_three_hardware_match(published=names, reference=names)
    assert r["all_declared_strings_equal"]
    assert not r["physical_validation_eligible"]


def _load_cli():
    """Load root script by exact file path; CI sys.path need not contain repo root."""
    path = Path(__file__).resolve().parents[2] / "scripts" / "inspect_dataverse_propulsion.py"
    spec = util.spec_from_file_location("aeroforge_dataverse_acquisition_cli", path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.cli


def test_offline_cli_lists_unverified_metadata(tmp_path, capsys):
    cli = _load_cli()
    p = tmp_path / "dataverse.json"
    p.write_text(json.dumps(payload()), encoding="utf-8")
    assert cli(["--metadata-json", str(p)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["metadata_file_count"] == 1
    assert not report["physical_propulsion_model_validated"]


def test_offline_cli_local_file_cannot_claim_physical_validation(tmp_path, capsys):
    cli = _load_cli()
    b = b"rpm,voltage_v,thrust_n,current_a\n1000,44,50,10\n"
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps(payload(b)), encoding="utf-8")
    local = tmp_path / "actual.csv"
    local.write_bytes(b)
    assert cli(["--metadata-json", str(metadata),
                "--original-file", str(local), "--file-id", "123"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert not report["locally_staged_original_file"]["provider_download_chain_or_author_authenticated"]
