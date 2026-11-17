"""Synthetic M26.17–19 vendor CSV adaptation; NO genuine instrument records."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from importlib import util
from pathlib import Path
import json

import pytest

from physics.validation.flight_vendor_csv_inspector import inspect_original_vendor_csv
from physics.validation.flight_explicit_csv_conversion import (
    derive_original_vendor_csv_bytes, write_derived_vendor_csv,
)
from physics.validation.flight_derived_csv_replay import replay_derived_flight_csv


def specimen(tmp_path):
    original_root = tmp_path / "untouched_original"
    (original_root / "flight01").mkdir(parents=True)
    original = (
        "Clock_ms,Optical motor Hz,Probe_F,unused_label\n"
        + "".join(f"{1000+100*k},{10+k},{68+k},{k}\n" for k in range(6))
    ).encode("utf-8")
    raw_file = original_root / "flight01" / "vendor recording.csv"
    raw_file.write_bytes(original)
    manifest = {
        "schema_version": "1.0",
        "archive_id": "synthetic_vendor_csv_not_physical",
        "publication_reference": "synthetic fixture",
        "archive_record_reference": "synthetic data source not a publication",
        "source_permission": None,
        "declared_vehicle_identity": "hypothetical airframe",
        "files": [{
            "relative_path": "flight01/vendor recording.csv",
            "flight_id": "flight01",
            "sensor_family": "vendor_instrument",
            "declared_channels": [],
            "original_sha256": sha256(original).hexdigest(),
            "original_byte_count": len(original),
            "calibration_reference": None,
            "clock_reference": None,
            "source_notes": "original native CSV in fictitious units",
        }],
    }
    mapping = {
        "source_relative_path": "flight01/vendor recording.csv",
        "time_column": "Clock_ms",
        "time_unit": "ms",
        "channel_column": "Optical motor Hz",
        "output_channel": "rotor_rpm",
        "channel_unit": "Hz",
        "mapping_source_reference": "synthetic invented unit note",
    }
    return original_root, manifest, mapping, raw_file


def _outputs(tmp_path):
    return tmp_path / "derived.csv", tmp_path / "derived.provenance.json"


def test_m2617_inventory_original_vendor_labels_without_guessing_units(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    before = raw.read_bytes()
    info = inspect_original_vendor_csv(
        root, manifest, relative_path=mapping["source_relative_path"]
    )
    assert info["original_record_count"] == 6
    assert info["exact_original_column_labels"] == [
        "Clock_ms", "Optical motor Hz", "Probe_F", "unused_label"
    ]
    assert info["original_file_sha256"] == sha256(before).hexdigest()
    assert not info["original_channel_units_verified"]
    assert not info["original_recorder_custody_authenticated"]
    assert raw.read_bytes() == before


def test_m2618_explicit_hz_to_rpm_and_ms_to_s_is_deterministic(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    existing = deepcopy(manifest)
    data, report = derive_original_vendor_csv_bytes(
        root, manifest, mapping=mapping
    )
    assert manifest == existing
    assert data.decode().startswith("t_s,rotor_rpm\n1,600\n1.1,660\n")
    assert report["derived_sample_count"] == 6
    assert report["unmapped_source_columns_not_interpreted"] == [
        "Probe_F", "unused_label"
    ]
    assert report["output_channel"] == "rotor_rpm"
    assert len(report["transformation_spec_sha256"]) == 64
    assert not report["raw_file_origin_or_license_independently_authenticated"]
    assert not report["physically_validated_simulation"]


def test_m2618_degrees_fahrenheit_to_celsius_requires_explicit_column(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    mapping["channel_column"] = "Probe_F"
    mapping["output_channel"] = "temperature_c"
    mapping["channel_unit"] = "degF"
    data, report = derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)
    assert data.decode().startswith("t_s,temperature_c\n1,20\n1.1,20.55555")
    assert report["output_channel"] == "temperature_c"


def test_m2618_reject_unknown_units_missing_columns_and_ambiguous_time(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    mapping["channel_unit"] = "rpm"  # actual synthetic data in Hz; cannot silently relabel
    # rpm is a supported declared unit, so source authority must be authenticated externally:
    data, report = derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)
    assert not report["source_instrument_units_and_calibration_independently_verified"]
    mapping["channel_unit"] = "rad/s"
    with pytest.raises(ValueError, match="incompatible|unknown"):
        derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)
    mapping["channel_unit"] = "Hz"
    mapping["time_column"] = "Unknown software timestamp"
    with pytest.raises(ValueError, match="original CSV headers"):
        derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)
    mapping["time_column"] = mapping["channel_column"]
    with pytest.raises(ValueError, match="distinct"):
        derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)


def test_m2618_timestamp_reversal_and_missing_cells_fail_closed(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    altered = raw.read_bytes().replace(b"1200,12", b"1100,12", 1)
    raw.write_bytes(altered)
    manifest["files"][0]["original_sha256"] = sha256(altered).hexdigest()
    manifest["files"][0]["original_byte_count"] = len(altered)
    with pytest.raises(ValueError, match="strictly increase"):
        derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)
    altered = raw.read_bytes().replace(b"1100,12", b"1200,", 1)
    raw.write_bytes(altered)
    manifest["files"][0]["original_sha256"] = sha256(altered).hexdigest()
    manifest["files"][0]["original_byte_count"] = len(altered)
    with pytest.raises(ValueError, match="invalid|missing|extra"):
        derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)


def test_m2619_write_and_replay_original_bytes_and_sidecar(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    original = raw.read_bytes()
    output, sidecar = _outputs(tmp_path)
    report = write_derived_vendor_csv(
        root, manifest, mapping=mapping,
        derived_csv_path=output, provenance_json_path=sidecar,
    )
    replay = replay_derived_flight_csv(
        root, manifest, derived_csv_path=output, provenance_json_path=sidecar,
    )
    assert replay["same_original_bytes_and_transformation_reproduced"]
    assert replay["original_source_sha256"] == sha256(original).hexdigest()
    assert replay["derived_csv_sha256"] == report["derived_csv_sha256"]
    assert output.read_text().startswith("t_s,rotor_rpm\n")
    assert raw.read_bytes() == original
    assert not replay["physical_prediction_accuracy_established"]
    assert not replay["flight_release_authorized"]
    with pytest.raises(ValueError, match="new non-symlink"):
        write_derived_vendor_csv(
            root, manifest, mapping=mapping,
            derived_csv_path=output, provenance_json_path=sidecar,
        )


def test_m2619_tampered_derived_csv_and_false_certification_refused(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    output, sidecar = _outputs(tmp_path)
    write_derived_vendor_csv(
        root, manifest, mapping=mapping,
        derived_csv_path=output, provenance_json_path=sidecar,
    )
    output.write_bytes(output.read_bytes().replace(b"600", b"610"))
    with pytest.raises(ValueError, match="not reproducible"):
        replay_derived_flight_csv(
            root, manifest, derived_csv_path=output,
            provenance_json_path=sidecar,
        )
    # Restore exact output bytes, then add an invented certification claim.
    data, report = derive_original_vendor_csv_bytes(root, manifest, mapping=mapping)
    output.write_bytes(data)
    provenance = json.loads(sidecar.read_text())
    provenance["physically_validated_simulation"] = True
    sidecar.write_text(json.dumps(provenance))
    with pytest.raises(ValueError, match="provenance differs"):
        replay_derived_flight_csv(
            root, manifest, derived_csv_path=output,
            provenance_json_path=sidecar,
        )


def test_m2619_tampered_original_invalidates_derived_record(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    output, sidecar = _outputs(tmp_path)
    write_derived_vendor_csv(
        root, manifest, mapping=mapping,
        derived_csv_path=output, provenance_json_path=sidecar,
    )
    raw.write_bytes(raw.read_bytes()+b"source changed")
    with pytest.raises(ValueError, match="byte count|SHA-256|original"):
        replay_derived_flight_csv(
            root, manifest, derived_csv_path=output,
            provenance_json_path=sidecar,
        )


def test_m2619_output_must_not_be_written_inside_original_tree(tmp_path):
    root, manifest, mapping, raw = specimen(tmp_path)
    with pytest.raises(ValueError, match="outside original root"):
        write_derived_vendor_csv(
            root, manifest, mapping=mapping,
            derived_csv_path=root / "derived.csv",
            provenance_json_path=tmp_path / "sidecar.json",
        )
    assert not (root/"derived.csv").exists()


def _cli():
    p = Path(__file__).resolve().parents[2] / "scripts" / "prepare_original_instrument_csv.py"
    spec = util.spec_from_file_location("aeroforge_vendor_csv_cli", p)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.cli


def test_cli_full_inspect_convert_replay_using_exact_pinned_files(tmp_path, capsys):
    root, manifest, mapping, raw = specimen(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    mapping_path = tmp_path / "mapping.json"
    manifest_path.write_text(json.dumps(manifest))
    mapping_path.write_text(json.dumps(mapping))
    common = [
        "--original-root", str(root),
        "--source-manifest-json", str(manifest_path),
        "--source-manifest-sha256", sha256(manifest_path.read_bytes()).hexdigest(),
    ]
    assert _cli()(common + [
        "inspect", "--relative-path", mapping["source_relative_path"]
    ]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["original_record_count"] == 6
    output, sidecar = _outputs(tmp_path)
    assert _cli()(common + [
        "convert", "--mapping-json", str(mapping_path),
        "--mapping-sha256", sha256(mapping_path.read_bytes()).hexdigest(),
        "--derived-csv", str(output),
        "--provenance-json", str(sidecar),
    ]) == 0
    converted = json.loads(capsys.readouterr().out)
    assert converted["status"].startswith("DERIVED_")
    assert _cli()(common + [
        "verify", "--derived-csv", str(output), "--provenance-json", str(sidecar),
    ]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert verified["same_original_bytes_and_transformation_reproduced"]
    assert not verified["physical_prediction_accuracy_established"]


def test_cli_changed_source_manifest_pin_causes_nonzero_exit(tmp_path, capsys):
    root, manifest, mapping, raw = specimen(tmp_path)
    manifest_path = tmp_path/"manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    assert _cli()([
        "--original-root", str(root),
        "--source-manifest-json", str(manifest_path),
        "--source-manifest-sha256", "f"*64,
        "inspect", "--relative-path", mapping["source_relative_path"],
    ]) == 2
    assert "SHA-256 mismatch" in capsys.readouterr().err
