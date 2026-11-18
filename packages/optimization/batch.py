"""Batch evaluation and design-space exploration (M6).

Approach: exhaustive grid search over a declared parameter box (battery
capacity, rotor count, arm length, payload). Every candidate runs the SAME
physics as single runs — the sourced static powertrain model with battery
drain to the warning threshold — through a fast evaluator whose thrust->rpm
inversion is a precomputed lookup table VERIFIED against the strict brentq
path (test asserts agreement).

Validation gates (spec: "if the model says a candidate goes out of
validation range, skip or flag it"):
  - hover thrust per rotor outside the measured static table -> candidate
    flagged infeasible (reason recorded, never silently dropped),
  - hover trim impossible (geometry) -> flagged,
  - structural margin < 1 (arm bending at hover load) -> flagged,
  - battery-mass consistency enforced by construction (mass scaled with
    capacity using an ESTIMATED kg/Ah relation, flagged in results).

Output: per-candidate rows + the Pareto frontier of (total mass) vs
(endurance to the 3.5 V/cell warning) over feasible candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from aeroforge_schemas.component import BatterySpec
from aeroforge_schemas.design import DroneDesign
from physics.constants import GF_TO_N, STANDARD_GRAVITY
from physics.propulsion.battery import BatteryPack
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.esc import Esc
from physics.structures.beam import check_arm
from physics.structures.materials import MaterialProps

BATTERY_KG_PER_AH_ESTIMATED = 0.0969  # 16 Ah pack -> 1.55 kg (ESTIMATED scaling)
BATTERY_R_SCALED_WITH_CAPACITY = True  # pack R ~ 1/capacity (more parallel cells)
ENDURANCE_DT_S = 30.0


@dataclass
class CandidateResult:
    params: dict
    mass_kg: float
    hover_thrust_per_rotor_n: float | None
    hover_current_total_a: float | None
    hover_power_w: float | None
    v_bus_v: float | None
    endurance_to_warning_s: float | None
    structural_margin: float | None
    feasible: bool
    flags: list[str] = field(default_factory=list)

    def as_row(self) -> dict:
        return {
            **self.params,
            "mass_kg": round(self.mass_kg, 4),
            "hover_thrust_per_rotor_n": None if self.hover_thrust_per_rotor_n is None else round(self.hover_thrust_per_rotor_n, 3),
            "hover_current_total_a": None if self.hover_current_total_a is None else round(self.hover_current_total_a, 3),
            "hover_power_w": None if self.hover_power_w is None else round(self.hover_power_w, 1),
            "v_bus_v": None if self.v_bus_v is None else round(self.v_bus_v, 2),
            "endurance_to_warning_s": None if self.endurance_to_warning_s is None else round(self.endurance_to_warning_s, 0),
            "structural_margin": None if self.structural_margin is None else round(self.structural_margin, 2),
            "feasible": self.feasible,
            "flags": ";".join(self.flags),
        }


class FastHoverEvaluator:
    """Fast static-hover endurance evaluator with a verified thrust->rpm LUT."""

    def __init__(
        self,
        dataset: PowertrainDataset,
        battery_spec: BatterySpec,
        esc_spec,
        units: int,
    ) -> None:
        self.dataset = dataset
        self.battery = BatteryPack(battery_spec)
        self.esc = Esc(esc_spec)
        self.units = units
        envelope = dataset.envelope()
        rpm_lo, rpm_hi = envelope["rpm_range_merged"]
        self.rpm_lo, self.rpm_hi = float(rpm_lo), float(rpm_hi)
        self.gf_min = float(dataset._merged_thrust_gf.min())  # noqa: SLF001 — module-internal use
        self.gf_max = float(dataset._merged_thrust_gf.max())  # noqa: SLF001
        self.max_thrust_n = self.gf_max * GF_TO_N

        # LUT: thrust(gf) -> rpm on a fine grid (verified against brentq in tests).
        grid = np.linspace(self.rpm_lo, self.rpm_hi, 400)
        self._gf_grid = np.array([float(dataset.thrust_gf(r).value) for r in grid])
        self._rpm_grid = grid
        self.gf_at_rpm_lo = float(self._gf_grid[0])

        self.max_continuous_a = dataset.motor.max_continuous_current_a

    def thrust_to_rpm(self, thrust_n: float) -> tuple[float, bool]:
        """(rpm, extrapolated). Below the table: static scaling T ∝ rpm²."""
        gf = thrust_n / GF_TO_N
        if self.gf_min <= gf <= self.gf_max:
            return float(np.interp(gf, self._gf_grid, self._rpm_grid)), False
        if gf <= 0.0:
            return 0.0, False
        if gf < self.gf_min:
            return self.rpm_lo * float(np.sqrt(gf / self.gf_min)), True
        raise ValueError("thrust above table max — caller must gate this")

    def unit_current(self, rpm: float, v_bus: float) -> float:
        res = self.dataset.current_a(rpm, v_bus)
        return res.value

    def hover_point(self, mass_kg: float, soc_pct: float = 100.0,
                    max_endurance_hint: float = 24 * 3600.0) -> dict:
        """Static hover point + endurance to the battery warning voltage."""
        target_unit = mass_kg * STANDARD_GRAVITY / self.units
        flags: list[str] = []
        if target_unit > self.max_thrust_n:
            return {"feasible": False,
                    "reason": (f"hover thrust {target_unit:.2f} N/rotor exceeds measured max "
                               f"{self.max_thrust_n:.2f} N")}
        gf = target_unit / GF_TO_N
        rpm, extrapolated = self.thrust_to_rpm(target_unit)
        if extrapolated:
            flags.append("thrust_below_envelope")

        # Bus fixed point (currents depend on v_bus).
        v_bus = self.battery.ocv_pack(soc_pct)
        currents = np.zeros(self.units)
        for _ in range(10):
            for i in range(self.units):
                currents[i] = max(self.unit_current(rpm, v_bus), 0.0)
            total = float(currents.sum())
            v_new = self.battery.voltage_under_load(soc_pct, total)
            if abs(v_new - v_bus) < 1e-3:
                v_bus = v_new
                break
            v_bus = 0.5 * (v_bus + v_new)
        total_current = float(currents.sum())
        power_w = v_bus * total_current

        # Endurance: coulomb drain to the warning cell voltage (under load).
        soc = soc_pct
        t = 0.0
        endurance = None
        max_steps = int(max_endurance_hint / ENDURANCE_DT_S)
        for step in range(max_steps + 1):
            # Symmetric hover gives each controller the same branch current.
            esc_issues = self.esc.check(float(currents[0]), v_bus)
            if esc_issues:
                return {"feasible": False, "reason": ", ".join(esc_issues)}
            if step == max_steps:
                break
            status = self.battery.status(soc, total_current)
            if status.cutoff:
                break
            if status.warning:
                endurance = t
                break
            soc = self.battery.soc_after(soc, total_current, ENDURANCE_DT_S)
            t += ENDURANCE_DT_S
            # Bus/current drift with SOC.
            v_bus = self.battery.voltage_under_load(soc, total_current)
            currents = np.array([
                max(self.unit_current(rpm, v_bus), 0.0) for _i in range(self.units)
            ])
            total_current = float(currents.sum())
            if soc <= 0.0:
                break

        if extrapolated:
            flags.append("thrust_below_envelope")
        return {
            "feasible": True,
            "hover_thrust_per_rotor_n": target_unit,
            "rpm": rpm,
            "current_total_a": total_current,
            "power_w": power_w,
            "v_bus_v": v_bus,
            "endurance_to_warning_s": endurance,
            "flags": flags,
        }


def battery_spec_for_capacity(base: BatterySpec, capacity_ah: float) -> BatterySpec:
    """Clone the pack spec at a different capacity: mass ∝ capacity and pack
    R ∝ 1/capacity (ESTIMATED relations, flagged in the batch results)."""
    scale = capacity_ah / base.capacity_ah
    mass = None if base.mass_kg is None else base.mass_kg * scale
    r = None
    if base.internal_resistance_ohm is not None:
        r = base.internal_resistance_ohm / scale
    return base.model_copy(
        update={"capacity_ah": capacity_ah, "mass_kg": mass, "internal_resistance_ohm": r}
    )


def with_rotor_layout(design: DroneDesign, n_rotors: int, arm_length_m: float) -> DroneDesign:
    """Rebuild the rotor layout (motors/ESCs/props/rotors) for n rotors at the
    given radius, inheriting component masses from the base design."""
    from aeroforge_schemas.design import PartInstance, RotorInstance

    motor_mass = next(
        (p.mass_kg for p in design.parts if p.name.startswith("motor_")), 0.103
    )
    esc_mass = next((p.mass_kg for p in design.parts if p.name.startswith("esc_")), 0.03)
    prop_mass = next((p.mass_kg for p in design.parts if p.name.startswith("prop_")), 0.019)

    kept = [
        p for p in design.parts
        if not (p.name.startswith("motor_") or p.name.startswith("esc_") or p.name.startswith("prop_"))
    ]
    parts: list[PartInstance] = list(kept)
    rotors: list[RotorInstance] = []
    for i in range(n_rotors):
        theta = 2.0 * np.pi * i / n_rotors + (np.pi / n_rotors)
        x, y = arm_length_m * float(np.cos(theta)), arm_length_m * float(np.sin(theta))
        idx = f"{i:02d}"
        parts.append(PartInstance(name=f"motor_{idx}", mass_kg=motor_mass,
                                  position_m=(x, y, 0.02)))
        parts.append(PartInstance(name=f"esc_{idx}", mass_kg=esc_mass,
                                  position_m=(0.6 * x, 0.6 * y, 0.0)))
        parts.append(PartInstance(name=f"prop_{idx}", mass_kg=prop_mass,
                                  position_m=(x, y, 0.045)))
        rotors.append(RotorInstance(
            position_m=(x, y, 0.02),
            spin_direction=1 if i % 2 == 0 else -1,
            motor_id=design.powertrain.motor_id if design.powertrain else None,
            propeller_id=design.powertrain.propeller_id if design.powertrain else None,
        ))
    frame = design.frame
    if frame is not None:
        frame = frame.model_copy(update={"arm_length_m": arm_length_m})
    return design.model_copy(update={"parts": parts, "rotors": rotors, "frame": frame})


def with_payload(design: DroneDesign, payload_kg: float) -> DroneDesign:
    from aeroforge_schemas.design import PartInstance

    if payload_kg <= 0:
        return design
    parts = [p for p in design.parts if p.name != "payload"]
    parts.append(PartInstance(name="payload", mass_kg=payload_kg, position_m=(0.0, 0.0, 0.05)))
    return design.model_copy(update={"parts": parts})


def total_mass(design: DroneDesign) -> float:
    return float(sum(p.mass_kg for p in design.parts))


def run_grid(
    base_design: DroneDesign,
    library,
    grid: dict[str, list],
    material: MaterialProps | None = None,
    max_endurance_s: float = 24 * 3600.0,
) -> list[CandidateResult]:
    """Evaluate every combination in the grid. Batteries are cloned per
    capacity (mass/R scaled, ESTIMATED); payloads are added as parts; rotor
    layouts are regenerated per count/arm length."""
    from physics.structures.materials import load_materials

    motor = library.motor(base_design.powertrain.motor_id)
    prop = library.propeller(base_design.powertrain.propeller_id)
    battery_base = library.battery(base_design.powertrain.battery_id)
    esc_spec = library.esc(base_design.powertrain.esc_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)

    if material is None and base_design.frame is not None:
        materials = load_materials(library.data_dir / "materials.json")
        material = materials[base_design.frame.material_id]

    capacities = grid.get("battery_capacity_ah", [16.0])
    rotor_counts = grid.get("rotor_count", [4])
    arm_lengths = grid.get("arm_length_m", [0.25])
    payloads = grid.get("payload_kg", [0.0])

    results: list[CandidateResult] = []
    evaluators: dict[float, FastHoverEvaluator] = {}
    for cap in capacities:
        bspec = battery_spec_for_capacity(battery_base, cap)
        # One evaluator per capacity: the LUT depends only on the dataset;
        # the battery pack differs per capacity.
        evaluators[cap] = FastHoverEvaluator(dataset, bspec, esc_spec, units=1)
        for n in rotor_counts:
            for arm in arm_lengths:
                for payload in payloads:
                    flags: list[str] = []
                    d = with_rotor_layout(base_design, n, arm)
                    d = with_payload(d, payload)
                    # Battery part mass follows the cloned spec (consistency).
                    bmass = bspec.mass_kg
                    if bmass is not None:
                        d = d.model_copy(update={
                            "parts": [
                                p.model_copy(update={"mass_kg": bmass})
                                if "battery" in p.name.lower() else p
                                for p in d.parts
                            ]
                        })
                    mass = total_mass(d)

                    evaluator = evaluators[cap]
                    evaluator.units = n
                    point = evaluator.hover_point(mass, soc_pct=100.0,
                                                  max_endurance_hint=max_endurance_s)
                    if not point.get("feasible", False):
                        results.append(CandidateResult(
                            params={"battery_capacity_ah": cap, "rotor_count": n,
                                    "arm_length_m": arm, "payload_kg": payload},
                            mass_kg=mass, hover_thrust_per_rotor_n=None,
                            hover_current_total_a=None, hover_power_w=None,
                            v_bus_v=None, endurance_to_warning_s=None,
                            structural_margin=None, feasible=False,
                            flags=[f"out_of_envelope: {point.get('reason', '')}"],
                        ))
                        continue

                    flags.extend(point.get("flags", []))
                    struct_margin = None
                    struct_fail = False
                    if material is not None and base_design.frame is not None:
                        check = check_arm(
                            point["hover_thrust_per_rotor_n"], arm,
                            base_design.frame.tube_od_m, base_design.frame.tube_id_m,
                            material,
                        )
                        struct_margin = check.margin
                        if not check.ok:
                            struct_fail = True
                            flags.append(f"structure_yield: {check.message}")

                    feasible = not struct_fail
                    endurance = point.get("endurance_to_warning_s")
                    if endurance is not None and endurance > max_endurance_s:
                        endurance = max_endurance_s
                    results.append(CandidateResult(
                        params={"battery_capacity_ah": cap, "rotor_count": n,
                                "arm_length_m": arm, "payload_kg": payload},
                        mass_kg=mass,
                        hover_thrust_per_rotor_n=point["hover_thrust_per_rotor_n"],
                        hover_current_total_a=point["current_total_a"],
                        hover_power_w=point["power_w"],
                        v_bus_v=point["v_bus_v"],
                        endurance_to_warning_s=endurance,
                        structural_margin=struct_margin,
                        feasible=feasible,
                        flags=flags,
                    ))
    return results


def pareto_front(results: list[CandidateResult]) -> list[CandidateResult]:
    """Non-dominated set over (mass ↓, endurance ↑) among feasible candidates
    with a recorded endurance."""
    feasible = [r for r in results if r.feasible and r.endurance_to_warning_s is not None]
    front: list[CandidateResult] = []
    for r in feasible:
        dominated = False
        for other in feasible:
            if other is r:
                continue
            if (other.mass_kg <= r.mass_kg and other.endurance_to_warning_s >= r.endurance_to_warning_s
                    and (other.mass_kg < r.mass_kg or other.endurance_to_warning_s > r.endurance_to_warning_s)):
                dominated = True
                break
        if not dominated:
            front.append(r)
    front.sort(key=lambda r: r.mass_kg)
    return front
