"""M19 ingestion fixtures are SYNTHETIC, including cases labelled physical.

These tests verify audit behavior, NOT an actual laboratory campaign.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from physics.validation.telemetry_ingestion import (
    TelemetryManifest,
    audit_telemetry_bundle,
    audit_telemetry_csv,
    audit_telemetry_directory,
    audit_partition,
)


def fake_csv(*, voltage=12, times=(0, 1, 2, 3, 4, 5), bad=None):
    rows = ["t_s,terminal_voltage_v,current_a"]
    rows += [f"{t},{voltage},2" for t in times]
    if bad:
        rows[bad[0]] = bad[1]
    return ("\n".join(rows) + "\n").encode("utf-8")


def fake_manifest(raw: bytes, *,
                  id="synthetic_run_a", role="calibration",
                  kind="synthetic_fixture", group="first", **overrides):
    fields = {
        "schema_version": "1.0", "dataset_id": id, "dataset_kind": kind,
        "partition_role": role, "experiment_id": f"experiment_{group}",
        "recording_id": f"recording_{group}", "vehicle_id": f"vehicle_{group}",
        "battery_id": f"pack_{group}", "source_reference": "synthetic math verification",
        "license_or_permission": "self-generated synthetic fixture",
        "instrument_calibration_reference": None,
        "clock_alignment_error_bound_s": None,
        "filename": "trace.csv", "raw_sha256": sha256(raw).hexdigest(),
        "expected_samples": 6, "predeclared_max_sample_gap_s": 2,
        "columns": ["t_s", "terminal_voltage_v", "current_a"],
    }
    fields.update(overrides)
    return TelemetryManifest.model_validate(fields)


def test_synthetic_trace_has_correct_energy_and_no_physical_promotion():
    raw = fake_csv()
    result = audit_telemetry_csv(fake_manifest(raw), raw)
    assert result["status"] == "SYNTHETIC_VERIFICATION_ONLY"
    assert result["rows"] == 6
    assert result["observations"]["duration_s"] == 5
    assert result["observations"]["trapezoidal_reported_charge_ah"] == pytest.approx(10 / 3600)
    assert result["observations"]["trapezoidal_reported_energy_wh"] == pytest.approx(120 / 3600)
    assert result["quality"]["strictly_increasing_timestamps"]
    assert not result["physically_validated_model"]
    assert result["raw_sha256_verified_against_manifest"] == sha256(raw).hexdigest()


def test_operator_reported_physical_trace_can_pass_audit_but_not_validation():
    raw = fake_csv()
    manifest = fake_manifest(raw, kind="reported_physical_measurements")
    result = audit_telemetry_csv(manifest, raw)
    assert result["status"] == "OBSERVATIONS_AUDITED_PROVENANCE_UNAUTHENTICATED"
    assert result["predicted_aircraft_performance_error"] is None
    assert result["quality"]["instrument_calibration_reference_supplied"] is False
    assert not result["physically_validated_model"]


def test_sparse_sample_gaps_preclude_time_integration():
    raw = fake_csv(times=(0, 1, 2, 3, 4, 50))
    result = audit_telemetry_csv(fake_manifest(raw), raw)
    assert not result["quality"]["sampling_interval_within_predeclared_bound"]
    assert result["observations"]["trapezoidal_reported_charge_ah"] is None
    assert result["observations"]["trapezoidal_reported_energy_wh"] is None


@pytest.mark.parametrize("mutate,error", [
    (lambda d: fake_csv(bad=(2, "1,12,NaN")), "nonfinite"),
    (lambda d: fake_csv(bad=(2, "1,12,inf")), "nonfinite"),
    (lambda d: fake_csv(bad=(2, "1,,2")), "missing"),
    (lambda d: fake_csv(bad=(2, "1,12,-2")), "bounds"),
    (lambda d: fake_csv(bad=(2, "1,0,2")), "bounds"),
    (lambda d: fake_csv(times=(0, 1, 1, 3, 4, 5)), "strictly increasing"),
    (lambda d: fake_csv(times=(1, 2, 3, 4, 5, 6)), "exactly zero"),
    (lambda d: b"bad_time,terminal_voltage_v,current_a\n"+d.split(b"\n", 1)[1], "columns"),
    (lambda d: b"t_s,terminal_voltage_v,current_a\n"+b"".join(f"{i},12,2\n".encode("utf-8") for i in range(5)), "expected"),
    (lambda d: d.replace(b"12,2", b"12,3", 1), "SHA-256"),
])
def test_corruption_and_unsupported_time_rejected(mutate, error):
    good = fake_csv()
    changed = mutate(good)
    # Rehash malformed-but-genuine inputs so syntax validation is reached.
    # Only the explicit tampering case must fail at the integrity check.
    manifest = fake_manifest(good if error == "SHA-256" else changed)
    with pytest.raises(ValueError, match=error):
        audit_telemetry_csv(manifest, changed)


@pytest.mark.parametrize("mutation", [
    lambda d: d.update({"dataset_id": "../outside"}),
    lambda d: d.update({"filename": "../outside.csv"}),
    lambda d: d.update({"raw_sha256": "0" * 63}),
    lambda d: d.update({"expected_samples": -1}),
    lambda d: d.update({"predeclared_max_sample_gap_s": 0}),
    lambda d: d.update({"clock_alignment_error_bound_s": float("nan")}),
    lambda d: d.update({"columns": ["t_s", "terminal_voltage_v", "temperature_c"]}),
    lambda d: d.update({"columns": ["t_s", "terminal_voltage_v", "current_a", "current_a"]}),
    lambda d: d.update({"source_reference": "  "}),
    lambda d: d.update({"unrecognized": True}),
])
def test_manifest_schema_rejects_ambiguous_or_untrusted_inputs(mutation):
    raw = fake_csv()
    fields = fake_manifest(raw).model_dump()
    mutation(fields)
    with pytest.raises(ValidationError):
        TelemetryManifest.model_validate(fields)


def test_disjoint_synthetic_runs_never_promoted_to_physical_validation():
    a, b = fake_csv(voltage=12), fake_csv(voltage=11)
    x = fake_manifest(a, id="run_a", group="A", role="calibration")
    y = fake_manifest(b, id="run_b", group="B", role="holdout")
    report = audit_telemetry_bundle([(x, a), (y, b)])
    assert report["partition"]["status"] == "SYNTHETIC_OR_MIXED_DATASET_NO_PHYSICAL_VALIDATION"
    assert report["partition"]["cross_partition_collisions"] == []
    assert not report["near_real_world_simulation_accuracy_established"]


def test_declared_physical_disjointness_is_not_independent_authentication():
    a, b = fake_csv(voltage=12), fake_csv(voltage=11)
    x = fake_manifest(a, id="run_a", kind="reported_physical_measurements", group="A")
    y = fake_manifest(b, id="run_b", kind="reported_physical_measurements", role="holdout", group="B")
    report = audit_telemetry_bundle([(x, a), (y, b)])
    assert report["partition"]["status"] == "DECLARED_DISJOINT_SPLIT_NOT_INDEPENDENTLY_AUTHENTICATED"
    assert report["partition"]["physical_validation_established"] is False


@pytest.mark.parametrize("shared_field", [
    "experiment_id", "recording_id", "vehicle_id", "battery_id",
])
def test_cross_partition_leakage_flags_identical_group_identifiers(shared_field):
    a, b = fake_csv(voltage=12), fake_csv(voltage=11)
    x = fake_manifest(a, id="run_a", group="A")
    y_fields = fake_manifest(b, id="run_b", role="holdout", group="B").model_dump()
    y_fields[shared_field] = getattr(x, shared_field)
    y = TelemetryManifest.model_validate(y_fields)
    p = audit_telemetry_bundle([(x, a), (y, b)])["partition"]
    assert p["status"] == "CROSS_PARTITION_LEAKAGE_DECLARED"
    assert shared_field in p["cross_partition_collisions"][0]["shared_identifiers"]
    assert not p["physical_validation_established"]


def test_duplicate_original_file_also_flags_leakage():
    a = fake_csv()
    x = fake_manifest(a, id="run_a", group="A")
    y = fake_manifest(a, id="run_b", role="holdout", group="B")
    p = audit_telemetry_bundle([(x, a), (y, a)])["partition"]
    assert p["status"] == "CROSS_PARTITION_LEAKAGE_DECLARED"
    assert "raw_sha256" in p["cross_partition_collisions"][0]["shared_identifiers"]


def test_directory_audit_checks_files_and_does_not_mutate(tmp_path: Path):
    root = tmp_path / "datasets"
    root.mkdir()
    raw = fake_csv()
    m = fake_manifest(raw, id="synthetic_run_a")
    folder = root / m.dataset_id
    folder.mkdir()
    (folder / "manifest.json").write_text(m.model_dump_json())
    (folder / m.filename).write_bytes(raw)
    before = (folder / m.filename).read_bytes()
    r = audit_telemetry_directory(root)
    assert len(r["datasets"]) == 1
    assert r["partition"]["status"] == "NO_COMPLETE_CALIBRATION_HOLDOUT_SPLIT"
    assert before == (folder / m.filename).read_bytes()


def test_directory_refuses_symlink_and_file_escape(tmp_path: Path):
    root = tmp_path / "datasets"
    root.mkdir()
    raw = fake_csv()
    m = fake_manifest(raw)
    folder = root / m.dataset_id
    folder.mkdir()
    (folder / "manifest.json").write_text(m.model_dump_json())
    target = tmp_path / "raw.csv"
    target.write_bytes(raw)
    (folder / m.filename).symlink_to(target)
    with pytest.raises(ValueError, match="symlinked CSV"):
        audit_telemetry_directory(root)


def test_no_imported_physical_sources_is_explicit():
    assert audit_partition([])["status"] == "NO_EVIDENCE_IMPORTED"
