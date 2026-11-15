"""Uncertainty quantification (M7): Monte Carlo over declared parameter
uncertainties for the static-hover endurance and hover point.

Sampled parameters (each with its provenance-backed range):
  - battery capacity ±10 % (pack clones; mass scales with capacity —
    estimated relations, flagged),
  - battery internal resistance ±50 % (flagged estimate),
  - thrust table ±3 % (dataset uncertainty from manufacturer report MN.00011).
    EXACT equivalence used: uncertain delivered thrust at fixed required lift
    is identical to holding mass/thrust_factor with the nominal table — so
    the sampler evaluates the nominal dataset at the equivalent mass,
  - motor mass ±2 % (sourced; shifts total carried mass).

Deterministic seeding (traceable). The report carries best estimate, std,
5/95 percentiles, and a one-at-a-time sensitivity ranking so the user knows
WHICH measurement would most reduce uncertainty.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from aeroforge_schemas.design import DroneDesign
from physics.constants import STANDARD_GRAVITY
from physics.propulsion.battery import BatteryPack
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.loader import ComponentLibrary
from physics.propulsion.powertrain import StaticPowertrain
from physics.propulsion.esc import Esc

THRUST_UNCERTAINTY = 0.03    # dataset source uncertainty (MN.00011)
CAPACITY_UNCERTAINTY = 0.10
RESISTANCE_UNCERTAINTY = 0.50  # flagged estimate
MOTOR_MASS_UNCERTAINTY = 0.02

# (name, sample-key) pairs for the Monte Carlo and the sensitivity edges.
PARAMETERS = [
    ("battery_capacity", "capacity_factor", CAPACITY_UNCERTAINTY),
    ("battery_resistance", "resistance_factor", RESISTANCE_UNCERTAINTY),
    ("thrust", "thrust_factor", THRUST_UNCERTAINTY),
    ("motor_mass", "motor_mass_factor", MOTOR_MASS_UNCERTAINTY),
]


@dataclass
class UQResult:
    quantity: str
    unit: str
    n_samples: int
    best_estimate: float
    mean: float
    std: float
    p05: float
    p95: float
    sensitivities: dict[str, dict] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "quantity": self.quantity,
            "unit": self.unit,
            "n_samples": self.n_samples,
            "best_estimate": round(self.best_estimate, 3),
            "mean": round(self.mean, 3),
            "std": round(self.std, 3),
            "p05": round(self.p05, 3),
            "p95": round(self.p95, 3),
            "sensitivities": self.sensitivities,
            "notes": self.notes,
        }


class EnduranceSampler:
    """Static-hover endurance as a function of the uncertain parameters."""

    def __init__(self, design: DroneDesign, library: ComponentLibrary,
                 max_duration_s: float = 24 * 3600.0) -> None:
        if design.powertrain is None:
            raise ValueError("UQ needs a design with a powertrain block")
        motor = library.motor(design.powertrain.motor_id)
        prop = library.propeller(design.powertrain.propeller_id)
        self.battery_spec = library.battery(design.powertrain.battery_id)
        esc_spec = library.esc(design.powertrain.esc_id)
        dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
        self.powertrain = StaticPowertrain(dataset, Esc(esc_spec),
                                           BatteryPack(self.battery_spec),
                                           units=len(design.rotors))
        self.units = len(design.rotors)
        self.max_duration_s = max_duration_s

        self.mass_non_motor = float(
            sum(p.mass_kg for p in design.parts if not p.name.startswith("motor_"))
        )
        self.motor_mass = motor.mass_kg if motor.mass_kg is not None else 0.0
        self.n_motors = max(
            sum(1 for p in design.parts if p.name.startswith("motor_")), self.units
        )

    def evaluate(
        self,
        capacity_factor: float = 1.0,
        resistance_factor: float = 1.0,
        thrust_factor: float = 1.0,
        motor_mass_factor: float = 1.0,
    ) -> dict:
        spec = self.battery_spec.model_copy(update={
            "capacity_ah": self.battery_spec.capacity_ah * capacity_factor,
            "mass_kg": (self.battery_spec.mass_kg * capacity_factor
                        if self.battery_spec.mass_kg is not None else None),
            "internal_resistance_ohm": (
                self.battery_spec.internal_resistance_ohm * resistance_factor
                if self.battery_spec.internal_resistance_ohm is not None else None
            ),
        })
        # Swap the pack clone into the powertrain for this sample.
        from physics.propulsion.dataset import PowertrainDataset as _PD

        dataset = self.powertrain.dataset
        assert isinstance(dataset, _PD)
        powertrain = StaticPowertrain(dataset, self.powertrain.esc,
                                      BatteryPack(spec), units=self.units)
        mass = self.mass_non_motor + self.motor_mass * motor_mass_factor * self.n_motors
        # Thrust uncertainty: identical to hovering mass/thrust_factor with the
        # nominal table (exact equivalence for the static case).
        mass_eff = mass / thrust_factor
        try:
            res = powertrain.static_hover(mass_eff, max_duration_s=self.max_duration_s,
                                          dt_s=30.0)
        except Exception:  # noqa: BLE001 — a sampled point can be infeasible
            return {"feasible": False, "endurance_s": None, "power_w": None}
        return {
            "feasible": True,
            "endurance_s": res.endurance_to_warning_s,
            "power_w": res.hover_point.total_power_w,
        }


def monte_carlo_endurance(
    design: DroneDesign,
    library: ComponentLibrary,
    n_samples: int = 200,
    seed: int = 42,
) -> UQResult:
    sampler = EnduranceSampler(design, library)
    rng = np.random.default_rng(seed)

    base = sampler.evaluate()
    samples: list[float] = []
    for _ in range(n_samples):
        kwargs = {
            key: float(1.0 + rng.uniform(-unc, unc))
            for _name, key, unc in PARAMETERS
        }
        r = sampler.evaluate(**kwargs)
        if r["feasible"] and r["endurance_s"] is not None:
            samples.append(float(r["endurance_s"]))
    arr = np.array(samples)

    # One-at-a-time sensitivities at the parameter edges.
    sens: dict[str, dict] = {}
    for name, key, unc in PARAMETERS:
        lo = sampler.evaluate(**{key: 1.0 - unc})
        hi = sampler.evaluate(**{key: 1.0 + unc})
        e_lo = lo.get("endurance_s") or 0.0
        e_hi = hi.get("endurance_s") or 0.0
        sens[name] = {
            "endurance_low_s": round(e_lo, 0),
            "endurance_high_s": round(e_hi, 0),
            "delta_s": round(abs(e_hi - e_lo), 0),
        }

    notes = [
        f"thrust table ±{THRUST_UNCERTAINTY:.0%} (dataset uncertainty, MN.00011)",
        f"battery capacity ±{CAPACITY_UNCERTAINTY:.0%}; resistance "
        f"±{RESISTANCE_UNCERTAINTY:.0%} (capacity/R flagged estimated — "
        "expected dominant uncertainty source)",
        f"motor mass ±{MOTOR_MASS_UNCERTAINTY:.0%} (sourced)",
        "deterministic seeding; static-hover endurance to the 3.5 V/cell warning",
        "required hover thrust uses STANDARD_GRAVITY = "
        f"{STANDARD_GRAVITY} m/s² (site-specific g differs negligibly)",
    ]
    return UQResult(
        quantity="hover endurance (to 3.5 V/cell warning)",
        unit="s",
        n_samples=len(arr),
        best_estimate=float(base.get("endurance_s") or 0.0),
        mean=float(arr.mean()) if len(arr) else 0.0,
        std=float(arr.std()) if len(arr) else 0.0,
        p05=float(np.percentile(arr, 5)) if len(arr) else 0.0,
        p95=float(np.percentile(arr, 95)) if len(arr) else 0.0,
        sensitivities=sens,
        notes=notes,
    )
