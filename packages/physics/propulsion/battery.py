"""Battery pack model: OCV(SOC) + internal-resistance sag + coulomb counting.

MODEL STATUS: first-order equivalent circuit (OCV curve + single pack R).
- OCV-vs-SOC curve is per cell, sourced from community-measured LiPo charts
  (see the component JSON); pack OCV = cells x cell OCV.
- Sag: V_terminal = V_ocv - I * R_pack (R_pack must be known — fail closed
  otherwise; the placeholder pack flags its R as estimated).
- Causal bus equation (P0A-006): V_bus = V_oc(SOC) - V_rc - I * R_int, with
  V_rc an optional caller-owned polarization state (0 by default; no sourced
  RC parameters exist yet, and temperature dependence is NOT modeled — V_oc
  is the declared table at its declared measurement conditions).
- Constant-power demand is solved EXACTLY (quadratic), not iterated: the
  stable upper root is returned and a demand above the pack's maximum
  deliverable power V_oc^2 / (4 R) is reported as voltage collapse instead of
  an invented operating point.
- The OCV curve is honored ONLY inside its declared SOC support: below the
  lowest declared point (the uncalibrated discharge knee) queries fail
  closed rather than extrapolating an optimistic tail.
- NOT modeled: rate-dependent capacity derating (C-rating effects), temperature
  dependence, cell imbalance, cycle aging. Endurance numbers carry the
  battery source's uncertainty until a pack-specific discharge test is added.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator

from aeroforge_schemas.component import BatterySpec

# Deterministic bisection depth for in-tick threshold-crossing brackets:
# 60 halvings of any finite dt resolve to float precision.
_CROSSING_BISECTION_STEPS = 60


class PowertrainError(RuntimeError):
    """Powertrain cannot satisfy the requested operation — fail closed."""


class VoltageCollapseError(PowertrainError):
    """No feasible operating point exists at the demanded load: the demand
    exceeds the pack's deliverable power at this SOC (P0A-006)."""


class OutOfSupportError(PowertrainError):
    """The requested state lies outside the declared model support (e.g. a
    SOC below the calibrated OCV knee region) — refused, not extrapolated."""


@dataclass
class BatteryStatus:
    soc_pct: float
    ocv_pack_v: float
    cell_voltage_loaded_v: float
    warning: bool
    cutoff: bool


@dataclass(frozen=True)
class PowerSolution:
    """Exact constant-power bus solution (P0A-006).

    ``feasible`` is False when no real operating point exists (voltage
    collapse): the demanded power exceeds the pack's maximum deliverable
    power at this SOC. ``v_bus_v``/``current_a`` are None in that case.
    """

    feasible: bool
    v_bus_v: float | None
    current_a: float | None
    reason: str | None = None


class BatteryPack:
    def __init__(self, spec: BatterySpec) -> None:
        self.spec = spec
        socs = [p.soc_pct for p in spec.ocv_curve]
        volts = [p.cell_voltage_v for p in spec.ocv_curve]
        if len(socs) < 2 or any(b <= a for a, b in zip(socs, socs[1:])):
            raise ValueError("ocv_curve must have >= 2 points, ascending in SOC")
        # No extrapolation: outside the declared support the model must fail
        # closed, never invent an optimistic low-SOC tail (P0A-006).
        self._ocv_cell = PchipInterpolator(np.array(socs), np.array(volts), extrapolate=False)
        self._soc_support = (float(min(socs)), float(max(socs)))
        if spec.internal_resistance_ohm is None:
            # Allowed to construct, but any loaded query fails closed.
            self._r_pack: float | None = None
        else:
            self._r_pack = spec.internal_resistance_ohm

    def _require_r(self) -> float:
        if self._r_pack is None:
            raise PowertrainError(
                f"battery {self.spec.id!r} has unknown internal resistance — "
                "cannot compute voltage sag; supply a measured value"
            )
        return self._r_pack

    def _ocv_cell_in_support(self, soc_pct: float) -> float:
        """OCV with strict declared-support enforcement (fail closed below
        the calibrated knee region instead of extrapolating)."""
        lo, hi = self._soc_support
        if not lo <= soc_pct <= hi:
            raise OutOfSupportError(
                f"SOC {soc_pct:.2f}% outside the declared OCV support "
                f"[{lo:.2f}, {hi:.2f}]% of battery {self.spec.id!r} — the "
                "low-SOC discharge knee is not calibrated; refusing to "
                "extrapolate (fail closed)"
            )
        return float(self._ocv_cell(soc_pct))

    @property
    def declared_soc_support_pct(self) -> tuple[float, float]:
        """The SOC range over which the declared OCV table is calibrated."""
        return self._soc_support

    def ocv_cell(self, soc_pct: float) -> float:
        if not 0.0 <= soc_pct <= 100.0:
            raise ValueError(f"SOC {soc_pct:.1f}% outside [0, 100]")
        return self._ocv_cell_in_support(soc_pct)

    def ocv_pack(self, soc_pct: float) -> float:
        return self.ocv_cell(soc_pct) * self.spec.cells_series

    def voltage_under_load(self, soc_pct: float, current_a: float) -> float:
        r = self._require_r()
        ocv = self.ocv_pack(soc_pct)
        sag = current_a * r
        if sag > 0.9 * ocv:
            raise VoltageCollapseError(
                f"requested current {current_a:.1f} A exceeds what the pack can "
                f"supply (sag {sag:.2f} V vs OCV {ocv:.2f} V)"
            )
        return ocv - sag

    # ------------------------------------------------------------- P0A-006
    # Causal load-voltage coupling: exact constant-power solve, collapse
    # boundary, and deterministic in-tick threshold-crossing brackets.

    def max_deliverable_power_w(self, soc_pct: float, v_rc_v: float = 0.0) -> float:
        """The constant-power collapse boundary V_th^2 / (4 R) with
        V_th = V_oc(SOC) - V_rc: above it the quadratic V_bus^2 - V_th*V_bus
        + P*R = 0 has no real root (no feasible operating point)."""
        r = self._require_r()
        v_th = self.ocv_pack(soc_pct) - v_rc_v
        return v_th * v_th / (4.0 * r)

    def solve_constant_power(
        self, soc_pct: float, power_w: float, v_rc_v: float = 0.0
    ) -> PowerSolution:
        """Causal solve of V_bus = V_oc(SOC) - V_rc - I * R_int under a
        constant-power demand (I = P / V_bus).

        Substituting gives V_bus^2 - V_th*V_bus + P*R = 0 with
        V_th = V_oc(SOC) - V_rc; the STABLE upper root
        V_bus = (V_th + sqrt(V_th^2 - 4 P R)) / 2 is returned (the lower root
        is the unstable constant-power equilibrium). A demand above the
        maximum deliverable power V_th^2 / (4 R) — negative discriminant — is
        reported as voltage collapse (feasible=False), never as an invented
        operating point. Deterministic: exact algebra, no iteration.

        ``v_rc_v`` is a caller-owned polarization state advanced causally by
        the caller (0 by default — no sourced RC parameters exist yet).
        Charging (power_w < 0) is not modeled and raises ValueError.
        """
        if power_w < 0.0:
            raise ValueError("constant-power solve covers discharge only (power_w >= 0)")
        r = self._require_r()
        v_th = self.ocv_pack(soc_pct) - v_rc_v
        if power_w == 0.0:
            if v_th <= 0.0:
                return PowerSolution(False, None, None, "no source voltage at this SOC")
            return PowerSolution(True, v_th, 0.0, None)
        discriminant = v_th * v_th - 4.0 * power_w * r
        if v_th <= 0.0 or discriminant < 0.0:
            p_max = max(v_th, 0.0) ** 2 / (4.0 * r)
            return PowerSolution(
                False, None, None,
                f"demanded power {power_w:.1f} W exceeds the maximum deliverable "
                f"power {p_max:.1f} W at {soc_pct:.1f}% SOC "
                f"(V_oc {v_th + v_rc_v:.2f} V, V_rc {v_rc_v:.2f} V, R {r:.4f} ohm) "
                "— voltage collapse",
            )
        v_bus = 0.5 * (v_th + np.sqrt(discriminant))
        return PowerSolution(True, float(v_bus), float(power_w / v_bus), None)

    def crossing_time_below_cell_v(
        self,
        soc_start_pct: float,
        soc_end_pct: float,
        current_a: float,
        dt_s: float,
        threshold_cell_v: float,
    ) -> float | None:
        """First time in [0, dt_s] at which the loaded cell voltage falls to
        or below ``threshold_cell_v`` while the pack drains linearly from
        ``soc_start_pct`` to ``soc_end_pct`` at constant ``current_a``.

        Exact equality fires deterministically: a threshold crossing at the
        tick's start returns 0.0 (``<=``), one exactly at the tick's end
        returns dt_s, and an interior crossing is bracketed by bisection on
        the model's own OCV interpolation (60 halvings — float precision,
        bit-for-bit reproducible). Returns None when the threshold is not
        reached inside the tick. Requires the declared OCV curve to be
        monotone in SOC (all sourced and fitted tables are); raises
        PowertrainError if the drain leaves the declared OCV support before
        the threshold is reached (fail closed — no invented tail).
        """
        if dt_s <= 0.0:
            raise ValueError("dt_s must be positive")
        if current_a < 0.0:
            raise ValueError("discharge current must be >= 0")
        if soc_end_pct > soc_start_pct:
            raise ValueError("crossing bracketing covers discharge only (soc must not rise)")
        r = self._require_r()
        sag_cell = current_a * r / self.spec.cells_series

        def loaded_cell_v(soc: float) -> float:
            return self._ocv_cell_in_support(soc) - sag_cell

        def f(tau: float) -> float:
            soc = soc_start_pct + (soc_end_pct - soc_start_pct) * tau / dt_s
            return loaded_cell_v(soc) - threshold_cell_v

        # If the drain leaves the declared support before dt_s, bracket only
        # up to that instant and refuse an unsupported extrapolation.
        hi = dt_s
        support_lo, _ = self._soc_support
        if soc_end_pct < support_lo:
            if soc_start_pct < support_lo:
                raise OutOfSupportError(
                    f"SOC {soc_start_pct:.2f}% already outside the declared OCV "
                    f"support (below {support_lo:.2f}%) of battery {self.spec.id!r}"
                )
            tau_support = dt_s * (soc_start_pct - support_lo) / (soc_start_pct - soc_end_pct)
            if f(tau_support) > 0.0:
                raise OutOfSupportError(
                    f"battery {self.spec.id!r} leaves its declared OCV support "
                    f"at t+{tau_support:.6g} s before reaching the "
                    f"{threshold_cell_v:.2f} V/cell threshold — the low-SOC knee "
                    "is not calibrated; refusing to extrapolate (fail closed)"
                )
            hi = tau_support

        if f(0.0) <= 0.0:
            return 0.0
        if f(hi) == 0.0:
            # Crossing exactly at the bracket edge: deterministic exact
            # return (equality is inclusive via ``<=``).
            return hi
        if f(hi) > 0.0:
            return None
        lo = 0.0
        for _ in range(_CROSSING_BISECTION_STEPS):
            mid = 0.5 * (lo + hi)
            if f(mid) > 0.0:
                lo = mid
            else:
                hi = mid
        return hi

    def soc_after(self, soc_pct: float, current_a: float, dt_s: float) -> float:
        """Coulomb counting: dSOC = -100 * I * dt / (3600 * capacity)."""
        if current_a < 0.0:
            raise ValueError("discharge current must be >= 0")
        drained = 100.0 * current_a * dt_s / (3600.0 * self.spec.capacity_ah)
        return max(0.0, soc_pct - drained)

    def status(self, soc_pct: float, current_a: float) -> BatteryStatus:
        v_cell = self.voltage_under_load(soc_pct, current_a) / self.spec.cells_series
        return BatteryStatus(
            soc_pct=soc_pct,
            ocv_pack_v=self.ocv_pack(soc_pct),
            cell_voltage_loaded_v=v_cell,
            warning=v_cell <= self.spec.warning_cell_voltage_v,
            cutoff=v_cell <= self.spec.cutoff_cell_voltage_v,
        )

    def remaining_energy_wh(self, soc_pct: float) -> float:
        """Coarse stored-energy estimate (OCV based; under-load terminal voltage
        is lower — endurance results carry the battery uncertainty)."""
        return self.ocv_pack(soc_pct) * self.spec.capacity_ah * soc_pct / 100.0
