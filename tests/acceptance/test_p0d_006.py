"""P0D-006: Rain liquid-water drag penalty, wet CL_max reduction, and extreme precipitation refusal."""

from __future__ import annotations

import pytest

from physics.environment.adverse_weather import evaluate_rain_wet_effects


def test_p0d_006_rain_wet_degradation_and_extreme_refusal():
    dry = evaluate_rain_wet_effects(rain_mm_h=0.0)
    rainy = evaluate_rain_wet_effects(rain_mm_h=30.0)
    assert rainy["wet_cd0"] > dry["wet_cd0"]
    assert rainy["wet_cl_max"] < dry["wet_cl_max"]
    assert rainy["status"] == "SUPPORTED_WITH_CAVEATS"

    with pytest.raises(ValueError, match="Extreme precipitation"):
        evaluate_rain_wet_effects(rain_mm_h=150.0)
