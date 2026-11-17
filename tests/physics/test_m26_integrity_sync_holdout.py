"""M26.5–M26.7 synthetic original-file and clock/partition regression tests."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256

import pytest

from physics.validation.source_completeness import audit_source_completeness
from physics.validation.flight_clock_alignment import audit_same_flight_clock_alignment
from physics.validation.flight_holdout_preflight import prepare_whole_flight_holdout_manifest


def fixture(tmp_path):
    files=[]
    for flight, channels in [
        ("flight0", ("rotor_rpm", "pressure_pa")),
        ("flight1", ("rotor_rpm",)),
        ("flight2", ("rotor_rpm",)),
    ]:
        d=tmp_path/flight
        d.mkdir()
        for channel in channels:
            raw=("t_s,"+channel+"\n"+
                "".join(f"{1+i/10:.1f},{2500+i+(0 if channel=='rotor_rpm' else 101000)+(int(flight[-1])*3)}\n" for i in range(6))).encode()
            name=f"{channel}.csv"
            (d/name).write_bytes(raw)
            files.append({
                "relative_path":f"{flight}/{name}",
                "flight_id":flight,
                "sensor_family":channel,
                "declared_channels":[channel],
                "original_sha256":sha256(raw).hexdigest(),
                "original_byte_count":len(raw),
                "calibration_reference":"synthetic claimed calibration",
                "clock_reference":"synthetic claimed clock",
                "source_notes":"synthetic, no real flight",
            })
    return {
        "schema_version":"1.0", "archive_id":"synthetic_multiflight",
        "publication_reference":"fictional paper",
        "archive_record_reference":"fictional data repository",
        "source_permission":None,
        "declared_vehicle_identity":"fictional P80III vehicle",
        "files":files,
    }


def clocks():
    return [
        {"relative_path":"flight0/rotor_rpm.csv","channel":"rotor_rpm",
         "offset_to_shared_clock_s":0.0,"offset_hard_error_s":.002,
         "maximum_sample_gap_s":.2},
        {"relative_path":"flight0/pressure_pa.csv","channel":"pressure_pa",
         "offset_to_shared_clock_s":0.0,"offset_hard_error_s":.003,
         "maximum_sample_gap_s":.2},
    ]


def splits(manifest):
    ids=["flight0","flight1","flight2"]
    roles=["calibration","holdout","holdout"]
    return [{
        "flight_id":id_, "experimental_group_id":f"group{i}",
        "partition":roles[i],
        "source_file_sha256":next(f["original_sha256"] for f in manifest["files"] if f["flight_id"]==id_),
        "operating_regime_id":"synthetic_hover",
        "first_revealed_utc": "2026-11-01T00:00:00Z" if i==0 else "2026-11-16T00:00:00Z",
    } for i,id_ in enumerate(ids)]


def holdout(tmp_path,manifest,partition=None):
    return prepare_whole_flight_holdout_manifest(
        tmp_path,manifest,frozen_model_git_sha="a"*40,
        frozen_protocol_sha256="b"*64,
        preregistered_utc="2026-11-10T00:00:00Z",
        frozen_model_utc="2026-11-12T00:00:00Z",
        partitions=splits(manifest) if partition is None else partition,
    )


def test_m265_all_originals_hashed_without_physical_certification(tmp_path):
    m=fixture(tmp_path)
    previous=deepcopy(m)
    r=audit_source_completeness(tmp_path,m)
    assert m==previous
    assert r["whole_archive_files_checked"]==4
    assert r["all_present_files_accounted_for"]
    assert len(r["canonical_file_inventory_sha256"])==64
    assert not r["physical_measurements_validated"]
    assert not r["all_declared_flights_independently_verified"]


def test_m265_unlisted_file_and_symlink_refused(tmp_path):
    m=fixture(tmp_path)
    (tmp_path/"flight0"/"extra.csv").write_bytes(b"unknown")
    with pytest.raises(ValueError,match="undeclared"):
        audit_source_completeness(tmp_path,m)
    (tmp_path/"flight0"/"extra.csv").unlink()
    (tmp_path/"flight0"/"link.csv").symlink_to(tmp_path/"flight1"/"rotor_rpm.csv")
    with pytest.raises(ValueError,match="symlink"):
        audit_source_completeness(tmp_path,m)


def test_m265_cross_flight_identical_bytes_refused(tmp_path):
    m=fixture(tmp_path)
    src=(tmp_path/"flight0"/"rotor_rpm.csv").read_bytes()
    target=tmp_path/"flight1"/"rotor_rpm.csv"
    target.write_bytes(src)
    row=next(x for x in m["files"] if x["relative_path"]=="flight1/rotor_rpm.csv")
    row["original_byte_count"]=len(src)
    row["original_sha256"]=sha256(src).hexdigest()
    with pytest.raises(ValueError,match="identical original source bytes"):
        audit_source_completeness(tmp_path,m)


def test_m266_unique_sample_pairing_under_reported_clock_bounds(tmp_path):
    m=fixture(tmp_path)
    a,b=clocks()
    result=audit_same_flight_clock_alignment(
        tmp_path,m,source_a=a,source_b=b,
        maximum_joint_time_difference_s=.015,
    )
    assert result["matched_original_pairs"]==6
    assert result["minimum_pairs_met"]
    assert result["maximum_worst_case_time_difference_s"]==pytest.approx(.005)
    assert result["sample_indices_are_unique_and_monotonic"]
    assert not result["actual_sensor_sync_measured_independently"]


def test_m266_clock_uncertainty_alone_prevents_alignment(tmp_path):
    m=fixture(tmp_path)
    a,b=clocks()
    a["offset_hard_error_s"]=.04
    b["offset_hard_error_s"]=.04
    r=audit_same_flight_clock_alignment(
        tmp_path,m,source_a=a,source_b=b,maximum_joint_time_difference_s=.01)
    assert not r["minimum_pairs_met"]
    assert r["status"]=="SENSOR_CLOCK_ALIGNMENT_NOT_ESTABLISHED"


def test_m266_cross_flight_pair_refused(tmp_path):
    m=fixture(tmp_path)
    a,b=clocks()
    b["relative_path"]="flight1/rotor_rpm.csv"
    b["channel"]="rotor_rpm"
    with pytest.raises(ValueError,match="cross-flight"):
        audit_same_flight_clock_alignment(
            tmp_path,m,source_a=a,source_b=b,
            maximum_joint_time_difference_s=.02)


def test_m266_source_tamper_before_time_alignment_refused(tmp_path):
    m=fixture(tmp_path)
    a,b=clocks()
    path=tmp_path/"flight0"/"pressure_pa.csv"
    path.write_bytes(path.read_bytes().replace(b"103500",b"103501"))
    # Even if fixture's chosen substring does not occur, force a changed byte:
    path.write_bytes(path.read_bytes()+b"x")
    with pytest.raises(ValueError,match="original byte count|SHA-256"):
        audit_same_flight_clock_alignment(tmp_path,m,source_a=a,source_b=b,
                                          maximum_joint_time_difference_s=.02)


def test_m266_wrong_source_unit_or_absent_calibration_refused(tmp_path):
    m=fixture(tmp_path)
    a,b=clocks()
    next(x for x in m["files"] if x["relative_path"]==b["relative_path"])["calibration_reference"]=None
    with pytest.raises(ValueError,match="clock, calibration"):
        audit_same_flight_clock_alignment(tmp_path,m,source_a=a,source_b=b,
                                          maximum_joint_time_difference_s=.02)


def test_m267_frozen_whole_flight_groups_are_operator_declarations_only(tmp_path):
    m=fixture(tmp_path)
    r=holdout(tmp_path,m)
    assert r["declared_flight_count"]==3
    assert r["calibration_group_ids"]==["group0"]
    assert r["holdout_group_ids"]==["group1","group2"]
    assert len(r["canonical_split_sha256"])==64
    assert not r["frozen_timestamps_independently_authenticated"]
    assert not r["actual_independent_prediction_validation_completed"]
    assert not r["physical_release_authorized"]


def test_m267_same_group_calibration_and_holdout_refused(tmp_path):
    m=fixture(tmp_path)
    p=splits(m)
    p[1]["experimental_group_id"]="group0"
    with pytest.raises(ValueError,match="same whole experimental group"):
        holdout(tmp_path,m,p)


def test_m267_unfrozen_holdout_or_missing_flight_refused(tmp_path):
    m=fixture(tmp_path)
    p=splits(m)
    p[1]["first_revealed_utc"]="2026-11-11T00:00:00Z"
    with pytest.raises(ValueError,match="after the frozen model"):
        holdout(tmp_path,m,p)
    p=splits(m)[:2]
    with pytest.raises(ValueError,match="all declared original flight"):
        holdout(tmp_path,m,p)


def test_m267_swapped_source_digest_cannot_pass_as_another_flight(tmp_path):
    m=fixture(tmp_path)
    p=splits(m)
    p[2]["source_file_sha256"]=p[0]["source_file_sha256"]
    with pytest.raises(ValueError,match="correspond to an original declared file"):
        holdout(tmp_path,m,p)


def test_m267_invalid_freeze_and_malformed_timestamps_refused(tmp_path):
    m=fixture(tmp_path)
    p=splits(m)
    p[1]["first_revealed_utc"]="2026-11-16T00:00:00+05:30"
    with pytest.raises(ValueError,match="UTC timestamp"):
        holdout(tmp_path,m,p)
    with pytest.raises(ValueError,match="preregistration"):
        prepare_whole_flight_holdout_manifest(
            tmp_path,m,frozen_model_git_sha="a"*40,
            frozen_protocol_sha256="b"*64,
            preregistered_utc="2026-11-15T00:00:00Z",
            frozen_model_utc="2026-11-12T00:00:00Z",
            partitions=splits(m),
        )
