"""P0C-007: Transient electrical bus sag, I^2 R losses, thermal limit derating, and estimate tagging."""

from __future__ import annotations

from physics.aerodynamics.rotorcraft_vtol import run_coupled_electro_thermal_rotor_transient


def test_p0c_007_electro_thermal_transient_and_overtemp_fail():
    ok = run_coupled_electro_thermal_rotor_transient(demand_power_w=550.0, max_winding_temp_c=110.0)
    assert ok["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert ok["power_balance_residual_w"] < 1e-6
    assert ok["thermal_parameter_status"] == "UNVERIFIED_ESTIMATE"
    assert ok["min_bus_voltage_v"] < 22.2

    hot_fail = run_coupled_electro_thermal_rotor_transient(demand_power_w=1400.0, max_winding_temp_c=40.0, duration_s=10.0)
    assert hot_fail["verdict"] == "FAIL"
