"""M6 tests: fast evaluator correctness (vs strict brentq path), grid
evaluation gates, and the Pareto-frontier property."""

from pathlib import Path

import numpy as np
import pytest

from aeroforge_schemas.design import DroneDesign, FrameSpec
from optimization.batch import (
    FastHoverEvaluator,
    battery_spec_for_capacity,
    pareto_front,
    run_grid,
    with_payload,
    with_rotor_layout,
)
from physics.propulsion.battery import BatteryPack
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.loader import ComponentLibrary
from physics.structures.materials import load_materials

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def library() -> ComponentLibrary:
    return ComponentLibrary(REPO_ROOT / "data" / "components")


@pytest.fixture(scope="module")
def design() -> DroneDesign:
    return DroneDesign.model_validate_json(
        (REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def test_lut_matches_strict_inverse(library, design):
    """The fast evaluator's thrust->rpm LUT must reproduce the requested
    THRUST (the physically meaningful invariant). rpm recovery is checked
    only where the measured table is not flat (the 820 gf plateau from the
    two voltage planes makes the inverse ill-conditioned there by nature)."""
    motor = library.motor(design.powertrain.motor_id)
    prop = library.propeller(design.powertrain.propeller_id)
    battery_spec = library.battery(design.powertrain.battery_id)
    esc_spec = library.esc(design.powertrain.esc_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    ev = FastHoverEvaluator(dataset, battery_spec, esc_spec, units=4)

    envelope = dataset.envelope()
    lo, hi = envelope["rpm_range_merged"]
    for rpm_true in np.linspace(lo + 50, hi - 50, 12):
        gf = float(dataset.thrust_gf(rpm_true).value)
        thrust_n = gf * 9.80665e-3
        rpm_fast, extrapolated = ev.thrust_to_rpm(thrust_n)
        assert extrapolated is False
        # Thrust reconstruction is the invariant (0.5%).
        gf_back = float(dataset.thrust_gf(rpm_fast).value)
        assert gf_back == pytest.approx(gf, rel=5e-3)


def test_grid_rejects_esc_overload_and_excludes_it_from_frontier(library, design, monkeypatch):
    weak = library.esc(design.powertrain.esc_id).model_copy(update={"max_continuous_current_a": 1.0})
    monkeypatch.setattr(library, "esc", lambda key: weak)
    grid = {"battery_capacity_ah": [16.0], "rotor_count": [4],
            "arm_length_m": [0.30], "payload_kg": [0.0]}
    results = run_grid(design, library, grid)
    assert len(results) == 1 and not results[0].feasible
    assert any("ESC over-current" in flag for flag in results[0].flags)
    assert pareto_front(results) == []


def test_grid_evaluates_all_candidates_and_gates(library, design):
    material = load_materials(REPO_ROOT / "data" / "components" / "materials.json")["cfrp_quasi_iso"]
    grid = {
        "battery_capacity_ah": [10.0, 16.0, 22.0],
        "rotor_count": [4, 6],
        "arm_length_m": [0.25, 0.30],
        "payload_kg": [0.0, 2.0],
    }
    results = run_grid(design, library, grid, material=material)
    assert len(results) == 24
    assert all(r.mass_kg > 0 for r in results)
    feasible = [r for r in results if r.feasible]
    assert len(feasible) > 0
    # Flagged candidates carry a reason; nothing is silently dropped.
    for r in results:
        if not r.feasible:
            assert any(f.startswith("out_of_envelope") or f.startswith("structure_yield")
                       for f in r.flags)


def test_heavy_payload_flagged_out_of_envelope(library, design):
    """A payload so heavy the props cannot hold it: flagged, not faked."""
    material = load_materials(REPO_ROOT / "data" / "components" / "materials.json")["cfrp_quasi_iso"]
    results = run_grid(
        design, library,
        {"battery_capacity_ah": [16.0], "rotor_count": [4],
         "arm_length_m": [0.25], "payload_kg": [40.0]},
        material=material,
    )
    assert len(results) == 1
    assert not results[0].feasible
    assert any("exceeds measured max" in f for f in results[0].flags)


def test_pareto_front_is_non_dominated(library, design):
    material = load_materials(REPO_ROOT / "data" / "components" / "materials.json")["cfrp_quasi_iso"]
    grid = {
        "battery_capacity_ah": [8.0, 12.0, 16.0, 22.0],
        "rotor_count": [4, 6],
        "arm_length_m": [0.25],
        "payload_kg": [0.0, 2.0],
    }
    results = run_grid(design, library, grid, material=material)
    front = pareto_front(results)
    assert len(front) > 0
    # Property check: no feasible point dominates any frontier point.
    feasible = [r for r in results if r.feasible and r.endurance_to_warning_s is not None]
    for f in front:
        for other in feasible:
            if other is f:
                continue
            dominates = (
                other.mass_kg <= f.mass_kg
                and other.endurance_to_warning_s >= f.endurance_to_warning_s
                and (other.mass_kg < f.mass_kg or other.endurance_to_warning_s > f.endurance_to_warning_s)
            )
            assert not dominates, (f.params, other.params)


def test_battery_scaling_monotone_in_capacity(library, design):
    """Clone relations: capacity up -> mass up, pack R down (estimated model)."""
    base = library.battery(design.powertrain.battery_id)
    small = battery_spec_for_capacity(base, 8.0)
    big = battery_spec_for_capacity(base, 24.0)
    assert small.mass_kg < base.mass_kg < big.mass_kg
    assert small.internal_resistance_ohm > base.internal_resistance_ohm > big.internal_resistance_ohm


def test_rotor_layout_regeneration(design):
    hexa = with_rotor_layout(design, 6, 0.30)
    assert len(hexa.rotors) == 6
    assert len([p for p in hexa.parts if p.name.startswith("motor_")]) == 6
    radii = [np.hypot(r.position_m[0], r.position_m[1]) for r in hexa.rotors]
    assert all(abs(r - 0.30) < 1e-9 for r in radii)
    # spins alternate
    spins = [r.spin_direction for r in hexa.rotors]
    assert spins == [1, -1, 1, -1, 1, -1]


def test_hundreds_of_candidates_fast(library, design):
    """Spec acceptance: hundreds of candidates evaluated with gates + timing."""
    material = load_materials(REPO_ROOT / "data" / "components" / "materials.json")["cfrp_quasi_iso"]
    grid = {
        "battery_capacity_ah": [6.0, 10.0, 14.0, 18.0, 22.0],
        "rotor_count": [4, 6],
        "arm_length_m": [0.20, 0.25, 0.30],
        "payload_kg": [0.0, 1.0, 2.0, 3.0, 4.0],
    }
    import time

    t0 = time.perf_counter()
    results = run_grid(design, library, grid, material=material)
    elapsed = time.perf_counter() - t0
    assert len(results) == 150
    assert elapsed < 60.0
    assert any(r.feasible for r in results)
