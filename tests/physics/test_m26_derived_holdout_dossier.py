"""M26.20-24 tests: synthetic vendor data only, never physical experiments."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import pytest

from physics.validation.flight_explicit_csv_conversion import write_derived_vendor_csv
from physics.validation.derived_observation_admission import admit_derived_observation
from physics.validation.derived_hardware_screen import screen_declared_hardware_match
from physics.validation.derived_holdout_comparison import compare_derived_holdout
from physics.validation.derived_holdout_coverage import audit_derived_holdout_group_coverage
from physics.validation.derived_flight_dossier import build_derived_flight_dossier


def scenario(tmp_path):
    originals=tmp_path/"originals"
    originals.mkdir()
    rows=[]
    partition=[]
    cases=[]
    for i in range(3):
        flight=f"flight{i}"
        folder=originals/flight
        folder.mkdir()
        raw=("original_ms,encoder_Hz\n"+"".join(
            f"{1000+100*j},{40+i+j}\n" for j in range(6))).encode()
        (folder/"native.csv").write_bytes(raw)
        entry={
            "relative_path":f"{flight}/native.csv", "flight_id":flight,
            "sensor_family":"encoder",
            "declared_channels":[],
            "original_sha256":sha256(raw).hexdigest(),
            "original_byte_count":len(raw),
            "calibration_reference":"synthetic claimed certificate",
            "clock_reference":"synthetic claimed clock",
            "source_notes":"synthetic only",
        }
        rows.append(entry)
        partition.append({
            "flight_id":flight,
            "experimental_group_id":f"group{i}",
            "partition":"calibration" if i==0 else "holdout",
            "source_file_sha256":entry["original_sha256"],
            "operating_regime_id":"hover",
            "first_revealed_utc":"2026-01-01T00:00:00Z" if i==0 else "2026-01-05T00:00:00Z",
        })
    manifest={
        "schema_version":"1.0",
        "archive_id":"synthetic_derived_sensors",
        "publication_reference":"test fixture only",
        "archive_record_reference":"not real physical data",
        "source_permission":"operator claimed permissions",
        "declared_vehicle_identity":"synthetic test airframe",
        "files":rows,
    }
    split={
        "frozen_model_git_sha":"a"*40,
        "frozen_protocol_sha256":"b"*64,
        "preregistered_utc":"2026-01-02T00:00:00Z",
        "frozen_model_utc":"2026-01-03T00:00:00Z",
        "partitions":partition,
        "minimum_holdout_groups":2,
    }
    for i in (1,2):
        mapping={
            "source_relative_path":f"flight{i}/native.csv",
            "time_column":"original_ms",
            "time_unit":"ms",
            "channel_column":"encoder_Hz",
            "output_channel":"rotor_rpm",
            "channel_unit":"Hz",
            "mapping_source_reference":"synthetic claimed encoder Hz",
        }
        dpath=tmp_path/f"flight{i}_derived.csv"
        sidecar=tmp_path/f"flight{i}_sidecar.json"
        provenance=write_derived_vendor_csv(
            originals,manifest,mapping=mapping,
            derived_csv_path=dpath,provenance_json_path=sidecar,
        )
        # Prediction numerical test fixture: exact same derived grid and value.
        prediction=("t_s,prediction,lower,upper\n"+"".join(
            f"{1+j/10:.1f},{(40+i+j)*60},{(40+i+j)*60-1},{(40+i+j)*60+1}\n"
            for j in range(6))).encode()
        ppath=tmp_path/f"flight{i}_frozen.csv"
        ppath.write_bytes(prediction)
        cases.append({
            "derived_csv_path":str(dpath),
            "provenance_json_path":str(sidecar),
            "channel":"rotor_rpm",
            "maximum_declared_sample_gap_s":0.2,
            "frozen_prediction_csv_path":str(ppath),
            "frozen_prediction_sha256":sha256(prediction).hexdigest(),
            "measurement_hard_error":0.1,
            "numerical_hard_error":0.1,
            "model_discrepancy_hard_error":0.1,
            "predeclared_max_conservative_error":1.0,
            "predeclared_min_robust_coverage":0.95,
        })
    hardware={
        "aircraft_type":"quadcopter",
        "motor_model":"P80III-KV100",
        "propeller_model":"CF-PROP 30x10.5",
        "esc_model":"sample-ESC",
        "battery_pack_model":"sample-battery",
        "installed_rotor_count":4,
        "mount_configuration_id":"original-test-mount",
        "takeoff_mass_kg":25.,
    }
    measured=dict(hardware,ambient_temperature_c=22.)
    return originals,manifest,split,cases,hardware,measured


def compare(root,manifest,split,one):
    return compare_derived_holdout(root,manifest,holdout_case=split,**one)


def dossier(root,manifest,split,cases,reference,measured):
    return build_derived_flight_dossier(
        root,manifest,holdout_case=split,comparison_cases=cases,
        reference_hardware=reference,measured_hardware=measured,
        maximum_predeclared_mass_fraction_difference=0.05,
        declared_ambient_min_c=15.,declared_ambient_max_c=35.,
        required_regime="hover",required_channel="rotor_rpm",
    )


def test_m2620_admit_original_linked_derived_channel_only(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    old=deepcopy(manifest)
    case=cases[0]
    r=admit_derived_observation(
        root,manifest,derived_csv_path=case["derived_csv_path"],
        provenance_json_path=case["provenance_json_path"],
        output_channel="rotor_rpm",maximum_declared_sample_gap_s=0.2,
    )
    assert manifest==old
    assert r["sample_count"]==6
    assert r["operator_sampling_gap_requirement_met"]
    assert r["original_source_is_derived"]
    assert not r["real_sensor_clock_or_calibration_authenticated"]
    assert not r["physical_measurement_accuracy_established"]


def test_m2620_wrong_channel_or_tampered_source_fails(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    c=cases[0]
    with pytest.raises(ValueError,match="channel differs"):
        admit_derived_observation(
            root,manifest,derived_csv_path=c["derived_csv_path"],
            provenance_json_path=c["provenance_json_path"],
            output_channel="pressure_pa",maximum_declared_sample_gap_s=0.2,
        )
    p=Path(c["derived_csv_path"])
    p.write_bytes(p.read_bytes()+b"source tamper")
    with pytest.raises(ValueError,match="not reproducible"):
        admit_derived_observation(
            root,manifest,derived_csv_path=c["derived_csv_path"],
            provenance_json_path=c["provenance_json_path"],
            output_channel="rotor_rpm",maximum_declared_sample_gap_s=0.2,
        )


def test_m2621_hardware_match_is_only_a_declared_claim(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    r=screen_declared_hardware_match(
        ref,measured,maximum_predeclared_mass_fraction_difference=.05,
        declared_ambient_min_c=15,declared_ambient_max_c=35,
    )
    assert r["eligible_for_conditional_numerical_screen"]
    assert not r["installed_serials_and_hardware_revisions_independently_verified"]
    assert not r["flight_release_authorized"]


def test_m2621_aircraft_class_and_battery_mismatch_block_reuse(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    measured["aircraft_type"]="hexacopter"
    measured["battery_pack_model"]="different-pack"
    r=screen_declared_hardware_match(
        ref,measured,maximum_predeclared_mass_fraction_difference=.05,
        declared_ambient_min_c=15,declared_ambient_max_c=35,
    )
    assert not r["eligible_for_conditional_numerical_screen"]
    assert "aircraft_type" in r["operator_declared_hardware_fields_mismatched"]
    assert "battery_pack_model" in r["operator_declared_hardware_fields_mismatched"]


def test_m2622_comparison_recomputes_metrics_without_evidence_promotion(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    r=compare(root,manifest,split,cases[0])
    assert r["samples_compared"]==6
    assert r["nominal_rmse"]==0.
    assert r["max_conservative_residual"]==pytest.approx(.3)
    assert r["robust_interval_coverage_fraction"]==1.
    assert r["operator_declared_numerical_gate_passed"]
    assert r["source_kind"].startswith("derived")
    assert not r["physical_prediction_equivalence_established"]


def test_m2622_wrong_prediction_grid_and_failed_bound_are_detected(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    c=cases[0]
    p=Path(c["frozen_prediction_csv_path"])
    altered=p.read_bytes().replace(b"1.1,2520",b"1.15,2520")
    p.write_bytes(altered)
    c["frozen_prediction_sha256"]=sha256(altered).hexdigest()
    with pytest.raises(ValueError,match="grid differs"):
        compare(root,manifest,split,c)
    c["frozen_prediction_csv_path"]=cases[1]["frozen_prediction_csv_path"]
    c["frozen_prediction_sha256"]=cases[1]["frozen_prediction_sha256"]
    r=compare(root,manifest,split,c)
    assert not r["operator_declared_numerical_gate_passed"]


def test_m2623_heldout_groups_not_fake_originals(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    r=audit_derived_holdout_group_coverage(
        root,manifest,holdout_case=split,comparison_cases=cases,
        required_regime="hover",required_channel="rotor_rpm",
    )
    assert r["all_numeric_checks_passed"]
    assert r["declared_passing_groups"]==["group1","group2"]
    assert not r["independent_flight_custody_authenticated"]
    assert not r["physical_prediction_validation_completed"]


def test_m2623_one_group_inconclusive_and_duplicate_refused(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    one=audit_derived_holdout_group_coverage(
        root,manifest,holdout_case=split,comparison_cases=cases[:1],
        required_regime="hover",required_channel="rotor_rpm",
    )
    assert one["status"].startswith("INCONCLUSIVE")
    with pytest.raises(ValueError,match="duplicate"):
        audit_derived_holdout_group_coverage(
            root,manifest,holdout_case=split,comparison_cases=cases+[cases[0]],
            required_regime="hover",required_channel="rotor_rpm",
        )


def test_m2624_dossier_reproducible_but_not_certified(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    r=dossier(root,manifest,split,cases,ref,measured)
    assert r["status"]=="CONDITIONAL_DERIVED_NUMERICAL_CONSISTENCY_EXTERNAL_EVIDENCE_MISSING"
    assert len(r["recomputed_dossier_sha256"])==64
    assert not r["decision_equivalent_physical_evidence_established"]
    assert not r["manufacturing_or_flight_release_authorized"]
    assert r["recomputed_dossier_sha256"]==dossier(
        root,manifest,split,list(reversed(cases)),ref,measured
    )["recomputed_dossier_sha256"]


def test_m2624_hardware_mismatch_blocks_conditional_green(tmp_path):
    root,manifest,split,cases,ref,measured=scenario(tmp_path)
    measured["aircraft_type"]="hexacopter"
    r=dossier(root,manifest,split,cases,ref,measured)
    assert r["status"]=="INCONCLUSIVE_INCOMPATIBLE_DECLARED_HARDWARE"
    assert not r["decision_equivalent_physical_evidence_established"]
