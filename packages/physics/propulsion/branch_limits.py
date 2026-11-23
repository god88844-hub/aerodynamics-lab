"""P0A-012 supported quasi-static branch limits and voltage authority.

The only supported fault dynamics are an ideal branch cutout (zero drive
thrust and reaction torque) and voltage-limited static operation. No rotor
coastdown, blade fragmentation, winding-short drag or fault-tolerant
controller is inferred. Optional branch limits are explicitly supplied
engineering limits, not new measured ratings.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite

from physics.propulsion.dataset import OutOfEnvelopeError, PowertrainDataset


@dataclass(frozen=True)
class BranchLimits:
    """Additional declared hard limits for one zero-based rotor branch.

    Thermal limit is the exposure time above the specified current, not a
    fabricated temperature estimate. Absent optional limits are not assessed.
    """

    max_current_a: float | None = None
    max_voltage_v: float | None = None
    max_rpm: float | None = None
    max_actuator_thrust_n: float | None = None
    thermal_current_a: float | None = None
    thermal_duration_s: float | None = None

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if value is not None and (not isfinite(value) or value <= 0):
                raise ValueError(f"{item.name} must be finite and positive")
        if (self.thermal_current_a is None) != (self.thermal_duration_s is None):
            raise ValueError("thermal exposure requires both current and duration")


@dataclass(frozen=True)
class BranchFailure:
    branch_id: int
    at_s: float
    kind: str = "motor_cutout"

    def __post_init__(self):
        if type(self.branch_id) is not int or self.branch_id < 0:
            raise ValueError("branch_id must be a nonnegative rotor index")
        if not isfinite(self.at_s) or self.at_s < 0:
            raise ValueError("failure time must be finite and nonnegative")

    @property
    def supported(self):
        return self.kind in ("motor_cutout", "esc_cutout")


def attainable_ceiling(dataset: PowertrainDataset, voltage_v: float) -> tuple[float, float]:
    """Maximum supported RPM and thrust at the *loaded* branch voltage.

    Use the existing full-throttle voltage mapping and merged static thrust
    table; never extrapolate above the measured RPM limit or invent a low-
    voltage operating point below the thrust table. The dataset's declared
    voltage interpolation/extrapolation rules still apply.
    """
    rpm_lo, rpm_hi = dataset.envelope()["rpm_range_merged"]
    rpm = min(float(rpm_hi), float(dataset.rpm_at_throttle(1.0, voltage_v).value))
    if not isfinite(rpm) or rpm < rpm_lo:
        raise OutOfEnvelopeError("full-throttle RPM below supported static thrust range")
    return rpm, float(dataset.thrust_n(rpm).value)
