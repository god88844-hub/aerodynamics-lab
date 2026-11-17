"""M26.25-29: Zenodo M300 discovery and acquisition tests use fake local bytes.

Published DOI + source MD5 identify a candidate. Tests are synthetic and
must never be mistaken for successfully downloaded real flight observations.
"""
from __future__ import annotations

from hashlib import md5, sha256
from importlib import util
from io import BytesIO
from pathlib import Path
import json

import pytest

from physics.validation import (
    zenodo_flight_candidate as metadata_mod,
    zenodo_original_download as download_mod,
    zenodo_original_csv_schema as schema_mod,
)
from physics.validation.zenodo_m300_suitability import classify_m300_evidence_suitability


def fake_metadata(size=100):
    return {
        "id": metadata_mod.RECORD_ID,
        "doi": metadata_mod.DOI,
        "metadata": {
            "title": "Drone onboard multi-modal sensor dataset",
            "creators": [{"person_or_org": {"name": "synthetic author"}}],
            "license": None,
        },
        "files": {
            "entries": {
                "Drone onboard multi-modal sensor dataset\u00a0.csv": {
                    "size": size,
                    "checksum": f"md5:{metadata_mod.EXPECTED_MD5}",
                },
            },
        },
    }


def fake_csv():
    return (
        "uid;time_unix;position_x;battery_voltage;mode\n"
        + "".join(f"uid{i};{i};1.{i};24.{i};IDLE_HOVER\n" for i in range(6))
    ).encode("utf-8")


def fake_receipt(data):
    return {
        "status": "ZENODO_PROVIDER_CHECKSUM_MATCHED_SOURCE_BYTES_LOCALLY_SAVED",
        "source_doi": metadata_mod.DOI,
        "actual_source_bytes": len(data),
        "provider_md5_matched": True,
        "computed_original_sha256": sha256(data).hexdigest(),
    }


def test_m2625_known_doi_title_md5_and_m300_mismatch_not_validated():
    report = metadata_mod.inspect_zenodo_m300_record(fake_metadata())
    assert report["doi"] == "10.5281/zenodo.7643456"
    assert report["file_inventory"][0]["provider_md5"] == "e2f188e8f5cbf498c7009f422d401207"
    assert report["reported_aircraft_type_from_dataset_description"] == "DJI Matrice 300"
    assert not report["source_rights_independently_reviewed"]
    assert not report["full_vehicle_physical_accuracy_established"]


def test_m2625_changed_doi_record_and_md5_refused():
    for key, value in (("id", 7643457), ("doi", "10.5281/zenodo.7643457")):
        r = fake_metadata()
        r[key] = value
        with pytest.raises(ValueError, match="mismatch|differs"):
            metadata_mod.inspect_zenodo_m300_record(r)
    r = fake_metadata()
    r["files"]["entries"]["Drone onboard multi-modal sensor dataset\u00a0.csv"]["checksum"] = "md5:" + "0"*32
    with pytest.raises(ValueError, match="published MD5"):
        metadata_mod.inspect_zenodo_m300_record(r)


def test_m2625_reject_duplicate_entries_or_oversized_files():
    meta = fake_metadata()
    meta["files"]["entries"]["other.csv"] = {
        "size": 1, "checksum": "md5:" + metadata_mod.EXPECTED_MD5
    }
    with pytest.raises(ValueError, match="file list differs"):
        metadata_mod.inspect_zenodo_m300_record(meta)
    with pytest.raises(ValueError, match="size outside"):
        metadata_mod.inspect_zenodo_m300_record(fake_metadata(size=100_000_000))


def test_m2626_constructed_official_url_and_rights_reference_required():
    metadata = metadata_mod.inspect_zenodo_m300_record(fake_metadata())
    with pytest.raises(ValueError, match="reviewed data rights"):
        download_mod.plan_original_zenodo_download(metadata, source_use_review_reference="")
    plan = download_mod.plan_original_zenodo_download(
        metadata, source_use_review_reference="External source rights review required",
    )
    assert plan["official_constructed_content_url"].startswith(
        "https://zenodo.org/api/records/7643456/files/"
    )
    assert plan["official_constructed_content_url"].endswith("/content")
    assert not plan["provider_file_downloaded"]


def test_m2627_provider_md5_refuses_fabricated_bytes_and_cleans_file(tmp_path):
    plan = download_mod.plan_original_zenodo_download(
        metadata_mod.inspect_zenodo_m300_record(fake_metadata(size=20)),
        source_use_review_reference="Research use review reference",
    )
    target = tmp_path / "source.csv"
    with pytest.raises(ValueError, match="MD5 check"):
        download_mod.audit_zenodo_original_stream(
            plan, output_file=target, stream=BytesIO(b"x"*20),
        )
    assert not target.exists()


def test_m2627_wrong_byte_count_and_existing_file_refused(tmp_path):
    plan = download_mod.plan_original_zenodo_download(
        metadata_mod.inspect_zenodo_m300_record(fake_metadata(size=40)),
        source_use_review_reference="Research use review reference",
    )
    target = tmp_path / "source.csv"
    with pytest.raises(ValueError, match="byte length"):
        download_mod.audit_zenodo_original_stream(
            plan, output_file=target, stream=BytesIO(b"short"),
        )
    assert not target.exists()
    target.write_text("DO NOT OVERWRITE")
    with pytest.raises(ValueError, match="new .csv"):
        download_mod.audit_zenodo_original_stream(
            plan, output_file=target, stream=BytesIO(b"x"*40),
        )
    assert target.read_text() == "DO NOT OVERWRITE"


def test_m2627_synthetic_stream_checks_length_md5_sha_without_physical_claims(
    tmp_path, monkeypatch,
):
    raw = fake_csv()
    candidate = metadata_mod.inspect_zenodo_m300_record(fake_metadata(size=len(raw)))
    plan = download_mod.plan_original_zenodo_download(
        candidate, source_use_review_reference="Synthetic test rights review only",
    )
    # Replace the published MD5 solely for a synthetic on-disk unit test;
    # the production constant remains pinned to the real published MD5.
    synthetic_hash = md5(raw).hexdigest()
    monkeypatch.setattr(download_mod, "EXPECTED_MD5", synthetic_hash)
    plan["expected_provider_md5"] = synthetic_hash
    target = tmp_path/"fake_original.csv"
    receipt = download_mod.audit_zenodo_original_stream(
        plan, output_file=target, stream=BytesIO(raw),
    )
    assert receipt["computed_original_sha256"] == sha256(raw).hexdigest()
    assert receipt["provider_md5_matched"]
    assert not receipt["physical_aircraft_hardware_matched"]
    assert not receipt["flight_validation_authorized"]


def test_m2628_inspect_actual_csv_header_only_after_original_checksum(
    tmp_path, monkeypatch,
):
    raw = fake_csv()
    path = tmp_path/"synthetic_original.csv"
    path.write_bytes(raw)
    monkeypatch.setattr(schema_mod, "EXPECTED_MD5", md5(raw).hexdigest())
    report = schema_mod.inspect_downloaded_m300_csv(path, fake_receipt(raw))
    assert report["actual_original_column_names"] == [
        "uid", "time_unix", "position_x", "battery_voltage", "mode"
    ]
    assert report["original_csv_record_count"] == 6
    assert report["rows_with_one_or_more_blank_cells"] == 0
    assert not report["all_column_units_known"]
    assert not report["flight_prediction_accuracy_validated"]


def test_m2628_refuse_bad_source_sha_and_missing_fields(tmp_path, monkeypatch):
    raw = fake_csv()
    p = tmp_path/"synthetic_original.csv"
    p.write_bytes(raw)
    monkeypatch.setattr(schema_mod, "EXPECTED_MD5", md5(raw).hexdigest())
    receipt = fake_receipt(raw)
    receipt["computed_original_sha256"] = "a"*64
    with pytest.raises(ValueError, match="changed|MD5"):
        schema_mod.inspect_downloaded_m300_csv(p, receipt)
    raw2 = raw.replace(b"uid1;1;1.1", b"uid1;1")
    p.write_bytes(raw2)
    monkeypatch.setattr(schema_mod, "EXPECTED_MD5", md5(raw2).hexdigest())
    with pytest.raises(ValueError, match="inconsistent column count"):
        schema_mod.inspect_downloaded_m300_csv(p, fake_receipt(raw2))


def test_m2629_ineligible_hexacopter_even_with_fake_local_source(tmp_path, monkeypatch):
    raw = fake_csv()
    p = tmp_path/"fake_original.csv"
    p.write_bytes(raw)
    monkeypatch.setattr(schema_mod, "EXPECTED_MD5", md5(raw).hexdigest())
    met = metadata_mod.inspect_zenodo_m300_record(fake_metadata(size=len(raw)))
    receipt = fake_receipt(raw)
    schema = schema_mod.inspect_downloaded_m300_csv(p, receipt)
    result = classify_m300_evidence_suitability(
        met, acquisition_receipt=receipt, source_csv_report=schema,
        reference_aircraft_type="60 kg hexacopter",
    )
    assert result["published_source_csv_header_inspected"]
    assert "aircraft_model" in result["known_hardware_and_experiment_evidence_gaps"]
    assert not result["eligible_as_exact_60kg_reference_hexacopter_holdout"]
    assert not result["independent_physical_evidence_decision_equivalence_established"]


def test_m2629_metadata_only_stays_metadata_only():
    meta = metadata_mod.inspect_zenodo_m300_record(fake_metadata())
    r = classify_m300_evidence_suitability(meta)
    assert not r["published_dataset_original_bytes_acquired_locally"]
    assert not r["eligible_for_source_specific_schema_test_if_rights_permit"]


def test_offline_cli_discover_and_plan(tmp_path, capsys):
    spec_path = Path(__file__).resolve().parents[2] / "scripts" / "acquire_zenodo_m300_evidence.py"
    spec = util.spec_from_file_location("m300_zenodo_acquisition_cli", spec_path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path/"api_record.json"
    path.write_text(json.dumps(fake_metadata()))
    assert module.cli(["discover", "--metadata-json", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["doi"] == metadata_mod.DOI
    assert module.cli([
        "plan", "--metadata-json", str(path),
        "--rights-review-ref", "Operator review of data use rights required",
    ]) == 0
    p = json.loads(capsys.readouterr().out)
    assert not p["provider_file_downloaded"]
    assert not p["physical_experiment_authenticated"]


def test_cli_malformed_record_and_source_rights_missing_fail(tmp_path, capsys):
    spec_path = Path(__file__).resolve().parents[2] / "scripts" / "acquire_zenodo_m300_evidence.py"
    spec = util.spec_from_file_location("m300_zenodo_acquisition_cli_err", spec_path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path/"metadata.json"
    path.write_text('{"id":7643456,"id":7643456}')
    assert module.cli(["discover", "--metadata-json", str(path)]) == 2
    assert "duplicate" in capsys.readouterr().err
