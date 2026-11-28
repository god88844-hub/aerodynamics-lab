"""Tests for Jet/Compressible aerodynamics, NASA benchmarks, Seaplane Savitsky hydrodynamics, and catalog hardware."""

from __future__ import annotations

import pytest

from physics.aerodynamics.compressible_jet import (
    evaluate_compressible_wing,
    evaluate_jet_benchmarks,
    evaluate_jet_flight_point,
)
from physics.hydrodynamics.seaplane import evaluate_seaplane_water_takeoff, verify_savitsky_benchmark


def test_savitsky_worked_case_and_seaplane_hump_gates() -> None:
    bench = verify_savitsky_benchmark()
    assert bench["cv_err"] < 0.01
    assert bench["cl0_err"] < 0.002
    assert bench["cl_beta_err"] < 0.002
    assert bench["lift_rel_err"] < 0.02

    # Nominal twin-float seaplane clears hump drag & takeoff
    ok_sea = evaluate_seaplane_water_takeoff(mass_kg=3.2, installed_thrust_n=18.0, float_volume_each_m3=0.014)
    assert ok_sea["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert ok_sea["reserve_buoyancy_ratio"] >= 1.8
    assert ok_sea["takeoff_run_m"] is not None and ok_sea["takeoff_run_m"] > 2.0

    # Underpowered or rough-chop seaplane gets stuck behind water hump resistance -> FAIL
    stuck_sea = evaluate_seaplane_water_takeoff(mass_kg=4.5, installed_thrust_n=7.0, water_chop_m=0.14)
    assert stuck_sea["hump_ok"] is False
    assert stuck_sea["verdict"] == "FAIL"

    # Undersized floats fail Archimedes reserve buoyancy -> FAIL
    sink_sea = evaluate_seaplane_water_takeoff(mass_kg=8.0, installed_thrust_n=40.0, float_volume_each_m3=0.004)
    assert sink_sea["buoyancy_ok"] is False
    assert sink_sea["verdict"] == "FAIL"


def test_compressible_korn_wave_drag_brayton_lapse_and_nasa_benchmarks() -> None:
    sub = evaluate_compressible_wing(mach=0.35, cl_incompressible=0.4, cd0=0.018, aspect_ratio=7.0, sweep_deg=15.0)
    trans = evaluate_compressible_wing(mach=0.86, cl_incompressible=0.4, cd0=0.018, aspect_ratio=7.0, sweep_deg=15.0)
    assert trans["cd_wave"] > sub["cd_wave"] + 0.005
    assert trans["m_dd"] > 0.72

    # Catalog micro-turbojet cruise & EGT limit fail-closed test (realistic 5.2 kg RC turbine jet at ~90 m/s)
    nominal_jet = evaluate_jet_flight_point(
        propulsor_id="kingtech_k45g4",
        mass_kg=5.2,
        wing_area_m2=0.32,
        aspect_ratio=6.2,
        sweep_deg=26.0,
        mach=0.26,
        altitude_m=1500.0,
        alpha_deg=1.5,
        throttle_pct=95.0,
    )
    assert nominal_jet["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert nominal_jet["thrust_to_drag"] > 1.25

    overspeed_jet = evaluate_jet_flight_point(
        propulsor_id="kingtech_k45g4",
        mass_kg=5.2,
        wing_area_m2=0.48,
        aspect_ratio=6.2,
        sweep_deg=26.0,
        mach=1.05,  # exceeds KingTech K-45G4 0.88 envelope
        altitude_m=500.0,
        alpha_deg=2.0,
        throttle_pct=105.0,
    )
    assert overspeed_jet["verdict"] == "FAIL"

    with pytest.raises(ValueError, match="Unknown preloaded jet propulsor"):
        evaluate_jet_flight_point(
            propulsor_id="invented_custom_turbine",
            mass_kg=4.0,
            wing_area_m2=0.4,
            aspect_ratio=6.0,
            sweep_deg=20.0,
            mach=0.4,
            altitude_m=500.0,
            alpha_deg=3.0,
        )

    bm = evaluate_jet_benchmarks()
    assert bm["nasa_jet_m1p63"]["monotone_plume_decay"] is True
    assert bm["nasa_tm4074_ladson"]["rmse_cl"] < 0.08
