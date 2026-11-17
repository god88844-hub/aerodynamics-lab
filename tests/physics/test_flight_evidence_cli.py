"""End-to-end CLI smoke tests use only mock original-file bytes."""
from importlib import util
from hashlib import sha256
from pathlib import Path
import json


def cli():
    path = Path(__file__).resolve().parents[2] / "scripts" / "audit_flight_evidence_channels.py"
    spec = util.spec_from_file_location("aeroforge_M26_234_cli", path)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.cli


def test_cli_source_draft_csv_and_coverage_are_synthetic_and_noncertifying(tmp_path,capsys):
    source = tmp_path/"originals"
    source.mkdir()
    for k in range(2):
        directory = source/f"flight{k}"
        directory.mkdir()
        data = ("t_s,rotor_rpm\n" +
                "".join(f"{k*10+i*.1:.1f},{2500+i+k}\n" for i in range(5))).encode()
        (directory/"real_original.csv").write_bytes(data)
    assignments = {
        "archive_id":"synthetic_unverified",
        "publication_reference":"hypothetical independent data",
        "archive_record_reference":"offline test only",
        "declared_vehicle_identity":"hypothetical drone",
        "source_permission":"operator claims permission",
        "assignments":[{
            "relative_path":f"flight{k}/real_original.csv",
            "flight_id":f"flight{k}","sensor_family":"rotor",
            "declared_channels":["rotor_rpm"],
            "calibration_reference":"operator claims sensor calibration",
            "clock_reference":"operator claims synchronized clock",
            "source_notes":None,
        } for k in range(2)],
    }
    args_file = tmp_path/"assignments.json"
    args_file.write_text(json.dumps(assignments))
    draft_path = tmp_path/"draft.json"
    assert cli()(["--root",str(source),"--output",str(draft_path),"draft",
                  "--assignments-json",str(args_file)])==0
    report=json.loads(capsys.readouterr().out)
    manifest=report["manifest"]
    assert manifest["files"][0]["original_sha256"]==sha256(
        (source/"flight0"/"real_original.csv").read_bytes()).hexdigest()
    assert not report["physical_flight_measurements_validated"]
    manifest_path=tmp_path/"source_manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    channels_path=tmp_path/"channels.json"
    channels_path.write_text(json.dumps({"rotor_rpm":"rpm"}))
    assert cli()(["--root",str(source),"csv","--manifest",str(manifest_path),
                  "--relative-path","flight0/real_original.csv",
                  "--channels-json",str(channels_path),"--maximum-gap-s","0.2"])==0
    parsed=json.loads(capsys.readouterr().out)
    assert parsed["original_csv_sample_count"]==5
    assert not parsed["physical_sensor_measurements_authenticated"]
    sources_path=tmp_path/"sources.json"
    sources_path.write_text(json.dumps([{
        "relative_path":f"flight{k}/real_original.csv",
        "channels_with_units":{"rotor_rpm":"rpm"},
        "maximum_declared_sample_gap_s":0.2,
    } for k in range(2)]))
    assert cli()(["--root",str(source),"coverage","--manifest",str(manifest_path),
                  "--sources-json",str(sources_path),"--required-channels","rotor_rpm"])==0
    covered=json.loads(capsys.readouterr().out)
    assert covered["operator_reported_coverage_consistent"]
    assert not covered["full_vehicle_physical_prediction_validated"]


def test_cli_refuses_to_overwrite_original_source_file(tmp_path,capsys):
    source=tmp_path/"originals"
    source.mkdir()
    data=b"t_s,rotor_rpm\n0,1\n1,2\n2,3\n3,4\n4,5\n"
    (source/"original.csv").write_bytes(data)
    arguments={
        "archive_id":"synthetic", "publication_reference":"fiction",
        "archive_record_reference":"fiction", "declared_vehicle_identity":"fiction",
        "source_permission":None,
        "assignments":[{
            "relative_path":"original.csv","flight_id":"flight1",
            "sensor_family":"rotor","declared_channels":["rotor_rpm"],
            "calibration_reference":None,"clock_reference":None,"source_notes":None,
        }],
    }
    source_json=tmp_path/"draft.json"
    source_json.write_text(json.dumps(arguments))
    assert cli()(["--root",str(source),"--output",str(source/"report.json"),
                  "draft","--assignments-json",str(source_json)])==2
    assert (source/"original.csv").read_bytes()==data
    assert not (source/"report.json").exists()
    assert "FAILED" in capsys.readouterr().err
