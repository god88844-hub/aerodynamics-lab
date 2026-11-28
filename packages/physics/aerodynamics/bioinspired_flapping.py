"""Clean-room Phase 1 interface physics: Strouhal/LEV flapping, morphing reflex, and compliant beam scaling.

All models enforce SI units and fail closed outside declared subsonic bio-inspired envelopes.
Status remains RESEARCH_DEVELOPMENT / UNVALIDATED until Phase 1 confirmatory receipts close.
"""

from __future__ import annotations

import math
from typing import Any

from aeroforge_schemas.bioinspired import (
    BioInspiredVehicleContract,
    CompliantFlexureSpec,
    FlappingWingKinematics,
    MorphingWingState,
)


def compute_theodorsen_lag_magnitude(reduced_freq_k: float) -> float:
    """Rational Jones approximation to |C(k)| for harmonic unsteady circulation lag (k >= 0)."""
    if not math.isfinite(reduced_freq_k) or reduced_freq_k < 0.0:
        raise ValueError("reduced_freq_k must be finite and >= 0")
    if reduced_freq_k == 0.0:
        return 1.0
    # Jones two-pole approximation: C(k) ~ 1 - 0.165/(1 - 0.0455i/k) - 0.335/(1 - 0.30i/k)
    re1 = 0.165 / (1.0 + (0.0455 / reduced_freq_k) ** 2)
    im1 = (0.165 * (0.0455 / reduced_freq_k)) / (1.0 + (0.0455 / reduced_freq_k) ** 2)
    re2 = 0.335 / (1.0 + (0.30 / reduced_freq_k) ** 2)
    im2 = (0.335 * (0.30 / reduced_freq_k)) / (1.0 + (0.30 / reduced_freq_k) ** 2)
    c_re = 1.0 - re1 - re2
    c_im = -(im1 + im2)
    return math.hypot(c_re, c_im)


def evaluate_flapping_cycle_quasi_steady(
    kin: FlappingWingKinematics,
    *,
    vehicle_mass_kg: float,
    forward_airspeed_m_s: float = 0.0,
    rho_kg_m3: float = 1.225,
    mean_aoa_rad: float = 0.65,
    n_wings: int = 2,
) -> dict[str, Any]:
    """Evaluate dimensionless Strouhal/k, LEV lift, and cycle-averaged flapping hover/forward thrust."""
    if not math.isfinite(vehicle_mass_kg) or vehicle_mass_kg <= 0.0:
        raise ValueError("vehicle_mass_kg must be positive")
    if not math.isfinite(rho_kg_m3) or rho_kg_m3 <= 0.0:
        raise ValueError("rho_kg_m3 must be positive")

    omega = 2.0 * math.pi * kin.flap_frequency_hz
    # Mean angular stroke speed of sinusoidal stroke phi(t) = Phi * sin(omega * t):
    mean_phidot = (2.0 / math.pi) * omega * kin.stroke_amplitude_rad
    rms_phidot = omega * kin.stroke_amplitude_rad / math.sqrt(2.0)
    u_tip_peak = omega * kin.stroke_amplitude_rad * kin.wing_span_r_m
    a_sound = 340.3
    tip_mach = u_tip_peak / a_sound
    if tip_mach > 0.25:
        raise ValueError(f"Flapping tip Mach {tip_mach:.3f} exceeds incompressible Phase 1 envelope (<= 0.25)")

    u_ref = max(0.25, math.hypot(forward_airspeed_m_s, rms_phidot * kin.wing_span_r_m * math.sqrt(kin.r22_moment)))
    reduced_k = (omega * kin.mean_chord_c_m) / (2.0 * u_ref)
    stroke_arc_m = 2.0 * kin.wing_span_r_m * math.sin(kin.stroke_amplitude_rad)
    strouhal = (kin.flap_frequency_hz * stroke_arc_m) / forward_airspeed_m_s if forward_airspeed_m_s > 0.2 else None

    # Sane-Dickinson / Polhamus Leading-Edge Vortex (LEV) high-AoA lift & drag polars
    cl_trans = 0.225 + 1.58 * math.sin(2.13 * mean_aoa_rad - 0.125)
    cd_trans = 1.92 - 1.55 * math.cos(2.04 * mean_aoa_rad - 0.171)
    # Effective aerodynamic force coefficient scaled cleanly by Theodorsen wake factor
    c_k = compute_theodorsen_lag_magnitude(min(reduced_k, 1.5))

    wing_area = kin.wing_span_r_m * kin.mean_chord_c_m
    # Two-wing cycle-averaged vertical force: N_w * 0.5 * rho * S * (phidot_rms * R)^2 * r22 * C_L_eff
    u2_integral = (rms_phidot * kin.wing_span_r_m) ** 2 * kin.r22_moment
    rotational_boost = 1.0 + 0.18 * (kin.feathering_amplitude_rad / 1.2)
    mean_lift_n = n_wings * 0.5 * rho_kg_m3 * wing_area * u2_integral * max(0.05, cl_trans) * rotational_boost * (0.75 + 0.25 * c_k)
    mean_drag_torque_power_w = n_wings * 0.5 * rho_kg_m3 * wing_area * ((rms_phidot * kin.wing_span_r_m) ** 3) * kin.r33_moment * max(0.1, cd_trans)

    weight_n = vehicle_mass_kg * 9.80665
    return {
        "strouhal_number": strouhal,
        "reduced_frequency_k": reduced_k,
        "theodorsen_mag": c_k,
        "peak_tip_mach": tip_mach,
        "mean_lift_n": mean_lift_n,
        "hover_thrust_to_weight": mean_lift_n / weight_n,
        "aero_shaft_power_w": mean_drag_torque_power_w,
        "verdict": "NO_MODELED_LIMIT_BREACHED" if mean_lift_n >= weight_n else "INSUFFICIENT_LIFT",
        "physical_validation_status": "UNVALIDATED_BIOINSPIRED",
    }


def evaluate_morphing_wing_reflex(state: MorphingWingState, *, airspeed_m_s: float = 12.0, rho_kg_m3: float = 1.225) -> dict[str, Any]:
    """Modulate span, planform area, rolling authority, and rudderless yaw damping via PigeonBot-style morphing."""
    effective_span_m = state.baseline_span_m * (1.0 - 0.38 * state.wing_tuck_fraction)
    effective_area_m2 = state.baseline_area_m2 * (1.0 - 0.30 * state.wing_tuck_fraction)
    q = 0.5 * rho_kg_m3 * airspeed_m_s * airspeed_m_s
    # Asymmetric tuck + tail tilt generates adverse/proverse roll-yaw reflex moments
    roll_moment_nm = q * effective_area_m2 * effective_span_m * (0.14 * state.wing_asymmetry_diff)
    yaw_damping_gain = (0.04 + 0.08 * state.tail_spread_fraction) * math.cos(state.tail_tilt_rad)
    return {
        "effective_span_m": effective_span_m,
        "effective_area_m2": effective_area_m2,
        "roll_moment_nm": roll_moment_nm,
        "yaw_damping_coeff": yaw_damping_gain,
        "physical_validation_status": "UNVALIDATED_BIOINSPIRED",
    }


def evaluate_compliant_flex_beam(
    spec: CompliantFlexureSpec,
    *,
    span_m: float,
    section_mass_kg: float,
    peak_distributed_load_n_m: float,
    applied_cycles: int,
) -> dict[str, Any]:
    """Euler-Bernoulli flexible wing tip deflection, 1st natural mode, and fatigue fail-closed check."""
    if span_m <= 0.0 or section_mass_kg <= 0.0:
        raise ValueError("span_m and section_mass_kg must be positive")
    mass_per_m = section_mass_kg / span_m
    first_mode_hz = (1.875 * 1.875 / (2.0 * math.pi)) * math.sqrt(spec.flexural_rigidity_ei_nm2 / (mass_per_m * (span_m ** 4)))
    tip_deflection_m = (peak_distributed_load_n_m * (span_m ** 4)) / (8.0 * spec.flexural_rigidity_ei_nm2)
    root_moment_nm = 0.5 * peak_distributed_load_n_m * (span_m ** 2)
    fatigue_ok = applied_cycles <= spec.max_cycle_count_budget
    return {
        "first_bending_mode_hz": first_mode_hz,
        "static_tip_deflection_m": tip_deflection_m,
        "tip_deflection_span_ratio": tip_deflection_m / span_m,
        "root_moment_nm": root_moment_nm,
        "fatigue_ok": fatigue_ok,
        "verdict": "NO_MODELED_LIMIT_BREACHED" if fatigue_ok and (tip_deflection_m / span_m) < 0.25 else "FAIL",
        "physical_validation_status": "UNVALIDATED_BIOINSPIRED",
    }


def verify_bioinspired_contract(contract: BioInspiredVehicleContract) -> dict[str, Any]:
    """Validate structural/kinematic envelope boundaries for a registered Phase 1 configuration."""
    out: dict[str, Any] = {
        "id": contract.id,
        "bio_mode": contract.bio_mode,
        "physical_validation_status": contract.physical_validation_status,
    }
    if contract.flapping is not None:
        out["flapping_eval"] = evaluate_flapping_cycle_quasi_steady(
            contract.flapping, vehicle_mass_kg=contract.total_mass_kg
        )
    if contract.morphing is not None:
        out["morphing_eval"] = evaluate_morphing_wing_reflex(contract.morphing)
    return out
