"""Battery pack model: OCV(SOC) + internal-resistance sag + coulomb counting.

MODEL STATUS: first-order equivalent circuit (OCV curve + single pack R).
- OCV-vs-SOC curve is per cell, sourced from community-measured LiPo charts
  (see the component JSON); pack OCV = cells x cell OCV.
- Sag: V_terminal = V_ocv - I * R_pack (R_pack must be known — fail closed
  otherwise; the placeholder pack flags its R as estimated).
- NOT modeled: rate-dependent capacity derating (C-rating effects), temperature
  dependence, cell imbalance, cycle aging. Endurance numbers carry the
  battery source's uncertainty until a pack-specific discharge test is added.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import PchipInterpolator

from aeroforge_schemas.component import BatterySpec


class PowertrainError(RuntimeError):
    """Powertrain cannot satisfy the requested operation — fail closed."""


@dataclass
class BatteryStatus:
    soc_pct: float
    ocv_pack_v: float
    cell_voltage_loaded_v: float
    warning: bool
    cutoff: bool


class BatteryPack:
    def __init__(self, spec: BatterySpec) -> None:
        self.spec = spec
        socs = [p.soc_pct for p in spec.ocv_curve]
        volts = [p.cell_voltage_v for p in spec.ocv_curve]
        if len(socs) < 2 or any(b <= a for a, b in zip(socs, socs[1:])):
            raise ValueError("ocv_curve must have >= 2 points, ascending in SOC")
        self._ocv_cell = PchipInterpolator(np.array(socs), np.array(volts))
        if spec.internal_resistance_ohm is None:
            # Allowed to construct, but any loaded query fails closed.
            self._r_pack: float | None = None
        else:
            self._r_pack = spec.internal_resistance_ohm

    def ocv_cell(self, soc_pct: float) -> float:
        if not 0.0 <= soc_pct <= 100.0:
            raise ValueError(f"SOC {soc_pct:.1f}% outside [0, 100]")
        return float(self._ocv_cell(soc_pct))

    def ocv_pack(self, soc_pct: float) -> float:
        return self.ocv_cell(soc_pct) * self.spec.cells_series

    def voltage_under_load(self, soc_pct: float, current_a: float) -> float:
        if self._r_pack is None:
            raise PowertrainError(
                f"battery {self.spec.id!r} has unknown internal resistance — "
                "cannot compute voltage sag; supply a measured value"
            )
        ocv = self.ocv_pack(soc_pct)
        sag = current_a * self._r_pack
        if sag > 0.9 * ocv:
            raise PowertrainError(
                f"requested current {current_a:.1f} A exceeds what the pack can "
                f"supply (sag {sag:.2f} V vs OCV {ocv:.2f} V)"
            )
        return ocv - sag

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
