"""Aeroacoustics (Gutin/BPF & Whitham Sonic Boom), Helicopter VRS/Precession, Cavitation, and RF/RCS Stealth."""

from __future__ import annotations

import math
from typing import Any

GRAVITY = 9.80665


def evaluate_rotor_and_jet_aeroacoustics(
    *,
    is_jet: bool = False,
    rotor_count: int = 4,
    blade_count: int = 2,
    rotor_rpm: float = 4800.0,
    rotor_diameter_m: float = 0.381,
    total_thrust_n: float = 35.0,
    jet_mach: float = 0.30,
    jet_exhaust_vel_m_s: float = 380.0,
    jet_nozzle_diam_m: float = 0.095,
    fuselage_len_m: float = 1.32,
    altitude_m: float = 500.0,
    distance_m: float = 15.0,
    rho_kg_m3: float = 1.225,
    a_sound_m_s: float = 340.3,
    p_atm_pa: float = 101325.0,
    max_spl_dba: float = 88.0,
) -> dict[str, Any]:
    """Compute rotor BPF/Gutin dB(A), jet mixing noise OASPL, and supersonic sonic boom overpressure."""
    if distance_m <= 0.1 or a_sound_m_s <= 50.0:
        raise ValueError("distance_m must be > 0.1 and speed of sound > 50 m/s")
    if not is_jet:
        bpf_hz = (max(1, blade_count) * rotor_rpm) / 60.0
        omega = rotor_rpm * 2.0 * math.pi / 60.0
        v_tip = omega * max(0.02, rotor_diameter_m) * 0.5
        m_tip = max(0.05, v_tip / a_sound_m_s)
        t_each = max(0.1, total_thrust_n) / max(1, rotor_count)
        spl_1_15m = 56.0 + 26.0 * math.log10(max(0.05, m_tip / 0.25)) + 14.0 * math.log10(max(0.5, t_each / 5.0))
        total_spl = spl_1_15m + 10.0 * math.log10(max(1, rotor_count)) - 20.0 * math.log10(max(0.5, distance_m) / 15.0)
        sonic_boom_pa = 0.0
        noise_ok = total_spl <= max_spl_dba
    else:
        bpf_hz = 0.0
        d_area = max(1e-4, jet_nozzle_diam_m * jet_nozzle_diam_m)
        spl_30m = 82.0 + 35.0 * math.log10(max(20.0, jet_exhaust_vel_m_s) / 320.0) + 10.0 * math.log10(d_area / 0.008)
        total_spl = spl_30m - 20.0 * math.log10(max(1.0, distance_m) / 30.0)
        sonic_boom_pa = 0.0
        if jet_mach > 1.02:
            h = max(80.0, altitude_m)
            len_m = max(0.4, fuselage_len_m)
            sonic_boom_pa = (
                1.9 * math.sqrt(max(1000.0, p_atm_pa)) * ((jet_mach * jet_mach - 1.0) ** 0.125) * (len_m ** 0.25) / (h ** 0.75) * 28.0
            )
        noise_ok = (total_spl <= max(115.0, max_spl_dba)) and ((sonic_boom_pa * 0.0208854) <= 2.5)
    return {
        "bpf_hz": round(bpf_hz, 2),
        "total_spl_dba": round(total_spl, 2),
        "sonic_boom_pa": round(sonic_boom_pa, 3),
        "sonic_boom_psf": round(sonic_boom_pa * 0.0208854, 4),
        "verdict": "NO_MODELED_LIMIT_BREACHED" if noise_ok else "FAIL",
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }


def evaluate_helicopter_vrs_and_asymmetry(
    *,
    mass_kg: float = 3.2,
    rotor_diameter_m: float = 1.48,
    rotor_rpm: float = 1450.0,
    rotor_inertia_kg_m2: float = 0.14,
    horizontal_speed_m_s: float = 12.0,
    vertical_speed_m_s: float = 0.0,
    pitch_or_roll_rate_rad_s: float = 0.35,
    rho_kg_m3: float = 1.225,
    a_sound_m_s: float = 340.3,
) -> dict[str, Any]:
    """Evaluate helicopter advance ratio mu, retreating blade stall, Vortex Ring State (VRS) & gyro precession."""
    if mass_kg <= 0.0 or rotor_diameter_m <= 0.1 or rotor_rpm <= 10.0:
        raise ValueError("Invalid helicopter parameters")
    r = rotor_diameter_m * 0.5
    omega = rotor_rpm * 2.0 * math.pi / 60.0
    v_tip = omega * r
    v_h_abs = abs(horizontal_speed_m_s)
    mu = v_h_abs / max(1.0, v_tip)
    m_adv = (v_tip + v_h_abs) / max(50.0, a_sound_m_s)
    area = math.pi * r * r
    v_hover = math.sqrt((mass_kg * GRAVITY) / max(0.05, 2.0 * rho_kg_m3 * area))
    vrs_ratio = vertical_speed_m_s / max(0.5, v_hover)
    vrs_entered = (-1.25 <= vrs_ratio <= -0.35) and (v_h_abs < 0.70 * v_hover)
    retreating_stall = mu > 0.42
    gyro_torque = max(0.01, rotor_inertia_kg_m2) * omega * abs(pitch_or_roll_rate_rad_s)
    ok = (not vrs_entered) and (not retreating_stall) and (m_adv <= 0.90)
    return {
        "advance_ratio_mu": round(mu, 4),
        "advancing_tip_mach": round(m_adv, 4),
        "hover_induced_vel_m_s": round(v_hover, 3),
        "vrs_ratio": round(vrs_ratio, 3),
        "vrs_entered": vrs_entered,
        "retreating_stall_risk": retreating_stall,
        "gyro_precession_torque_nm": round(gyro_torque, 3),
        "verdict": "NO_MODELED_LIMIT_BREACHED" if ok else "FAIL",
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }


def evaluate_hydro_cavitation(
    *,
    prop_diameter_m: float = 0.14,
    prop_rpm: float = 3800.0,
    submergence_depth_m: float = 0.35,
    water_temp_c: float = 20.0,
    water_rho_kg_m3: float = 1025.0,
    p_atm_pa: float = 101325.0,
    sigma_crit: float = 0.35,
) -> dict[str, Any]:
    """Compute marine/amphibious propeller cavitation number sigma via Antoine water vapor pressure."""
    if prop_diameter_m <= 0.01 or prop_rpm <= 0.0:
        raise ValueError("prop_diameter_m and prop_rpm must be positive")
    v_tip = (prop_rpm * 2.0 * math.pi / 60.0) * (prop_diameter_m * 0.5)
    tc = max(0.0, min(60.0, water_temp_c))
    p_vap = (10.0 ** (8.07131 - 1730.63 / (233.426 + tc))) * 133.322
    p_loc = p_atm_pa + water_rho_kg_m3 * GRAVITY * max(0.0, submergence_depth_m)
    sigma = (p_loc - p_vap) / max(1.0, 0.5 * water_rho_kg_m3 * v_tip * v_tip)
    cavitating = sigma < sigma_crit
    return {
        "tip_speed_m_s": round(v_tip, 3),
        "vapor_pressure_pa": round(p_vap, 2),
        "cavitation_number": round(sigma, 4),
        "cavitating": cavitating,
        "verdict": "FAIL" if cavitating else "NO_MODELED_LIMIT_BREACHED",
    }


def evaluate_rf_and_rcs(
    *,
    distance_km: float = 2.5,
    frequency_mhz: float = 2400.0,
    tx_power_dbm: float = 20.0,
    tx_gain_dbi: float = 2.0,
    rx_gain_dbi: float = 5.0,
    rx_sensitivity_dbm: float = -98.0,
    rain_mm_h: float = 0.0,
    sweep_deg: float = 26.0,
    frontal_area_m2: float = 0.08,
    stealth_shaping: bool = False,
) -> dict[str, Any]:
    """Evaluate Friis RF link margin with ITU-R rain attenuation and physical-optics swept RCS (dBsm)."""
    if distance_km <= 0.001 or frequency_mhz <= 1.0:
        raise ValueError("distance_km and frequency_mhz must be positive")
    fspl = 32.44 + 20.0 * math.log10(frequency_mhz) + 20.0 * math.log10(distance_km)
    f_ghz = frequency_mhz / 1000.0
    rain_fade = (0.00018 * (f_ghz ** 2.2) * (rain_mm_h ** 1.05) * distance_km) if rain_mm_h > 0.0 else 0.0
    rx_dbm = tx_power_dbm + tx_gain_dbi + rx_gain_dbi - fspl - rain_fade
    margin = rx_dbm - rx_sensitivity_dbm
    cos_sw = max(0.25, math.cos(math.radians(min(68.0, abs(sweep_deg)))))
    rcs_m2 = max(1e-4, frontal_area_m2 * 1.45 * (cos_sw ** 2.4) * (0.08 if stealth_shaping else 1.0))
    return {
        "fspl_db": round(fspl, 2),
        "rain_fade_db": round(rain_fade, 3),
        "link_margin_db": round(margin, 2),
        "rcs_m2": round(rcs_m2, 5),
        "rcs_dbsm": round(10.0 * math.log10(rcs_m2), 2),
        "verdict": "NO_MODELED_LIMIT_BREACHED" if margin >= 6.0 else "FAIL",
    }
