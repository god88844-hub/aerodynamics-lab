"""P0D-005: Spatial wind shear, seeded turbulence fields, and ISA temperature/pressure/humidity properties."""

from __future__ import annotations

import pytest

from physics.environment.adverse_weather import evaluate_spatial_turbulence
from physics.environment.isa_atmosphere import isa_atmosphere_1976


def test_p0d_005_spatial_turbulence_seed_reproducibility_and_isa_humidity():
    t1 = evaluate_spatial_turbulence(altitude_m=25.0, mean_wind_10m_m_s=(4.0, -1.5, 0.0), turbulence_intensity=0.15, seed=42)
    t2 = evaluate_spatial_turbulence(altitude_m=25.0, mean_wind_10m_m_s=(4.0, -1.5, 0.0), turbulence_intensity=0.15, seed=42)
    assert t1["gust_samples_m_s"] == t2["gust_samples_m_s"]
    assert t1["shear_scale"] > 1.0

    dry = isa_atmosphere_1976(500.0, relative_humidity=0.0, temperature_offset_k=0.0)
    hot_humid = isa_atmosphere_1976(500.0, relative_humidity=0.90, temperature_offset_k=15.0)
    assert hot_humid.density_kg_m3 < dry.density_kg_m3

    with pytest.raises(ValueError, match="turbulence_intensity"):
        evaluate_spatial_turbulence(altitude_m=10.0, mean_wind_10m_m_s=(1.0, 0.0, 0.0), turbulence_intensity=0.95)
