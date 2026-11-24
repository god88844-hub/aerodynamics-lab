"""Per-rotor limits for the quasi-static flight plant, in SI units."""

from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite


@dataclass(frozen=True)
class BranchLimits:
    """Optional installed ratings in addition to the shared motor/ESC ratings.

    Series resistance is upstream of the ESC. The thermal monitor is an
    above-current dwell limit, not a model of winding temperature.
    """

    series_resistance_ohm: float = 0.0
    max_current_a: float | None = None
    min_voltage_v: float | None = None
    max_voltage_v: float | None = None
    max_rpm: float | None = None
    max_thrust_n: float | None = None
    thermal_current_a: float | None = None
    thermal_duration_s: float | None = None

    def __post_init__(self) -> None:
        for spec in fields(self):
            value = getattr(self, spec.name)
            if value is not None and (
                not isfinite(value) or value < 0
                or (value == 0 and spec.name != "series_resistance_ohm")
            ):
                raise ValueError(f"invalid branch {spec.name}: {value}")
        if (self.thermal_current_a is None) != (self.thermal_duration_s is None):
            raise ValueError("branch thermal current and duration must be declared together")
        if (self.min_voltage_v is not None and self.max_voltage_v is not None
                and self.min_voltage_v > self.max_voltage_v):
            raise ValueError("branch minimum voltage exceeds maximum voltage")


@dataclass(frozen=True)
class BranchFailure:
    """A fault at a declared time. Only motor_cutout and esc_cutout are modeled."""

    branch_id: int
    at_s: float
    kind: str

    def __post_init__(self) -> None:
        if not isfinite(self.at_s) or self.at_s < 0:
            raise ValueError("branch failure time must be finite and nonnegative")


@dataclass(frozen=True)
class BranchFinding:
    branch_id: int
    component: str
    limit: str
    observed: float | None = None
    threshold: float | None = None
    unit: str | None = None
    status: str = "FAIL"


def limit_findings(
    branch_id: int, limits: BranchLimits, current: float, voltage: float,
    rpm: float, thrust: float,
) -> list[BranchFinding]:
    checks = (
        ("esc", "branch_current", current, limits.max_current_a, "A", False),
        ("esc", "branch_undervoltage", voltage, limits.min_voltage_v, "V", True),
        ("esc", "branch_overvoltage", voltage, limits.max_voltage_v, "V", False),
        ("motor", "rotor_rpm", rpm, limits.max_rpm, "rpm", False),
        ("actuator", "actuator_thrust", thrust, limits.max_thrust_n, "N", False),
    )
    return [
        BranchFinding(branch_id, component, name, value, threshold, unit)
        for component, name, value, threshold, unit, below in checks
        if threshold is not None and (value < threshold if below else value > threshold)
    ]
