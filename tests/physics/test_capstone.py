"""M8 capstone tests: the 60 kg hexa design is valid, flyable within its
measured envelope, completes the flight mission, and records the motor-
failure outcome honestly. The full mission suite lives in
scripts/run_capstone.py (its artifacts ship in outputs/)."""

from pathlib import Path

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.loader import ComponentLibrary
from physics.scenarios.runner import (
    landing_scenario,
    motor_failure_scenario,
    run_scenario,
    takeoff_climb_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN = REPO_ROOT / "data" / "designs" / "hexa_p80_60kg.json"


@pytest.fixture(scope="module")
def library() -> ComponentLibrary:
    return ComponentLibrary(REPO_ROOT / "data" / "components")


@pytest.fixture(scope="module")
def design() -> DroneDesign:
    return DroneDesign.model_validate_json(DESIGN.read_text(encoding="utf-8"))


def test_capstone_design_is_60kg_hexa_with_sourced_powertrain(design, library):
    assert design.name == "hexa_p80_60kg"
    assert len(design.rotors) == 6
    total = sum(p.mass_kg for p in design.parts)
    assert total == pytest.approx(60.0, abs=0.01)  # AUW 60 kg MTOW
    # The reaction-torque parameter is sourced from the bench torque column.
    assert design.rotor_torque_per_thrust_n_m_per_n == pytest.approx(0.0224)
    motor = library.motor(design.powertrain.motor_id)
    assert motor.source.estimated is False
    assert any(row.torque_nm is not None for row in motor.test_data)


def test_hover_point_within_measured_envelope(design, library):
    motor = library.motor(design.powertrain.motor_id)
    prop = library.propeller(design.powertrain.propeller_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    mass = sum(p.mass_kg for p in design.parts)
    target_per_rotor = mass * 9.80665 / 6.0
    envelope = dataset.envelope()
    lo, hi = envelope["rpm_range_merged"]
    gf_target = target_per_rotor / 9.80665e-3
    gf_table_min = float(dataset._merged_thrust_gf.min())
    gf_table_max = float(dataset._merged_thrust_gf.max())
    assert gf_table_min <= gf_target <= gf_table_max
    # Thrust margin: max thrust per rotor vs hover.
    margin = gf_table_max / gf_target
    assert 1.3 <= margin <= 1.6  # ~1.40 for this design: thin-but-viable margin
    _ = (lo, hi)


def test_flight_mission_completes(design, library):
    res = run_scenario(design, takeoff_climb_scenario(5.0), library)
    assert not res.aborted, res.abort_event.message if res.abort_event else None
    assert res.time_to_altitude_s is not None
    assert res.energy_wh > 0
    assert res.structural_margin_min is not None and res.structural_margin_min >= 1.0


def test_landing_mission_completes(design, library):
    res = run_scenario(design, landing_scenario(4.0, duration_s=14.0), library)
    assert not res.aborted, res.abort_event.message if res.abort_event else None
    assert abs(res.states[-1, 2]) < 0.10


def test_motor_failure_outcome_is_named(design, library):
    """Hexa hovers at 82% throttle: one rotor out demands ~12 kg from the
    remaining five (86%+ each) — the controller loses attitude and the run
    aborts with a NAMED cause (recorded honestly, not silently survived)."""
    res = run_scenario(design, motor_failure_scenario(5.0, failure_at_s=6.0), library)
    assert res.aborted
    assert res.abort_event.kind in ("attitude_loss", "ground_crash")
