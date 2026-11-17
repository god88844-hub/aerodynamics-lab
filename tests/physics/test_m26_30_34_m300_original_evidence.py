"""M26.35–M26.39 original M300 pipeline: all source fixtures are SYNTHETIC."""
from __future__ import annotations
from copy import deepcopy
from hashlib import md5,sha256
from importlib import util
from pathlib import Path
import json
import pytest

from physics.validation import zenodo_original_quality as quality
from physics.validation.zenodo_official_fallback import _official_source_urls, alternate_zenodo_original_download
from physics.validation.zenodo_original_time_segments import audit_original_m300_time_segments
from physics.validation.zenodo_original_channel_probe import inspect_declared_original_m300_channel
from physics.validation.zenodo_m300_exploratory_report import build_original_m300_exploratory_report
from physics.validation.zenodo_flight_candidate import inspect_zenodo_m300_record
from physics.validation.zenodo_original_download import plan_original_zenodo_download

def fixture(tmp_path,monkeypatch):
    raw=("clock_ms;voltage_mV;current_mA;note\n"+
         "".join(f"{1000+100*i};{24000+i};{5000+i};SYNTHETIC\n" for i in range(6))).encode()
    file=tmp_path/"synthetic_original.csv"
    file.write_bytes(raw)
    monkeypatch.setattr(quality,"EXPECTED_MD5",md5(raw).hexdigest())
    receipt={
        "source_doi":"10.5281/zenodo.7643456",
        "actual_source_bytes":len(raw),
        "provider_md5_matched":True,
        "computed_original_sha256":sha256(raw).hexdigest(),
    }
    mapping={
        "original_time_column":"clock_ms",
        "original_time_unit":"ms",
        "declared_max_sample_gap_s":0.2,
        "channel_mappings":[{"original_column":"voltage_mV","claimed_channel":"battery_voltage",
                             "claimed_original_unit":"mV",
                             "instrument_unit_document_reference":"SYNTHETIC source units claimed only"}],
        "reference_aircraft":"60 kg hexacopter",
    }
    return file,receipt,mapping

def test_m2630_fallback_only_official_provider_urls():
    provider={
        "id":7643456,"doi":"10.5281/zenodo.7643456",
        "metadata":{"title":"Drone onboard multi-modal sensor dataset"},
        "files":[{"key":"source CSV.csv","size":15000000,"checksum":"md5:e2f188e8f5cbf498c7009f422d401207"}],
    }
    candidate=inspect_zenodo_m300_record(provider)
    plan=plan_original_zenodo_download(candidate,source_use_review_reference="SYNTHETIC research rights review only")
    urls=_official_source_urls(plan)
    assert len(urls)==2
    assert all(url.startswith("https://zenodo.org/") for url in urls)
    bad={**plan,"official_constructed_content_url":"https://evil.example/source"}
    with pytest.raises(ValueError,match="canonical"):
        _official_source_urls(bad)

def test_m2631_exact_source_missingness_audit(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    result=quality.audit_original_m300_field_quality(file,receipt)
    assert result["records_scanned_without_modification"]==6
    assert result["columns"][1]["original_label"]=="voltage_mV"
    assert not result["has_missing_cells"]
    assert not result["all_units_or_timebases_known"]
    before=file.read_bytes()
    assert file.read_bytes()==before

def test_m2631_hash_mismatch_and_missingness(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match="checksum"):
        quality.audit_original_m300_field_quality(file,{**receipt,"computed_original_sha256":"a"*64})
    raw=file.read_bytes().replace(b";SYNTHETIC\n",b";\n")
    file.write_bytes(raw)
    monkeypatch.setattr(quality,"EXPECTED_MD5",md5(raw).hexdigest())
    receipt.update(actual_source_bytes=len(raw),computed_original_sha256=sha256(raw).hexdigest())
    r=quality.audit_original_m300_field_quality(file,receipt)
    assert r["has_missing_cells"]
    assert r["columns"][3]["blank_count"]==6

def test_m2632_time_segments_keep_contiguous_blocks_not_flights(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    x=audit_original_m300_time_segments(file,receipt,
        original_time_column="clock_ms",original_time_unit="ms",
        declared_max_sample_gap_s=.2)
    assert len(x["contiguous_blocks"])==1
    assert x["blocks_with_sufficient_rows"]==1
    assert not x["distinct_flights_or_original_clock_authenticated"]

def test_m2632_backward_clock_rejected(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    raw=file.read_bytes().replace(b"1200;24002",b"1100;24002")
    file.write_bytes(raw)
    monkeypatch.setattr(quality,"EXPECTED_MD5",md5(raw).hexdigest())
    receipt.update(actual_source_bytes=len(raw),computed_original_sha256=sha256(raw).hexdigest())
    with pytest.raises(ValueError,match="duplicate or nonmonotone"):
        audit_original_m300_time_segments(file,receipt,
            original_time_column="clock_ms",original_time_unit="ms",
            declared_max_sample_gap_s=.2)

def test_m2633_declared_channel_conversion_magnitude_not_calibration(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    result=inspect_declared_original_m300_channel(file,receipt,
        **mapping["channel_mappings"][0])
    assert result["samples_checked"]==6
    assert result["minimum_in_declared_base_unit"]=="24.000"
    assert not result["source_units_or_sensor_calibration_independently_authenticated"]

def test_m2633_reject_unknown_column_or_unit(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    props=mapping["channel_mappings"][0]
    with pytest.raises(ValueError,match="observed original"):
        inspect_declared_original_m300_channel(file,receipt,
            **{**props,"original_column":"not_in_source"})
    with pytest.raises(ValueError,match="supported channel"):
        inspect_declared_original_m300_channel(file,receipt,
            **{**props,"claimed_original_unit":"invented_unverified"})

def test_m2634_deterministic_report_and_ineligible_full_vehicle(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    baseline=deepcopy(mapping)
    one=build_original_m300_exploratory_report(file,receipt,**mapping)
    two=build_original_m300_exploratory_report(file,receipt,**mapping)
    assert one["reproducible_exploratory_report_sha256"]==two["reproducible_exploratory_report_sha256"]
    assert one["original_quality"]["records_scanned_without_modification"]==6
    assert not one["eligible_for_full_60kg_hexacopter_physical_validation"]
    assert not one["flight_release_authorized"]
    assert baseline==mapping

def test_m2634_duplicate_mapping_refused(tmp_path,monkeypatch):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    mapping["channel_mappings"].append(deepcopy(mapping["channel_mappings"][0]))
    with pytest.raises(ValueError,match="duplicate original"):
        build_original_m300_exploratory_report(file,receipt,**mapping)

def test_m2634_cli_pinned_report(tmp_path,monkeypatch,capsys):
    file,receipt,mapping=fixture(tmp_path,monkeypatch)
    rp=tmp_path/"receipt.json"
    mp=tmp_path/"mapping.json"
    rp.write_text(json.dumps(receipt))
    mp.write_text(json.dumps(mapping))
    script=Path(__file__).resolve().parents[2]/"scripts"/"profile_zenodo_m300_original.py"
    spec=util.spec_from_file_location("m300_profiling_cli",script)
    module=util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args=["profile-local","--original-file",str(file),
          "--receipt-json",str(rp),"--receipt-sha256",sha256(rp.read_bytes()).hexdigest(),
          "--mapping-json",str(mp),"--mapping-sha256",sha256(mp.read_bytes()).hexdigest()]
    assert module.main(args)==0
    output=json.loads(capsys.readouterr().out)
    assert not output["flight_release_authorized"]
    assert output["status"]=="SOURCE_BYTES_CONSISTENT_FOR_EXPLORATION_HARDWARE_UNMATCHED"
    assert module.main(args[:-1]+["a"*64])==2
