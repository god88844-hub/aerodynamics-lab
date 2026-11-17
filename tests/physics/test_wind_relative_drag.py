"""M24 analytic *software verification*, NOT physical wind-tunnel validation.

Uniform wind influences first-order airframe drag only. Rotor inflow, gusts,
installation effects and controller rejection are not modeled by these tests.
"""
import numpy as np
import pytest

from physics.aerodynamics.drag import AirframeDrag
from physics.dynamics.quadrotor import MultirotorPlant, Rotor
from physics.dynamics.rigid_body import RigidBody, make_state


def state(v=(0, 0, 0)):
    return make_state(
        r_world=np.zeros(3), v_world=np.array(v, dtype=float),
        q_bw=np.array([1.0, 0, 0, 0]), omega_body=np.zeros(3),
    )


def test_no_wind_keeps_existing_quadratic_drag():
    drag = AirframeDrag(cd_a_m2=2, rho_kg_m3=1)
    assert np.allclose(drag.force_world(np.array([3., 4., 0.])), [-15., -20., 0.])
    assert np.array_equal(drag.force_world([0., 0., 0.]), np.zeros(3))
    assert np.allclose(drag.force_world([3., 4., 0.], [0., 0., 0.]),
                       [-15., -20., 0.])


def test_stationary_body_in_headwind_experiences_downwind_force():
    drag = AirframeDrag(cd_a_m2=2, rho_kg_m3=1)
    # v_airframe=0, v_air=+3 m/s; relative airspeed is -3 m/s.
    assert np.allclose(drag.force_world([0., 0., 0.], [3., 0., 0.]),
                       [9., 0., 0.])


def test_moving_along_with_air_has_zero_relative_drag():
    drag = AirframeDrag(cd_a_m2=.5, rho_kg_m3=1.225)
    assert np.array_equal(
        drag.force_world([10., -2., .5], [10., -2., .5]),
        np.zeros(3),
    )


def test_galilean_velocity_shift_does_not_change_drag():
    drag = AirframeDrag(cd_a_m2=.33, rho_kg_m3=1.1)
    v = np.array([8., 2., -1.])
    w = np.array([3., -1., .1])
    shift = np.array([200., 4., 0.])
    assert np.allclose(drag.force_world(v, w),
                       drag.force_world(v + shift, w + shift))


def test_wind_acts_only_when_explicitly_attached_to_airframe_plant():
    body = RigidBody(2., np.eye(3))
    drag = AirframeDrag(cd_a_m2=2., rho_kg_m3=1.)
    calm = MultirotorPlant(body=body, rotors=[], drag=drag)
    windy = MultirotorPlant(body=body, rotors=[], drag=drag,
                           wind_world=np.array([3., 0., 0.]))
    f_calm, t_calm = calm.net_force_torque(state(), np.zeros(0))
    f_wind, t_wind = windy.net_force_torque(state(), np.zeros(0))
    assert np.array_equal(f_calm, np.zeros(3))
    assert np.array_equal(t_calm, np.zeros(3))
    assert np.allclose(f_wind, [9., 0., 0.])
    assert np.array_equal(t_wind, np.zeros(3))
    assert not hasattr(windy, "wind_powertrain_validated")


def test_relative_wind_uses_world_frame_not_body_local_axes():
    body = RigidBody(1., np.eye(3))
    drag = AirframeDrag(cd_a_m2=1., rho_kg_m3=1.)
    plant = MultirotorPlant(body=body, rotors=[], drag=drag,
                            wind_world=np.array([0., 2., 0.]))
    f, _ = plant.net_force_torque(state(v=(0, 0, 0)), np.zeros(0))
    assert np.allclose(f, [0., 2., 0.])


@pytest.mark.parametrize("bad", [
    [1., 2.], [1., 2., 3., 4.], [0., np.nan, 0.],
    [np.inf, 0., 0.], [1e308, -1e308, 0.],
])
def test_invalid_relative_airflow_rejected(bad):
    drag = AirframeDrag(cd_a_m2=1., rho_kg_m3=1.)
    with pytest.raises(ValueError, match="finite|overflow"):
        drag.force_world([0., 0., 0.], bad)


@pytest.mark.parametrize("bad", [
    [1., 2.], [np.inf, 0., 0.], [0., np.nan, 0.],
])
def test_invalid_world_velocity_rejected(bad):
    drag = AirframeDrag(cd_a_m2=1., rho_kg_m3=1.)
    with pytest.raises(ValueError, match="finite"):
        drag.force_world(bad)


def test_wind_field_has_explicit_validated_shape_and_nonfinite_thrust_fails_closed():
    body = RigidBody(2., np.eye(3))
    with pytest.raises(ValueError, match="wind_world"):
        MultirotorPlant(body=body, rotors=[], wind_world=np.array([1., np.nan, 0.]))
    plant = MultirotorPlant(
        body=body, rotors=[Rotor(np.array([0., 0., 0.]))],
    )
    with pytest.raises(ValueError, match="finite"):
        plant.net_force_torque(state(), np.array([np.nan]))
    with pytest.raises(ValueError, match="finite"):
        plant.net_force_torque(state(), np.array([np.inf]))


def test_no_wind_does_not_change_ideal_hover_dynamics():
    body = RigidBody(1.5, np.eye(3))
    points = [
        Rotor(np.array([1., 1., 0.])),
        Rotor(np.array([-1., 1., 0.])),
        Rotor(np.array([-1., -1., 0.])),
        Rotor(np.array([1., -1., 0.])),
    ]
    plant = MultirotorPlant(body=body, rotors=points)
    trim = plant.hover_trim()
    assert np.allclose(trim, np.full(4, 1.5 * 9.80665 / 4))
    f, torque = plant.net_force_torque(state(), trim)
    assert f[2] == pytest.approx(1.5 * 9.80665)
    assert np.allclose(torque, np.zeros(3), atol=1e-12)
