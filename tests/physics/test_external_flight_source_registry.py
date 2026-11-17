"""Research registry invariants only; no empirical flight data is asserted."""
import json
from pathlib import Path

REGISTRY = (
    Path(__file__).resolve().parents[2] /
    "data/benchmarks/flight/tu_braunschweig_p80iii_2023_candidate.json"
)


def load():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_original_flight_data_are_not_invented_or_falsely_ingested():
    r = load()
    source = r["original_data_reference"]
    assert source["record_url"] == "https://leopard.tu-braunschweig.de/receive/dbbs_mods_00070168"
    assert source["original_files_downloaded"] is False
    assert source["original_provider_file_inventory"] == []
    assert source["source_sha256"] is None
    assert source["source_license_verified"] is False
    assert source["original_channel_schema_verified"] is False
    assert not r["ready_for_m26_acceptance"]


def test_exact_motor_name_does_not_forge_complete_aircraft_match():
    r = load()
    aircraft = r["reported_vehicle"]
    assert aircraft["motor_model_string"] == "P80III-KV100"
    assert aircraft["propeller_model_string"] == "CF-PROP 30 x 10.5"
    assert aircraft["vehicle_type"] == "quadcopter"
    assert aircraft["takeoff_mass_kg_approx"] == 25
    assert aircraft["installed_esc_model"] is None
    assert not aircraft["geometry_mass_inertia_verified_against_aeroforge_reference"]


def test_no_unsupported_flight_telemetry_channels_or_release():
    r = load()
    channels = r["reported_measurands"]
    assert not channels["full_flight_position_velocity_attitude_commands_confirmed_in_original_data"]
    assert not channels["full_battery_current_voltage_soc_confirmed_in_original_data"]
    assert not channels["clock_alignment_and_independent_sensor_calibration_confirmed"]
    assert r["status"] == "PHYSICAL_FLIGHT_FIDELITY_NOT_ESTABLISHED_EXTERNAL_SOURCE_CUSTODY_PENDING"
    assert r["classification"].endswith("NOT_INGESTED")


def test_article_and_repository_are_traceable_but_distinct():
    r = load()
    assert r["journal_article"]["doi"] == "10.3390/atmos14091336"
    assert r["original_data_reference"]["repository"] == "Technische Universität Braunschweig"
    assert "original" not in r["classification"].lower() or not r["ready_for_m26_acceptance"]
