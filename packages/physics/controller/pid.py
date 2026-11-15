"""Discrete-time PID controller with anti-windup and output limits.

Anti-windup strategy: when the output saturates, the integral is *tracked*
to the value that exactly produces the saturated output given the current
error (integral tracking / back-calculation). This makes recovery from
saturation immediate — no stored windup to unwind.

Verified in tests/physics/test_pid.py: steady-state error elimination via the
integral term, derivative damping on a second-order plant, and anti-windup
recovery.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PID:
    kp: float
    ki: float = 0.0
    kd: float = 0.0
    output_limits: tuple[float, float] | None = None
    integral_limits: tuple[float, float] | None = None
    # State
    integral: float = field(default=0.0)
    _prev_measurement: float | None = field(default=None, repr=False)

    def reset(self) -> None:
        self.integral = 0.0
        self._prev_measurement = None

    def step(self, error: float, measurement: float, dt: float) -> float:
        """One control step. Derivative acts on the measurement (derivative-on-
        measurement), which avoids setpoint-derivative kicks."""
        if dt <= 0.0:
            raise ValueError("dt must be > 0")

        # Derivative on measurement.
        d = 0.0
        if self._prev_measurement is not None and self.kd != 0.0:
            d = -(measurement - self._prev_measurement) / dt
        self._prev_measurement = measurement

        # Integral accumulation (anti-windup tracking may overwrite it below
        # when the output saturates).
        self.integral += error * dt

        u_unsat = self.kp * error + self.ki * self.integral + self.kd * d

        if self.output_limits is None:
            u = u_unsat
        else:
            lo, hi = self.output_limits
            if self.ki != 0.0 and u_unsat > hi:
                # Integral tracking: hold the integral at the value that
                # produces exactly the saturated output (no windup stored).
                self.integral = (hi - self.kp * error - self.kd * d) / self.ki
                u = hi
            elif self.ki != 0.0 and u_unsat < lo:
                self.integral = (lo - self.kp * error - self.kd * d) / self.ki
                u = lo
            else:
                u = u_unsat

        if self.integral_limits is not None:
            ilo, ihi = self.integral_limits
            self.integral = min(max(self.integral, ilo), ihi)
        return u
