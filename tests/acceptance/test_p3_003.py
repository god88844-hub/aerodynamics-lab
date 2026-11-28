"""P3-003 Acceptance Tests: Coupled Jet Cycle, Cargo Slung-Load, Tailsitter & Flying Wing."""

from __future__ import annotations

import math

import pytest

from physics.aerodynamics.compressible_jet import (
    compute_isentropic_cd_nozzle,
    compute_mil_e_5008b_inlet_recovery,
    evaluate_coupled_jet_cycle,
)
from physics.dynamics.slung_load_and_tailsitter import (
    evaluate_cargo_slung_load,
    evaluate_flying_wing_reflex,
    evaluate_tailsitter_transition,
)


def test_p3_003_coupled_jet_inlet_nozzle_and_shock_cone() -> None:
    eta_sub = compute_mil_e_5008b_inlet_recovery(0.45)
    eta_sup = compute_mil_e_5008b_inlet_recovery(1.45)
    assert 0.97 < eta_sub < 0.99
    assert 0.70 < eta_sup < eta_sub

    nozzle = compute_isentropic_cd_nozzle(pt_pa=240000.0, tt_k=920.0, throat_area_m2=0.0023, exit_area_m2=0.0028, ambient_p_pa=101325.0, mach_flight=1.25)
    assert nozzle["choked"] is True and float(nozzle["mdot_kg_s"]) > 0.5

    sup = evaluate_coupled_jet_cycle(mach=1.40, throttle_frac=0.95, static_thrust_n=95.0)
    assert math.isclose(float(sup["mach_cone_half_angle_deg"]), math.degrees(math.asin(1.0 / 1.40)), abs_tol=0.15)
    assert float(sup["cd_wave"]) > 0.01

    choked_intake = evaluate_coupled_jet_cycle(mach=0.7, intake_area_m2=0.0014, throttle_frac=1.0, cooling_grade=0, oat_c=42.0)
    assert choked_intake["egt_ok"] is False and choked_intake["verdict"] == "FAIL"


def test_p3_003_cargo_slung_load_and_release_step() -> None:
    loaded = evaluate_cargo_slung_load(carrier_mass_kg=4.2, cargo_mass_kg=1.8, cable_length_m=1.2, airspeed_m_s=12.0, max_thrust_n=125.0, payload_released=False)
    released = evaluate_cargo_slung_load(carrier_mass_kg=4.2, cargo_mass_kg=1.8, cable_length_m=1.2, airspeed_m_s=12.0, max_thrust_n=125.0, payload_released=True)
    assert loaded["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert float(loaded["pendulum_freq_hz"]) == pytest.approx(0.455, abs=0.02)
    assert float(released["effective_mass_kg"]) == pytest.approx(4.2, abs=1e-6)
    assert float(released["blowback_drag_n"]) == 0.0
    assert float(released["residual_tw"]) > float(loaded["residual_tw"])

    overloaded = evaluate_cargo_slung_load(carrier_mass_kg=4.2, cargo_mass_kg=7.5, cable_length_m=1.2, airspeed_m_s=24.0, cg_offset_m=0.14, max_thrust_n=110.0)
    assert overloaded["verdict"] == "FAIL"


def test_p3_003_tailsitter_and_flying_wing_models() -> None:
    tail_ok = evaluate_tailsitter_transition(
        mass_kg=1.85,
        wing_area_m2=0.42,
        wingspan_m=1.05,
        max_thrust_n=32.0,
        airspeed_m_s=12.0,
        transition_pitch_deg=72.0,
        duct_area_ratio=1.08,
    )
    assert tail_ok["verdict"] == "NO_MODELED_LIMIT_BREACHED" and float(tail_ok["propwash_slip_m_s"]) > 20.0

    wing_ok = evaluate_flying_wing_reflex(mass_kg=1.4, wing_area_m2=0.38, sweep_deg=26.0, airspeed_m_s=22.0)
    wing_bad = evaluate_flying_wing_reflex(mass_kg=1.4, wing_area_m2=0.38, sweep_deg=8.0, airspeed_m_s=22.0)
    assert wing_ok["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert wing_bad["verdict"] == "FAIL"
