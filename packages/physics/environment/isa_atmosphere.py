"""US Standard Atmosphere 1976 (0..32 km) with Sutherland viscosity and virtual-temperature humidity correction."""

from __future__ import annotations

from dataclasses import dataclass
import math

R_DRY_AIR = 287.05287  # J/(kg*K)
GAMMA_AIR = 1.4
G0 = 9.80665
SUTHERLAND_C1 = 1.458e-6
SUTHERLAND_S = 110.4


@dataclass(frozen=True)
class AtmosphereState:
    altitude_m: float
    temperature_k: float
    pressure_pa: float
    density_kg_m3: float
    speed_of_sound_m_s: float
    dynamic_viscosity_pa_s: float
    kinematic_viscosity_m2_s: float
    relative_humidity: float = 0.0


def saturation_vapor_pressure_pa(temperature_k: float) -> float:
    """Magnus-Tetens approximation valid cleanly across [-45 C, +60 C]."""
    t_c = temperature_k - 273.15
    return 610.78 * math.exp((17.27 * t_c) / max(1.0, t_c + 237.3))


def isa_atmosphere_1976(
    altitude_m: float,
    *,
    temperature_offset_k: float = 0.0,
    relative_humidity: float = 0.0,
) -> AtmosphereState:
    """Compute SI atmosphere properties (Troposphere 0..11 km, Lower Stratosphere 11..32 km)."""
    if not math.isfinite(altitude_m) or altitude_m < -500.0 or altitude_m > 32000.0:
        raise ValueError("altitude_m must be finite within [-500, 32000] m for ISA-1976 layers")
    if not 0.0 <= relative_humidity <= 1.0:
        raise ValueError("relative_humidity must stay in [0.0, 1.0]")

    h = float(altitude_m)
    if h <= 11000.0:
        lapse = -0.0065
        t_isa = 288.15 + lapse * h
        p_pa = 101325.0 * ((t_isa / 288.15) ** (-G0 / (R_DRY_AIR * lapse)))
    elif h <= 20000.0:
        t_isa = 216.65
        p_11 = 22632.06
        p_pa = p_11 * math.exp(-G0 * (h - 11000.0) / (R_DRY_AIR * t_isa))
    else:
        lapse2 = 0.0010
        t_isa = 216.65 + lapse2 * (h - 20000.0)
        p_20 = 5474.889
        p_pa = p_20 * ((t_isa / 216.65) ** (-G0 / (R_DRY_AIR * lapse2)))

    t_k = max(50.0, t_isa + temperature_offset_k)
    if relative_humidity > 0.0:
        pv = min(0.95 * p_pa, relative_humidity * saturation_vapor_pressure_pa(t_k))
        # Moist air density = (P_dry / (R_d * T)) + (P_v / (R_v * T)) with R_v = 461.495
        rho = ((p_pa - pv) / (R_DRY_AIR * t_k)) + (pv / (461.495 * t_k))
    else:
        rho = p_pa / (R_DRY_AIR * t_k)

    a = math.sqrt(GAMMA_AIR * R_DRY_AIR * t_k)
    mu = SUTHERLAND_C1 * (t_k ** 1.5) / (t_k + SUTHERLAND_S)
    nu = mu / rho
    return AtmosphereState(
        altitude_m=h,
        temperature_k=t_k,
        pressure_pa=p_pa,
        density_kg_m3=rho,
        speed_of_sound_m_s=a,
        dynamic_viscosity_pa_s=mu,
        kinematic_viscosity_m2_s=nu,
        relative_humidity=relative_humidity,
    )
