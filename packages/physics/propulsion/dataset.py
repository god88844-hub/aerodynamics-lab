"""Static powertrain dataset — the model of record for M2 propulsion.

MODEL STATUS: measured-data interpolation (highest available fidelity for
static conditions). The manufacturer bench table (T-Motor test report
MN.00011) is interpolated directly; no physics formula substitutes for the
data inside the measured envelope.

Interpolation scheme
--------------------
- ``thrust_gf(rpm)``: monotone PCHIP over the merged static points from all
  measured voltage planes (static thrust is set by rpm; residual
  cross-voltage scatter in the overlap band is recorded as dataset scatter
  and folded into the uncertainty).
- ``current_a(rpm, voltage)``: PCHIP in rpm per voltage plane. Between the
  measured plane voltages: linear interpolation between the planes. Outside
  them: linear-in-voltage slope correction fitted from the planes' overlap
  band, flagged as extrapolation. Voltage excursions beyond ±15 % of the
  measured range are refused (fail-closed).
- ``rpm(throttle, voltage)``: PCHIP per plane over that plane's measured
  throttle knots, interpolated linearly in voltage between planes;
  extrapolation below the lowest measured knot (50 %) is allowed down to
  35 % with an explicit flag.
- electrical power is ``v_bus * current`` (exact DC identity) — the table's
  power column is reproduced at the measured plane voltages.

KNOWN PHYSICS CROSS-CHECK FINDING (documented, not hidden): a lumped DC motor
model using the datasheet Kv (380 rpm/V) and winding resistance (205 mOhm)
does NOT reproduce the loaded bench points — inductive/timing effects of the
BLDC+ESC chain dominate. The lumped model is therefore a reported cross-check
(see physics/validation/benchmarks.py), not the model of record.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from aeroforge_schemas.component import MotorSpec
from physics.constants import GF_TO_N

# Allowable voltage excursion relative to the measured plane range.
VOLTAGE_EXTRAP_LOW_FRAC = 0.85
VOLTAGE_EXTRAP_HIGH_FRAC = 1.15
# Throttle extrapolation floor below the lowest measured knot (typically 50 %).
THROTTLE_EXTRAP_MIN_PCT = 35.0
# Tolerance for "at the measured plane voltage".
V_TOLERANCE_V = 0.3
# Beyond this excursion from the plane voltage, the linear slope correction
# is floored by a power-based current estimate (eta assumption flagged).
FAR_FROM_PLANE_V = 2.0
# Shaft-power estimate assumption for out-of-envelope current floors. The
# same eta=0.8 assumption is used for the rotor reaction-torque estimate;
# both are flagged estimates until a motor dyno run is captured.
MOTOR_EFFICIENCY_ASSUMED = 0.8


class OutOfEnvelopeError(ValueError):
    """Query outside the measured/validated envelope — fail closed."""


@dataclass
class QueryResult:
    """A scalar query plus envelope flags (every flag must surface in reports)."""

    value: float
    plane_voltage_v: float
    voltage_corrected: bool = False
    voltage_extrapolated: bool = False
    throttle_extrapolated: bool = False
    note: str = ""

    @property
    def flags(self) -> dict:
        return {
            "voltage_corrected": self.voltage_corrected,
            "voltage_extrapolated": self.voltage_extrapolated,
            "throttle_extrapolated": self.throttle_extrapolated,
            "note": self.note,
        }


@dataclass
class _Plane:
    """One voltage plane of the bench table (measurements at a fixed supply V)."""

    voltage_v: float
    rpm: np.ndarray
    thrust_gf: np.ndarray
    current_a: np.ndarray
    throttle_pct: np.ndarray
    thrust_interp: PchipInterpolator = field(init=False)
    current_interp: PchipInterpolator = field(init=False)
    rpm_from_throttle: PchipInterpolator = field(init=False)

    def __post_init__(self) -> None:
        # Sort rows by rpm, keeping row alignment; then build the
        # throttle -> rpm mapping from the same (now aligned) rows.
        order = np.argsort(self.rpm)
        self.rpm = self.rpm[order]
        self.thrust_gf = self.thrust_gf[order]
        self.current_a = self.current_a[order]
        self.throttle_pct = self.throttle_pct[order]

        thr_order = np.argsort(self.throttle_pct)
        thr_pct_sorted = self.throttle_pct[thr_order]
        rpm_by_throttle = self.rpm[thr_order]
        if not np.all(np.diff(rpm_by_throttle) > 0):
            raise ValueError("throttle->rpm mapping is not strictly increasing")
        if not np.all(np.diff(self.rpm) > 0):
            raise ValueError("duplicate rpm rows within one voltage plane")

        self.thrust_interp = PchipInterpolator(self.rpm, self.thrust_gf)
        self.current_interp = PchipInterpolator(self.rpm, self.current_a)
        self.rpm_from_throttle = PchipInterpolator(thr_pct_sorted, rpm_by_throttle)

    @property
    def rpm_range(self) -> tuple[float, float]:
        return float(self.rpm[0]), float(self.rpm[-1])

    @property
    def throttle_range(self) -> tuple[float, float]:
        return float(self.throttle_pct[0]), float(self.throttle_pct[-1])

    def contains_rpm(self, rpm: float) -> bool:
        lo, hi = self.rpm_range
        return lo <= rpm <= hi


class PowertrainDataset:
    """Measured static bench data for one motor + propeller combination."""

    def __init__(self, motor: MotorSpec, prop_key: str) -> None:
        self.motor = motor
        self.prop_key = prop_key
        rows = [d for d in motor.test_data if d.prop == prop_key]
        if not rows:
            raise ValueError(f"no test data for prop {prop_key!r} in motor {motor.id!r}")

        by_voltage: dict[float, list] = {}
        for d in rows:
            by_voltage.setdefault(d.voltage_v, []).append(d)
        self.planes: list[_Plane] = [
            _Plane(
                voltage_v=voltage,
                rpm=np.array([r.rpm for r in vrows], dtype=float),
                thrust_gf=np.array([r.thrust_gf for r in vrows], dtype=float),
                current_a=np.array([r.current_a for r in vrows], dtype=float),
                throttle_pct=np.array([r.throttle_pct for r in vrows], dtype=float),
            )
            for voltage, vrows in sorted(by_voltage.items())
        ]
        self._v_min = min(p.voltage_v for p in self.planes)
        self._v_max = max(p.voltage_v for p in self.planes)

        self._build_merged_thrust()
        self._current_voltage_slope = self._fit_voltage_slope()

    # ---------------------------------------------------------------- build

    def _build_merged_thrust(self) -> None:
        points: list[tuple[float, float]] = []
        for p in self.planes:
            points.extend(zip(p.rpm.tolist(), p.thrust_gf.tolist()))
        points.sort()
        rpm = np.array([r for r, _ in points])
        gf = np.array([t for _, t in points])
        if np.any(np.diff(gf) < -1e-9):
            raise ValueError("merged static thrust table is not monotone in rpm")
        self._merged_rpm = rpm
        self._merged_thrust_gf = gf
        self._thrust_interp = PchipInterpolator(rpm, gf)

        # Cross-voltage scatter in the planes' overlap band -> dataset scatter.
        scatter = 0.0
        if len(self.planes) >= 2:
            lo = max(p.rpm_range[0] for p in self.planes)
            hi = min(p.rpm_range[1] for p in self.planes)
            if hi > lo:
                grid = np.linspace(lo, hi, 25)
                vals = np.array([p.thrust_interp(grid) for p in self.planes])
                mean = vals.mean(axis=0)
                scatter = float(np.max(np.abs(vals - mean) / mean)) * 100.0
        self.scatter_pct = scatter

    def _fit_voltage_slope(self) -> float:
        """d(current)/d(voltage) fitted in the planes' overlap band (A per V)."""
        if len(self.planes) < 2:
            return 0.0
        lo = max(p.rpm_range[0] for p in self.planes)
        hi = min(p.rpm_range[1] for p in self.planes)
        if hi <= lo:
            return 0.0
        grid = np.linspace(lo, hi, 25)
        i_lo = self.planes[0].current_interp(grid)
        i_hi = self.planes[1].current_interp(grid)
        dv = self.planes[1].voltage_v - self.planes[0].voltage_v
        return float(np.mean(i_hi - i_lo) / dv)

    # --------------------------------------------------------------- queries

    def thrust_gf(self, rpm: float) -> QueryResult:
        lo, hi = float(self._merged_rpm[0]), float(self._merged_rpm[-1])
        if not lo <= rpm <= hi:
            raise OutOfEnvelopeError(
                f"rpm {rpm:.0f} outside measured static range [{lo:.0f}, {hi:.0f}] "
                f"for {self.prop_key!r}"
            )
        return QueryResult(
            value=float(self._thrust_interp(rpm)), plane_voltage_v=self._v_max
        )

    def thrust_n(self, rpm: float) -> QueryResult:
        res = self.thrust_gf(rpm)
        res.value *= GF_TO_N
        return res

    @property
    def supported_voltage_range(self) -> tuple[float, float]:
        return (self._v_min * VOLTAGE_EXTRAP_LOW_FRAC,
                self._v_max * VOLTAGE_EXTRAP_HIGH_FRAC)

    def _voltage_allowed(self, voltage: float) -> bool:
        lo, hi = self.supported_voltage_range
        return lo <= voltage <= hi

    def _voltage_extrapolated(self, voltage: float) -> bool:
        return voltage < self._v_min or voltage > self._v_max

    def current_a(self, rpm: float, voltage: float) -> QueryResult:
        if not self._voltage_allowed(voltage):
            raise OutOfEnvelopeError(
                f"voltage {voltage:.2f} V outside allowed excursion "
                f"[{self._v_min * VOLTAGE_EXTRAP_LOW_FRAC:.1f}, "
                f"{self._v_max * VOLTAGE_EXTRAP_HIGH_FRAC:.1f}] V "
                f"(measured planes: {self._v_min}/{self._v_max} V)"
            )
        covering = [p for p in self.planes if p.contains_rpm(rpm)]
        if not covering:
            raise OutOfEnvelopeError(
                f"rpm {rpm:.0f} outside all measured planes' rpm ranges "
                f"{[p.rpm_range for p in self.planes]} for {self.prop_key!r}"
            )

        if len(covering) >= 2 and self._v_min <= voltage <= self._v_max:
            # Strictly between measured planes (or on them): linear in voltage.
            p1, p2 = covering[0], covering[-1]
            i1 = float(p1.current_interp(rpm))
            i2 = float(p2.current_interp(rpm))
            value = i1 + (i2 - i1) * (voltage - p1.voltage_v) / (p2.voltage_v - p1.voltage_v)
            return QueryResult(
                value=max(value, 0.0),
                plane_voltage_v=p1.voltage_v,
                voltage_corrected=True,
                voltage_extrapolated=self._voltage_extrapolated(voltage),
                note="current linearly interpolated in voltage between measured planes",
            )

        # Single covering plane (or voltage beyond the plane range): nearest
        # plane by voltage + fitted slope correction. For single-plane
        # datasets the power-based estimate carries the extrapolation
        # (flagged) instead of refusing: the ±15 % excursion limit still
        # bounds how far this may go.
        plane = min(covering, key=lambda p: abs(p.voltage_v - voltage))
        value = float(plane.current_interp(rpm))
        dv = voltage - plane.voltage_v
        corrected = abs(dv) > V_TOLERANCE_V
        notes = []
        if corrected:
            value += self._current_voltage_slope * dv
            notes.append(
                f"linear voltage-slope correction {self._current_voltage_slope:+.4f} A/V "
                "fitted from measured planes' overlap"
            )
        if corrected and (abs(dv) > FAR_FROM_PLANE_V or len(self.planes) < 2):
            # A linear slope correction over a large excursion is unreliable
            # (it can go negative). Apply a physical floor: the shaft power at
            # this rpm demands at least P_mech / V of current.
            i_plane = max(float(plane.current_interp(rpm)), 0.0)
            p_mech = MOTOR_EFFICIENCY_ASSUMED * plane.voltage_v * i_plane
            i_power = p_mech / max(voltage, 5.0)
            if i_power > value:
                value = i_power
            notes.append(
                f"power-based current estimate applied (V excursion {dv:+.1f} V, "
                f"eta={MOTOR_EFFICIENCY_ASSUMED:.2f} assumed, flagged estimate)"
            )
        value = max(value, 0.0)
        return QueryResult(
            value=max(value, 0.0),
            plane_voltage_v=plane.voltage_v,
            voltage_corrected=corrected,
            voltage_extrapolated=self._voltage_extrapolated(voltage),
            note="; ".join(notes),
        )

    def power_w(self, rpm: float, voltage: float) -> QueryResult:
        """Electrical power = v_bus x current (exact DC identity; reproduces the
        datasheet power column at the measured plane voltages)."""
        res = self.current_a(rpm, voltage)
        res.value *= voltage
        return res

    def rpm_at_throttle(self, throttle: float, voltage: float) -> QueryResult:
        throttle_pct = throttle * 100.0
        if not (THROTTLE_EXTRAP_MIN_PCT <= throttle_pct <= 100.0 + 1e-9):
            raise OutOfEnvelopeError(
                f"throttle {throttle_pct:.1f}% outside usable range "
                f"[{THROTTLE_EXTRAP_MIN_PCT:.0f}, 100]% for {self.prop_key!r}"
            )
        if not self._voltage_allowed(voltage):
            raise OutOfEnvelopeError(
                f"voltage {voltage:.2f} V outside allowed excursion for throttle mapping"
            )
        covering = [
            p
            for p in self.planes
            if p.throttle_range[0] <= throttle_pct <= p.throttle_range[1]
        ]
        if not covering:
            # Below the lowest measured knot (50 %): PCHIP extrapolation per
            # plane, then the same linear-in-voltage combination as above the
            # knot (keeps the throttle<->rpm composite consistent).
            vals = [float(p.rpm_from_throttle(throttle_pct)) for p in self.planes]
            if len(vals) >= 2:
                v1, v2 = self.planes[0].voltage_v, self.planes[-1].voltage_v
                rpm = vals[0] + (vals[-1] - vals[0]) * (voltage - v1) / (v2 - v1)
            else:
                rpm = vals[0] * (voltage / self.planes[0].voltage_v)
            return QueryResult(
                value=rpm,
                plane_voltage_v=self.planes[-1].voltage_v,
                throttle_extrapolated=True,
                note="rpm extrapolated below the lowest measured throttle knot (50 %)",
            )
        if len(covering) >= 2:
            p1, p2 = covering[0], covering[-1]
            r1 = float(p1.rpm_from_throttle(throttle_pct))
            r2 = float(p2.rpm_from_throttle(throttle_pct))
            rpm = r1 + (r2 - r1) * (voltage - p1.voltage_v) / (p2.voltage_v - p1.voltage_v)
            return QueryResult(
                value=rpm,
                plane_voltage_v=p1.voltage_v,
                voltage_corrected=abs(voltage - p1.voltage_v) > 1e-9,
                voltage_extrapolated=self._voltage_extrapolated(voltage),
                note="rpm linearly interpolated in voltage between measured planes",
            )
        plane = covering[0]
        rpm_at_plane = float(plane.rpm_from_throttle(throttle_pct))
        if abs(voltage - plane.voltage_v) <= V_TOLERANCE_V:
            return QueryResult(
                value=rpm_at_plane,
                plane_voltage_v=plane.voltage_v,
            )
        # Far from the plane voltage: rpm scales proportionally with voltage
        # at fixed throttle — empirically supported by the two-plane MN3508
        # data (2600/3900 rpm over 14.8/22.2 V = exactly the voltage ratio).
        rpm = rpm_at_plane * (voltage / plane.voltage_v)
        return QueryResult(
            value=rpm,
            plane_voltage_v=plane.voltage_v,
            voltage_corrected=True,
            voltage_extrapolated=self._voltage_extrapolated(voltage),
            note="rpm scaled proportionally with voltage (empirically supported "
            "by two-plane data; flagged extrapolation)",
        )

    def attainable_static_thrust_n(self, voltage: float) -> float:
        """Full-throttle thrust ceiling at branch voltage, capped to measured RPM."""
        rpm = self.rpm_at_throttle(1.0, voltage).value
        rpm_min, rpm_max = float(self._merged_rpm[0]), float(self._merged_rpm[-1])
        if rpm < rpm_min:
            return self.thrust_n(rpm_min).value * (max(rpm, 0.0) / rpm_min) ** 2
        return self.thrust_n(min(rpm, rpm_max)).value

    def thrust_at_throttle(self, throttle: float, voltage: float) -> QueryResult:
        rpm_res = self.rpm_at_throttle(throttle, voltage)
        thr_res = self.thrust_n(rpm_res.value)
        thr_res.throttle_extrapolated = rpm_res.throttle_extrapolated
        thr_res.voltage_corrected = rpm_res.voltage_corrected
        thr_res.voltage_extrapolated = rpm_res.voltage_extrapolated
        thr_res.note = rpm_res.note
        return thr_res

    def inverse_throttle_for_unit_thrust(
        self, target_thrust_n: float, voltage: float
    ) -> QueryResult:
        """Solve the throttle at which one unit produces ``target_thrust_n``.

        Inversion runs in *rpm space* against the merged measured thrust table
        (the measured data is the envelope — thrust is never extrapolated, even
        at bus voltages above the measured planes). The rpm -> throttle step
        then interpolates in voltage like ``rpm_at_throttle``; its envelope
        flags are propagated.
        """
        target_gf = target_thrust_n / GF_TO_N
        gf_lo = float(self._merged_thrust_gf.min())
        gf_hi = float(self._merged_thrust_gf.max())
        if not gf_lo <= target_gf <= gf_hi:
            raise OutOfEnvelopeError(
                f"required per-unit thrust {target_thrust_n:.2f} N "
                f"({target_gf:.0f} gf) is outside the measured static table "
                f"[{gf_lo:.0f}, {gf_hi:.0f}] gf "
                "— thrust is not extrapolated beyond measured data"
            )
        rpm_lo, rpm_hi = float(self._merged_rpm[0]), float(self._merged_rpm[-1])
        f = lambda r: float(self._thrust_interp(r)) - target_gf  # noqa: E731
        rpm_target = brentq(f, rpm_lo, rpm_hi, xtol=1e-4)
        return self.throttle_at_rpm(rpm_target, voltage)

    def throttle_at_rpm(self, rpm: float, voltage: float) -> QueryResult:
        """Inverse of ``rpm_at_throttle``: the throttle producing the given rpm
        at the given bus voltage.

        Implemented as a numerical inversion of the *composite* mapping
        (``rpm_at_throttle``), which guarantees the throttle->rpm->throttle
        chain is self-consistent by construction. Envelope flags are taken
        from the composite evaluation at the solution.
        """
        if not self._voltage_allowed(voltage):
            raise OutOfEnvelopeError(
                f"voltage {voltage:.2f} V outside allowed excursion for throttle mapping"
            )
        lo_t = THROTTLE_EXTRAP_MIN_PCT / 100.0
        hi_t = 1.0
        rpm_lo = self.rpm_at_throttle(lo_t, voltage).value
        rpm_hi = self.rpm_at_throttle(hi_t, voltage).value
        if not rpm_lo <= rpm <= rpm_hi:
            raise OutOfEnvelopeError(
                f"rpm {rpm:.0f} is outside the throttle-mapping coverage "
                f"[{rpm_lo:.0f}, {rpm_hi:.0f}] rpm at {voltage:.1f} V "
                f"({THROTTLE_EXTRAP_MIN_PCT:.0f}%-100% throttle)"
            )
        f = lambda t: self.rpm_at_throttle(t, voltage).value - rpm  # noqa: E731
        t = brentq(f, lo_t, hi_t, xtol=1e-7)
        res = self.rpm_at_throttle(t, voltage)
        return QueryResult(
            value=t,
            plane_voltage_v=res.plane_voltage_v,
            voltage_corrected=res.voltage_corrected,
            voltage_extrapolated=res.voltage_extrapolated,
            throttle_extrapolated=res.throttle_extrapolated,
            note=res.note,
        )

    # ------------------------------------------ declared-extrapolation path

    def thrust_rpm_extrapolated(self, thrust_gf: float) -> QueryResult:
        """rpm estimate for thrust BELOW the measured static table minimum
        (descent regime), via the static scaling the table itself follows
        (T ∝ rpm² at fixed density): rpm = rpm_min · sqrt(T/T_min).

        DECLARED extrapolation — callers must surface the flag; the strict
        ``thrust_gf``/inverse APIs remain envelope-guarded.
        """
        gf_min = float(self._merged_thrust_gf.min())
        rpm_min = float(self._merged_rpm[0])
        if thrust_gf <= 0.0:
            return QueryResult(value=0.0, plane_voltage_v=self._v_min)
        if thrust_gf >= gf_min:
            raise OutOfEnvelopeError("use the strict inverse APIs for in-envelope thrust")
        rpm = rpm_min * math.sqrt(thrust_gf / gf_min)
        return QueryResult(
            value=rpm,
            plane_voltage_v=self._v_min,
            note="rpm below measured range: static-scaling extrapolation (T ∝ rpm²)",
        )

    def current_a_extrapolated(self, rpm: float, voltage: float) -> QueryResult:
        """Current estimate outside the measured rpm ranges (nearest plane
        PCHIP + fitted voltage slope, floored by the power-based estimate and
        ceilinged at 1.5x the plane's max measured current — PCHIP
        extrapolation far outside the table is not trusted beyond that).
        DECLARED extrapolation — callers must surface the flag."""
        plane = min(self.planes, key=lambda p: abs(p.voltage_v - voltage))
        i_plane = max(float(plane.current_interp(rpm)), 0.0)
        value = i_plane + self._current_voltage_slope * (voltage - plane.voltage_v)
        p_mech = MOTOR_EFFICIENCY_ASSUMED * plane.voltage_v * i_plane
        i_power = p_mech / max(voltage, 5.0)
        value = max(value, i_power, 0.05)
        ceiling = 1.5 * float(plane.current_a.max())
        value = min(value, ceiling)
        return QueryResult(
            value=value,
            plane_voltage_v=plane.voltage_v,
            voltage_corrected=True,
            voltage_extrapolated=self._voltage_extrapolated(voltage),
            note=(
                "current extrapolated outside measured rpm range "
                f"(nearest plane + slope, power-based floor, ceiling {ceiling:.1f} A)"
            ),
        )

    # ------------------------------------------------------------- metadata

    @property
    def voltage_range(self) -> tuple[float, float]:
        return self._v_min, self._v_max

    def envelope(self) -> dict:
        return {
            "prop_key": self.prop_key,
            "motor_id": self.motor.id,
            "rpm_range_merged": [float(self._merged_rpm[0]), float(self._merged_rpm[-1])],
            "plane_rpm_ranges": {str(p.voltage_v): list(p.rpm_range) for p in self.planes},
            "voltage_planes_v": [p.voltage_v for p in self.planes],
            "voltage_slope_a_per_v": self._current_voltage_slope,
            "cross_voltage_thrust_scatter_pct": self.scatter_pct,
            "dataset_uncertainty_pct": self.motor.source.uncertainty_pct,
        }

    @property
    def provenance(self) -> str:
        s = self.motor.source
        return f"{s.source} ({s.url}); uncertainty ±{s.uncertainty_pct}%"
