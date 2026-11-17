"""Deterministic closed-loop simulation harness.

Runs the plant at a fixed control period with RK4 substeps between control
ticks, applies scheduled disturbance forces/torques, and records telemetry.
Deterministic by construction (fixed steps, no noise) — sensor noise and
delay models arrive with M4's sensor models.

Verification: tests/physics/test_controller.py (hover hold, disturbance
rejection, 5° roll command per the spec's checkpoint, yaw hold, mixer wrench
reconstruction).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from physics.integration.runtime_limit import check_time_limit

from physics.controller.attitude import ControlTargets, QuadcopterController
from physics.dynamics.quaternion import conjugate, rotate
from physics.dynamics.rigid_body import RigidBody, make_state, normalize_state, unpack_state
from physics.dynamics.quadrotor import MultirotorPlant
from physics.integration.rk4 import rk4_step


@dataclass
class Disturbance:
    """Constant world-frame force and/or body-frame torque applied over a
    time window [t_start, t_end]."""

    t_start: float
    t_end: float
    force_world: np.ndarray | None = None  # (3,) N
    torque_body: np.ndarray | None = None  # (3,) N·m

    def active(self, t: float) -> bool:
        return self.t_start <= t <= self.t_end


@dataclass
class TelemetryResult:
    times: np.ndarray
    states: np.ndarray  # (N, 13)
    thrusts: np.ndarray  # (N, n_rotors)
    alt_commands: np.ndarray  # (N,) accel commands (diagnostic)
    disturbances: list[Disturbance] = field(default_factory=list)

    def state_at(self, t: float) -> np.ndarray:
        idx = int(np.searchsorted(self.times, t))
        idx = min(max(idx, 0), len(self.times) - 1)
        return self.states[idx]

    def final_state(self) -> np.ndarray:
        return self.states[-1]


def run_controlled_simulation(
    plant: MultirotorPlant,
    controller: QuadcopterController,
    targets: ControlTargets,
    duration_s: float,
    control_dt_s: float = 0.004,
    substeps: int = 2,
    disturbances: list[Disturbance] | None = None,
    initial_state: np.ndarray | None = None,
    record_every: int = 1,
) -> TelemetryResult:
    """Closed-loop hover/attitude simulation (fixed-step, deterministic)."""
    if control_dt_s <= 0.0 or substeps < 1:
        raise ValueError("control_dt_s must be > 0 and substeps >= 1")
    dt = control_dt_s / substeps
    disturbances = disturbances or []
    controller.reset()  # every run starts from a clean controller state

    if initial_state is None:
        state = make_state(
            r_world=np.zeros(3),
            v_world=np.zeros(3),
            q_bw=np.array([1.0, 0.0, 0.0, 0.0]),
            omega_body=np.zeros(3),
        )
    else:
        state = normalize_state(np.asarray(initial_state, dtype=float))

    body: RigidBody = plant.body
    n_steps = int(round(duration_s / control_dt_s))
    times, states, thrusts_log, alt_cmd_log = [], [], [], []

    for k in range(n_steps):
        check_time_limit()
        t = k * control_dt_s
        thrusts = controller.step(state, targets, control_dt_s)

        # Applied wrench from the plant + any active disturbance.
        f_body, t_body = plant.net_force_torque(state, thrusts)
        for d in disturbances:
            if d.active(t):
                if d.force_world is not None:
                    f_body = f_body + rotate(conjugate(state[6:10]), d.force_world)
                if d.torque_body is not None:
                    t_body = t_body + np.asarray(d.torque_body, dtype=float)

        def deriv(_t: float, x: np.ndarray) -> np.ndarray:
            # Disturbances are evaluated at the window's control tick (zero-
            # order hold) — recompute plant wrench per substep.
            fb, tb = plant.net_force_torque(x, thrusts)
            for d in disturbances:
                if d.active(_t):
                    if d.force_world is not None:
                        fb = fb + rotate(conjugate(x[6:10]), d.force_world)
                    if d.torque_body is not None:
                        tb = tb + np.asarray(d.torque_body, dtype=float)
            return body.derivs(x, fb, tb)

        for _ in range(substeps):
            state = rk4_step(deriv, t, state, dt)
            state = normalize_state(state)
            t += dt

        if k % record_every == 0:
            times.append(k * control_dt_s)
            states.append(state.copy())
            thrusts_log.append(thrusts.copy())
            alt_cmd_log.append(controller._last_accel_cmd)

    return TelemetryResult(
        times=np.array(times),
        states=np.array(states),
        thrusts=np.array(thrusts_log),
        alt_commands=np.array(alt_cmd_log),
        disturbances=list(disturbances),
    )
