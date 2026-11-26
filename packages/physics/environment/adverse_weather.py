"""Slice 0D weather software core: spatial turbulence gusts, supported rain/wet drag & CL loss, and icing."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

MAX_SUPPORTED_RAIN_MM_H = 100.0
MIN_SUPPORTED_ICING_TEMP_C = -25.0


def evaluate_spatial_turbulence(
    *,
    altitude_m: float,
    mean_wind_10m_m_s: tuple[float, float, float],
    turbulence_intensity: float,
    seed: int = 42,
    n_samples: int = 20,
) -> dict[str, Any]:
    """Deterministic wind shear + seeded Dryden-proxy turbulence samples."""
    if altitude_m < 0.0 or not 0.0 <= turbulence_intensity <= 0.5:
        raise ValueError("altitude_m must be >= 0 and turbulence_intensity in [0, 0.5]")
    shear_scale = ((max(1.0, altitude_m) / 10.0) ** 0.143)
    base = np.array(mean_wind_10m_m_s, dtype=float) * shear_scale
    sigma = max(0.05, float(np.linalg.norm(base))) * turbulence_intensity
    rng = np.random.default_rng(np.random.PCG64(int(seed)))
    gusts = rng.normal(0.0, sigma, size=(n_samples, 3))
    return {
        "schema_version": "1.0",
        "shear_scale": float(shear_scale),
        "mean_wind_at_alt_m_s": base.tolist(),
        "gust_samples_m_s": (base + gusts).tolist(),
        "seed": int(seed),
    }


def evaluate_rain_wet_effects(
    *,
    rain_mm_h: float,
    base_cl_max: float = 1.45,
    base_cd0: float = 0.025,
) -> dict[str, Any]:
    """Compute bounded rain liquid-water content drag penalty and wet-airfoil CL_max reduction."""
    if rain_mm_h < 0.0 or not math.isfinite(rain_mm_h):
        raise ValueError("rain_mm_h must be finite and >= 0")
    if rain_mm_h > MAX_SUPPORTED_RAIN_MM_H:
        raise ValueError(f"Extreme precipitation {rain_mm_h} mm/h exceeds supported {MAX_SUPPORTED_RAIN_MM_H} mm/h limit")

    # Marshall-Palmer LWC [g/m^3] ~ 0.072 * R^0.88
    lwc_g_m3 = 0.072 * (rain_mm_h ** 0.88) if rain_mm_h > 0.0 else 0.0
    wet_fraction = min(0.28, 0.03 * math.sqrt(rain_mm_h))
    cl_max_wet = base_cl_max * (1.0 - wet_fraction)
    cd0_wet = base_cd0 + 0.0018 * math.sqrt(rain_mm_h)
    return {
        "schema_version": "1.0",
        "rain_mm_h": float(rain_mm_h),
        "liquid_water_content_g_m3": float(lwc_g_m3),
        "wet_cl_max": float(cl_max_wet),
        "wet_cd0": float(cd0_wet),
        "status": "SUPPORTED_WITH_CAVEATS",
        "caveat": "Empirically bounded wet airfoil degradation model; physical validation pending P0D-010/011.",
    }


def evaluate_icing_and_shedding(
    *,
    oat_c: float,
    lwc_g_m3: float,
    exposure_s: float,
    chord_m: float = 0.15,
    airspeed_m_s: float = 18.0,
    anti_ice_power_w: float = 0.0,
) -> dict[str, Any]:
    """Compute bounded icing accretion mass, drag multiplier, and anti-ice/mechanical shedding."""
    if lwc_g_m3 < 0.0 or exposure_s < 0.0 or chord_m <= 0.0 or airspeed_m_s < 0.0:
        raise ValueError("Icing inputs must be non-negative physical quantities")
    if oat_c < MIN_SUPPORTED_ICING_TEMP_C:
        raise ValueError(f"OAT {oat_c} C colder than supported icing envelope ({MIN_SUPPORTED_ICING_TEMP_C} C)")

    active = oat_c <= 0.0 and lwc_g_m3 > 0.0
    if not active:
        return {"icing_active": False, "accreted_mass_kg": 0.0, "drag_multiplier": 1.0, "shedding_event": False}

    freezing_frac = min(1.0, max(0.05, -oat_c / 8.0))
    raw_mass_kg = 0.001 * lwc_g_m3 * airspeed_m_s * (0.25 * chord_m) * exposure_s * freezing_frac
    # Anti-ice heating or melting near 0C sheds part of accreted ice asymmetrically
    melt_reduction = min(raw_mass_kg, 0.000015 * anti_ice_power_w * exposure_s)
    net_mass_kg = max(0.0, raw_mass_kg - melt_reduction)
    shedding_event = melt_reduction > 0.0 and net_mass_kg > 0.001
    drag_mult = 1.0 + min(1.5, 45.0 * net_mass_kg)
    verdict = "FAIL" if net_mass_kg > 0.12 else "NO_MODELED_LIMIT_BREACHED"
    return {
        "schema_version": "1.0",
        "icing_active": True,
        "oat_c": float(oat_c),
        "accreted_mass_kg": float(net_mass_kg),
        "drag_multiplier": float(drag_mult),
        "shedding_event": shedding_event,
        "verdict": verdict,
        "physical_validation_status": "UNVALIDATED",
    }
