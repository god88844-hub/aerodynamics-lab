"""Static powertrain: N identical motor+ESC+prop units on one shared battery.

MODEL STATUS (M2): static conditions only — hover hold, thrust-bench-style
runs, endurance estimation. No advance ratio / forward-flight effects, no
motor dynamics or controller loop (M3/M4), no thermal integration yet (the
motor's continuous limit is applied as an instantaneous current check with
its datasheet duration caveat).

Every query result carries envelope flags; the hover solution reports them
so reports can state exactly which operating points are measured data vs
voltage-extrapolated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from physics.propulsion.battery import BatteryPack, PowertrainError
from physics.propulsion.dataset import OutOfEnvelopeError, PowertrainDataset, QueryResult
from physics.propulsion.esc import Esc

MAX_BUS_ITERATIONS = 60
BUS_TOLERANCE_V = 1e-4


def _flag_strings(flags: dict, prefix: str = "") -> list[str]:
    """Flatten nested flag dicts into readable strings for reports."""
    out: list[str] = []
    for key, val in flags.items():
        if isinstance(val, dict):
            out.extend(_flag_strings(val, prefix + key + "."))
        elif isinstance(val, bool):
            if val:
                out.append(prefix + key)
        elif isinstance(val, str) and val:
            out.append(f"{prefix}{key}: {val}")
    return out


@dataclass
class UnitPoint:
    throttle: float
    rpm: float
    thrust_n: float
    current_a: float
    power_w: float
    flags: dict = field(default_factory=dict)


@dataclass
class OperatingPoint:
    throttle: float
    v_bus: float
    total_thrust_n: float
    total_current_a: float
    total_power_w: float
    per_unit: UnitPoint
    iterations: int


@dataclass
class HoverSample:
    t_s: float
    soc_pct: float
    v_bus: float
    throttle: float
    total_thrust_n: float
    total_current_a: float
    total_power_w: float
    cell_voltage_loaded_v: float


@dataclass
class StaticHoverResult:
    mass_kg: float
    hover_point: OperatingPoint
    samples: list[HoverSample]
    endurance_to_warning_s: float | None
    endurance_to_cutoff_s: float | None
    energy_used_wh: float
    min_cell_voltage_v: float
    limit_issues: list[str]
    envelope_flags: list[str]


class StaticPowertrain:
    def __init__(
        self,
        dataset: PowertrainDataset,
        esc: Esc,
        battery: BatteryPack,
        units: int,
    ) -> None:
        if units < 1:
            raise ValueError("units must be >= 1")
        self.dataset = dataset
        self.esc = esc
        self.battery = battery
        self.units = units

    # ------------------------------------------------------------- solvers

    def unit_point(self, throttle: float, v_bus: float) -> UnitPoint:
        rpm_res = self.dataset.rpm_at_throttle(throttle, v_bus)
        rpm = rpm_res.value
        thrust_res = self.dataset.thrust_n(rpm)
        current_res = self.dataset.current_a(rpm, v_bus)
        return UnitPoint(
            throttle=throttle,
            rpm=rpm,
            thrust_n=thrust_res.value,
            current_a=current_res.value,
            power_w=current_res.value * v_bus,
            flags={**rpm_res.flags, "current": current_res.flags},
        )

    def solve_bus(self, soc_pct: float, throttle: float) -> tuple[float, UnitPoint, int]:
        """Fixed-point solve: v_bus = OCV(soc) - I_total(v_bus) * R_pack."""
        ocv = self.battery.ocv_pack(soc_pct)
        v_bus = ocv
        unit: UnitPoint | None = None
        for iterations in range(1, MAX_BUS_ITERATIONS + 1):
            unit = self.unit_point(throttle, v_bus)
            total_current = unit.current_a * self.units
            v_new = self.battery.voltage_under_load(soc_pct, total_current)
            if abs(v_new - v_bus) < BUS_TOLERANCE_V:
                v_bus = v_new
                # Recompute the unit point at the converged bus voltage.
                unit = self.unit_point(throttle, v_bus)
                return v_bus, unit, iterations
            v_bus = 0.5 * (v_bus + v_new)  # damped
        raise PowertrainError(
            f"bus voltage solve did not converge (last v_bus={v_bus:.3f} V)"
        )

    def operating_point(self, throttle: float, soc_pct: float) -> OperatingPoint:
        v_bus, unit, iters = self.solve_bus(soc_pct, throttle)
        return OperatingPoint(
            throttle=throttle,
            v_bus=v_bus,
            total_thrust_n=unit.thrust_n * self.units,
            total_current_a=unit.current_a * self.units,
            total_power_w=unit.power_w * self.units,
            per_unit=unit,
            iterations=iters,
        )

    def throttle_for_total_thrust(self, target_total_n: float, soc_pct: float) -> float:
        """Inverse solve of the per-unit thrust against the bus-voltage loop.

        Thrust comes from the measured static table (bus-independent at static
        conditions), so the throttle solves directly in rpm space and only the
        current/v_bus pair needs the fixed-point iteration.
        """
        target_unit = target_total_n / self.units
        v_bus = self.battery.ocv_pack(soc_pct)
        throttle: float | None = None
        for _ in range(MAX_BUS_ITERATIONS):
            res = self.dataset.inverse_throttle_for_unit_thrust(target_unit, v_bus)
            throttle = res.value
            rpm = self.dataset.rpm_at_throttle(throttle, v_bus).value
            current = self.dataset.current_a(rpm, v_bus).value
            v_new = self.battery.voltage_under_load(soc_pct, current * self.units)
            if abs(v_new - v_bus) < BUS_TOLERANCE_V:
                break
            v_bus = 0.5 * (v_bus + v_new)
        else:
            raise PowertrainError("thrust inverse bus solve did not converge")
        assert throttle is not None
        return throttle

    # ------------------------------------------------------------- scenarios

    def static_hover(
        self,
        total_mass_kg: float,
        max_duration_s: float = 3600.0,
        dt_s: float = 1.0,
        soc_start_pct: float = 100.0,
        stop_at_warning: bool = True,
    ) -> StaticHoverResult:
        """Simulate a stationary hover until battery warning/cutoff or
        ``max_duration_s``. Thrust held exactly at m*g (trim); battery drained
        by coulomb counting; every step checked against ESC/motor limits."""
        if total_mass_kg <= 0:
            raise ValueError("mass must be > 0")
        from physics.constants import STANDARD_GRAVITY

        target_total = total_mass_kg * STANDARD_GRAVITY
        # Starting point sanity: a pack already below the cutoff cannot hover.
        start_status = self.battery.status(soc_start_pct, 0.0)
        if start_status.cutoff:
            raise PowertrainError(
                "battery starts below the cutoff voltage — hover impossible at "
                f"{soc_start_pct:.0f}% SOC"
            )

        samples: list[HoverSample] = []
        issues: list[str] = []
        envelope_flags: list[str] = []
        soc = soc_start_pct
        t = 0.0
        energy_wh = 0.0
        min_cell_v = float("inf")
        end_warning: float | None = None
        end_cutoff: float | None = None
        throttle = self.throttle_for_total_thrust(target_total, soc_start_pct)

        while t <= max_duration_s + 1e-9:
            # Altitude-hold assumption: thrust re-trimmed to m*g every step as
            # the bus voltage sags (perfect controller, documented).
            throttle = self.throttle_for_total_thrust(target_total, soc)
            op = self.operating_point(throttle, soc)
            status = self.battery.status(soc, op.total_current_a)
            min_cell_v = min(min_cell_v, status.cell_voltage_loaded_v)
            samples.append(
                HoverSample(
                    t_s=t,
                    soc_pct=soc,
                    v_bus=op.v_bus,
                    throttle=throttle,
                    total_thrust_n=op.total_thrust_n,
                    total_current_a=op.total_current_a,
                    total_power_w=op.total_power_w,
                    cell_voltage_loaded_v=status.cell_voltage_loaded_v,
                )
            )
            for flag in _flag_strings(op.per_unit.flags):
                if flag not in envelope_flags:
                    envelope_flags.append(flag)

            # Component limit checks (fail-closed policy: recorded as issues).
            issues.extend(self.esc.check(op.total_current_a, op.v_bus))
            motor = self.dataset.motor
            if (
                motor.max_continuous_current_a is not None
                and op.per_unit.current_a > motor.max_continuous_current_a
            ):
                issues.append(
                    f"motor over continuous current: {op.per_unit.current_a:.1f} A > "
                    f"{motor.max_continuous_current_a:.1f} A (180 s rating)"
                )

            if status.cutoff and end_cutoff is None:
                end_cutoff = t
                break
            if status.warning and end_warning is None:
                end_warning = t
                if stop_at_warning:
                    break

            energy_wh += op.total_power_w * dt_s / 3600.0
            soc = self.battery.soc_after(soc, op.total_current_a, dt_s)
            t += dt_s

        return StaticHoverResult(
            mass_kg=total_mass_kg,
            # The headline hover point is the FULL-CHARGE operating point:
            # throttle re-solved at soc_start (the loop variable held the last
            # step's depleted-SOC throttle).
            hover_point=self.operating_point(
                self.throttle_for_total_thrust(target_total, soc_start_pct),
                soc_start_pct,
            ),
            samples=samples,
            endurance_to_warning_s=end_warning,
            endurance_to_cutoff_s=end_cutoff,
            energy_used_wh=energy_wh,
            min_cell_voltage_v=min_cell_v,
            limit_issues=sorted(set(issues)),
            envelope_flags=sorted(set(envelope_flags)),
        )
