"""P0C-006: Coupled VTOL hover-to-cruise and cruise-to-hover transitions and stall/thrust rejection."""

from __future__ import annotations

from physics.aerodynamics.rotorcraft_vtol import run_vtol_transition_corridor


def test_p0c_006_vtol_forward_and_reverse_transition_and_envelope_fail():
    fwd = run_vtol_transition_corridor(mass_kg=3.0, wing_area_m2=0.45, max_rotor_thrust_n=50.0, max_cruise_thrust_n=25.0, direction="hover_to_cruise")
    assert fwd["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert fwd["samples"][0]["tilt_deg"] == 90.0
    assert fwd["samples"][-1]["tilt_deg"] == 0.0

    rev = run_vtol_transition_corridor(mass_kg=3.0, wing_area_m2=0.45, max_rotor_thrust_n=50.0, max_cruise_thrust_n=25.0, direction="cruise_to_hover")
    assert rev["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert rev["samples"][0]["tilt_deg"] == 0.0
    assert rev["samples"][-1]["tilt_deg"] == 90.0

    stall_fail = run_vtol_transition_corridor(mass_kg=3.0, wing_area_m2=0.45, max_rotor_thrust_n=50.0, max_cruise_thrust_n=25.0, stall_speed_m_s=28.0)
    assert stall_fail["verdict"] == "FAIL"
