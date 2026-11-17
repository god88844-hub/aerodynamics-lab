"""M16 audit of *reported real* PX4 flight telemetry from the cited source.

These tests verify source identity and recorded electrical channel consistency.
They do NOT validate or fit any AeroForge battery or aircraft model.
"""
from pathlib import Path
import json

import pytest

from physics.validation.public_evidence import (
    DATA_DIR, audit_quadplane_battery, get_public_source_inventory,
)


def test_actual_licensed_px4_battery_log_is_bitwise_pinned_and_finite():
    result = audit_quadplane_battery()
    assert result["source"]["git_blob_sha1"] == "1e434d8edcc26d5dfc016a557e24d5c44cffff3c"
    assert result["source"]["bytes"] == 121674
    assert result["source"]["license"] == "CC BY 4.0"
    assert result["quality"]["rows_verified"] == 1442
    assert result["quality"]["numeric_and_finite"]
    assert result["quality"]["counter_monotonic"]
    assert result["quality"]["remaining_fraction_nonincreasing"]
    assert result["source"]["instrument_and_identity_authenticated_by_aeroforge"] is False


def test_real_observed_power_and_discharge_are_not_misreported_as_endurance():
    report = audit_quadplane_battery()
    observations = report["observed"]
    assert observations["voltage_range_v"][0] == pytest.approx(21.646976470947266)
    assert observations["voltage_range_v"][1] == pytest.approx(25.30971336364746)
    assert observations["current_range_a"][1] == pytest.approx(72.45195770263672)
    assert observations["difference_in_reported_discharge_counter_mah"] == pytest.approx(
        2640.931427001953,
    )
    assert observations["peak_sampled_pack_electrical_power_w"] == pytest.approx(
        1596.971942918637,
    )
    assert observations["controller_implied_nominal_capacity_mah_not_independent_measurement"] == pytest.approx(
        10000, rel=1e-5,
    )
    assert observations["power_time_integral_wh"] is None
    assert observations["independently_measured_capacity_ah"] is None
    assert observations["per_row_time_s"] is None
    assert report["validated_flight_prediction_error"] is None
    assert report["near_real_world_equivalence_established"] is False
    assert report["benchmark_status"] == "PUBLIC_PHYSICAL_OBSERVATIONS_AUDITED_NOT_MODEL_VALIDATION"


def test_bytes_must_match_pinned_upstream_git_blob(tmp_path: Path):
    directory = tmp_path / "physical"
    directory.mkdir()
    (directory / "manifest.json").write_bytes((DATA_DIR / "manifest.json").read_bytes())
    raw = (DATA_DIR / "BATT.csv").read_bytes()
    # Changing a single reported sample must fail evidence integrity checking.
    (directory / "BATT.csv").write_bytes(raw.replace(b"25.227624893188477", b"26.227624893188477", 1))
    with pytest.raises(ValueError, match="integrity mismatch"):
        audit_quadplane_battery(data_dir=directory)


def test_licensing_and_timestamp_assertions_are_fail_closed(tmp_path: Path):
    directory = tmp_path / "physical"
    directory.mkdir()
    (directory / "BATT.csv").write_bytes((DATA_DIR / "BATT.csv").read_bytes())
    orig = json.loads((DATA_DIR / "manifest.json").read_text())
    orig["timestamp_column_available"] = True
    (directory / "manifest.json").write_text(json.dumps(orig))
    with pytest.raises(ValueError, match="timestamp"):
        audit_quadplane_battery(data_dir=directory)
    orig["timestamp_column_available"] = False
    orig["battery_model_match_verified"] = True
    (directory / "manifest.json").write_text(json.dumps(orig))
    with pytest.raises(ValueError, match="unverified vehicle"):
        audit_quadplane_battery(data_dir=directory)
    orig["battery_model_match_verified"] = False
    orig["license"] = "not-established"
    (directory / "manifest.json").write_text(json.dumps(orig))
    with pytest.raises(ValueError, match="license"):
        audit_quadplane_battery(data_dir=directory)


def test_public_evidence_sources_preserve_research_gaps():
    reg = get_public_source_inventory()
    by_id = {s["id"]: s for s in reg["datasets"]}
    assert "cmu_matrice100_209_flights" in by_id
    assert "uiuc_propeller_database" in by_id
    assert by_id["quadplane_px4_2022"]["source_status"] == "CHECKSUM_VERIFIED_COPY_INCLUDED"
    assert by_id["amovfly"]["license_status"] == "NO_LICENSE_FOUND_IN_REPOSITORY_VERIFY_PERMISSIONS"
    assert by_id["nasa_battery_pcoe"]["ingestion_status"] == "NOT_IMPORTED"
    assert all(s["aircraft_model_match"] is False for s in reg["datasets"])
