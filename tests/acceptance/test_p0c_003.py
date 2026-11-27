"""P0C-003: Rotor torque balance, main/tail/coaxial/tandem control trim, and saturation FAIL bounds."""

from __future__ import annotations

import pytest

from physics.aerodynamics.rotorcraft_vtol import solve_helicopter_control_trim


def test_p0c_003_helicopter_torque_balance_and_saturation():
    for layout in ("main_tail", "coaxial", "tandem"):
        ok = solve_helicopter_control_trim(layout=layout, main_torque_nm=6.5, tail_arm_m=0.95, max_tail_thrust_n=18.0, cyclic_cmd_deg=4.0)
        assert ok["verdict"] == "NO_MODELED_LIMIT_BREACHED"
        assert ok["yaw_authority_margin"] > 1.0

    yaw_fail = solve_helicopter_control_trim(layout="main_tail", main_torque_nm=30.0, tail_arm_m=0.95, max_tail_thrust_n=18.0)
    assert yaw_fail["verdict"] == "FAIL"

    cyclic_fail = solve_helicopter_control_trim(layout="coaxial", main_torque_nm=5.0, cyclic_cmd_deg=15.0, max_cyclic_deg=10.0)
    assert cyclic_fail["verdict"] == "FAIL"

    with pytest.raises(ValueError, match="Unsupported helicopter layout"):
        solve_helicopter_control_trim(layout="monorotor", main_torque_nm=5.0)
