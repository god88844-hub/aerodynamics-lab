"""P0B-008: Stall, load factor, overspeed, and conflicting/absent limit enforcement."""

from __future__ import annotations

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import run_fixed_wing_mission
from physics.aerodynamics.sixdof_fixed_wing import simulate_6dof_fixed_wing


def test_p0b_008_structural_load_and_overspeed_fail():
    wing = ParametricWingSpec(name="EnvWing", wingspan_m=1.8, root_chord_m=0.26, tip_chord_m=0.14)
    load_fail = run_fixed_wing_mission(wing, mass_kg=1.8, max_load_factor_g=0.95, duration_s=2.0)
    assert load_fail["verdict"] == "FAIL"
    assert "Load factor" in (load_fail["abort_reason"] or "")

    speed_fail = run_fixed_wing_mission(wing, mass_kg=1.8, initial_airspeed_m_s=24.0, max_airspeed_m_s=20.0, duration_s=2.0)
    assert speed_fail["verdict"] == "FAIL"
    assert "Overspeed" in (speed_fail["abort_reason"] or "")


def test_p0b_008_stall_and_conflicting_limits_rejected():
    with pytest.raises(ValueError, match="Conflicting or invalid load-factor"):
        wing = ParametricWingSpec(name="ConflictWing", wingspan_m=1.6, root_chord_m=0.22, tip_chord_m=0.14)
        run_fixed_wing_mission(wing, mass_kg=1.5, min_load_factor_g=4.0, max_load_factor_g=2.0)

    with pytest.raises(ValueError, match="Post-stall AoA"):
        simulate_6dof_fixed_wing(initial_airspeed_m_s=10.0, elevator_rad=-0.45, duration_s=1.0)
