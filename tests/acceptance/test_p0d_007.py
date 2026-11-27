"""P0D-007: Icing accretion, drag growth, anti-ice melting/shedding, and cold envelope guard."""

from __future__ import annotations

import pytest

from physics.environment.adverse_weather import evaluate_icing_and_shedding


def test_p0d_007_icing_accretion_melting_shedding_and_bounds():
    warm = evaluate_icing_and_shedding(oat_c=10.0, lwc_g_m3=0.5, exposure_s=10.0)
    assert warm["icing_active"] is False

    unheated = evaluate_icing_and_shedding(oat_c=-4.0, lwc_g_m3=0.5, exposure_s=30.0, anti_ice_power_w=0.0)
    heated = evaluate_icing_and_shedding(oat_c=-4.0, lwc_g_m3=0.5, exposure_s=30.0, anti_ice_power_w=2.5)
    assert unheated["icing_active"] is True
    assert unheated["accreted_mass_kg"] > heated["accreted_mass_kg"]
    assert unheated["drag_multiplier"] > 1.0
    assert heated["shedding_event"] is True

    with pytest.raises(ValueError, match="OAT"):
        evaluate_icing_and_shedding(oat_c=-40.0, lwc_g_m3=0.4, exposure_s=10.0)
