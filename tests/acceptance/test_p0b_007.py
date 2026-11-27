"""P0B-007: Fixed-wing propulsion, trim, control surfaces, and shared 6-DoF flight plant."""

from __future__ import annotations

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import compute_fixed_wing_cruise_trim
from physics.aerodynamics.sixdof_fixed_wing import build_derivatives_from_wing, simulate_6dof_fixed_wing


def test_p0b_007_cruise_trim_feasibility_and_infeasible_thrust_detection():
    wing = ParametricWingSpec(name="TrimWing", wingspan_m=1.8, root_chord_m=0.26, tip_chord_m=0.14)
    ok_trim = compute_fixed_wing_cruise_trim(wing, mass_kg=1.8, airspeed_m_s=18.0, max_thrust_n=12.0)
    assert ok_trim["trim_feasible"] is True
    assert 0.0 < ok_trim["thrust_required_n"] <= 12.0

    infeasible = compute_fixed_wing_cruise_trim(wing, mass_kg=1.8, airspeed_m_s=18.0, max_thrust_n=0.2)
    assert infeasible["trim_feasible"] is False


def test_p0b_007_control_surface_deflection_6dof_response():
    wing = ParametricWingSpec(name="CtrlWing", wingspan_m=1.8, root_chord_m=0.25, tip_chord_m=0.15)
    derivs = build_derivatives_from_wing(wing)
    neutral = simulate_6dof_fixed_wing(aero=derivs, elevator_rad=0.0, aileron_rad=0.0, duration_s=0.4, dt_s=0.01)
    rolled = simulate_6dof_fixed_wing(aero=derivs, elevator_rad=0.0, aileron_rad=0.08, duration_s=0.4, dt_s=0.01)
    assert rolled["final_quaternion_wxyz"] != neutral["final_quaternion_wxyz"]
    assert abs(rolled["final_position_m"][1]) > abs(neutral["final_position_m"][1])
