"""Run an AeroForge simulation scenario from a design snapshot.

Scenarios
---------
hover-ideal (M1):  6-DOF dynamics verification — mass/CoG/inertia assembly,
                   analytic hover trim, RK4/scipy integration. Actuators are
                   IDEAL (commanded thrust == delivered thrust).
hover-static (M2): sourced-powertrain static analysis — throttle/current/rpm
                   from measured manufacturer bench data (model of record),
                   battery sag + endurance, component limit checks, pre-
                   registered propulsion benchmarks, envelope flags.

Both scenarios print an engineering report with Design / Scenario / Results /
Trustworthiness sections. Every caveat is explicit; neither scenario is a
flight-worthiness claim (dynamics + controller validation arrive in M3/M4).

Usage:
    python scripts/run_simulation.py data/designs/quad_mn3508_6s.json
    python scripts/run_simulation.py data/designs/quad_example_2kg.json --scenario hover-ideal
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

import numpy as np  # noqa: E402

from aeroforge_schemas.design import DroneDesign  # noqa: E402
from physics import __version__ as physics_version  # noqa: E402
from physics.constants import STANDARD_GRAVITY  # noqa: E402
from physics.dynamics.design_adapter import build_multirotor  # noqa: E402
from physics.dynamics.rigid_body import make_state, normalize_state, unpack_state  # noqa: E402
from physics.integration.rk4 import integrate_fixed  # noqa: E402
from physics.integration.scipy_solver import integrate_ivp  # noqa: E402
from physics.propulsion.battery import BatteryPack  # noqa: E402
from physics.propulsion.dataset import PowertrainDataset  # noqa: E402
from physics.propulsion.esc import Esc  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.propulsion.powertrain import StaticPowertrain  # noqa: E402
from physics.validation.benchmarks import run_propulsion_benchmarks  # noqa: E402


# --------------------------------------------------------------- M1: ideal


def run_hover_ideal(design: DroneDesign, duration_s: float, dt_s: float, solver: str) -> dict:
    """M1 stationary-hover verification with ideal actuators."""
    plant, mass = build_multirotor(design)
    trim = plant.hover_trim()

    x0 = make_state(
        r_world=np.zeros(3),
        v_world=np.zeros(3),
        q_bw=np.array([1.0, 0.0, 0.0, 0.0]),
        omega_body=np.zeros(3),
    )
    f = lambda t, x: plant.derivs(x, trim)  # noqa: E731

    if solver == "rk4":
        times, states = integrate_fixed(f, x0, 0.0, duration_s, dt_s, post_step=normalize_state)
    elif solver == "ivp":
        times, states = integrate_ivp(f, x0, 0.0, duration_s, post_step=normalize_state, max_step=0.05)
    else:  # pragma: no cover
        raise ValueError(f"unknown solver {solver!r}")

    max_net_accel = max(
        float(np.linalg.norm(f(t, x)[3:6])) for t, x in zip(times, states)
    )
    r_final, v_final, _, _ = unpack_state(states[-1])
    return {
        "scenario": "hover-ideal (M1 dynamics verification)",
        "design": {
            "name": design.name,
            "mass_kg": mass.mass_kg,
            "cog_m": mass.cog_m.tolist(),
            "principal_moments_kg_m2": mass.principal_moments.tolist(),
            "n_rotors": len(design.rotors),
        },
        "trim": {
            "per_rotor_thrust_n": trim.tolist(),
            "total_thrust_n": float(np.sum(trim)),
            "weight_n": mass.mass_kg * STANDARD_GRAVITY,
        },
        "integration": {"duration_s": duration_s, "dt_s": dt_s, "solver": solver,
                        "gravity_m_s2": STANDARD_GRAVITY},
        "results": {
            "final_altitude_m": float(r_final[2]),
            "horizontal_drift_m": float(np.hypot(r_final[0], r_final[1])),
            "final_speed_m_s": float(np.linalg.norm(v_final)),
            "max_net_acceleration_m_s2": max_net_accel,
        },
        "trustworthiness": {
            "dynamics_core": {"status": "verified",
                              "evidence": "unit tests vs analytical solutions — tests/physics/"},
            "mass_properties": {"status": "verified",
                                "evidence": "parallel-axis assembly tests vs known cases"},
            "actuator_model": {"status": "idealized placeholder",
                               "caveat": "commanded thrust == delivered thrust; no motor/prop/"
                               "ESC/battery dynamics. Run --scenario hover-static for the "
                               "sourced powertrain analysis."},
            "verdict": "M1 dynamics verification only — not a flight-worthiness claim",
        },
    }


# ------------------------------------------------------------ M2: static


def run_hover_static(design: DroneDesign, max_duration_s: float, dt_s: float) -> dict:
    """M2 static hover on the sourced powertrain: throttle/current/endurance."""
    if design.powertrain is None:
        raise ValueError(
            "design has no powertrain block — add one or use --scenario hover-ideal"
        )
    lib = ComponentLibrary(REPO_ROOT / "data" / "components")
    motor = lib.motor(design.powertrain.motor_id)
    prop = lib.propeller(design.powertrain.propeller_id)
    battery_spec = lib.battery(design.powertrain.battery_id)
    esc_spec = lib.esc(design.powertrain.esc_id)

    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    battery = BatteryPack(battery_spec)
    powertrain = StaticPowertrain(dataset, Esc(esc_spec), battery, units=len(design.rotors))

    _, mass_props = build_multirotor(design)
    total_mass = mass_props.mass_kg

    # Traceability cross-check: the battery Part in the design must match the
    # battery component's spec mass within the estimate's uncertainty.
    battery_part = next((p for p in design.parts if "battery" in p.name.lower()), None)
    consistency = "ok"
    if battery_part is not None and battery_spec.mass_kg is not None:
        rel = abs(battery_part.mass_kg - battery_spec.mass_kg) / battery_spec.mass_kg
        if rel > 0.25:
            raise ValueError(
                f"design battery part mass {battery_part.mass_kg} kg differs from "
                f"component spec {battery_spec.mass_kg} kg by {rel * 100:.0f}% — "
                "fix the design or the component entry"
            )
        elif rel > 1e-9:
            consistency = f"within {rel * 100:.1f}% of component spec"

    hover = powertrain.static_hover(
        total_mass, max_duration_s=max_duration_s, dt_s=dt_s
    )
    benchmarks = run_propulsion_benchmarks(dataset)

    estimated_components = []
    for label, spec in (("motor", motor), ("propeller", prop),
                        ("battery", battery_spec), ("esc", esc_spec)):
        if spec.source.estimated:
            estimated_components.append(label)
    if prop.mass_kg is None:
        estimated_components.append("propeller mass (unknown — user must supply)")

    return {
        "scenario": "hover-static (M2 sourced powertrain)",
        "design": {
            "name": design.name,
            "mass_kg": total_mass,
            "cog_m": mass_props.cog_m.tolist(),
            "n_rotors": len(design.rotors),
            "powertrain": design.powertrain.model_dump(),
            "battery_mass_consistency": consistency,
        },
        "benchmarks": [
            {"name": b.name, "status": b.status, "metrics": b.metrics,
             "tolerances": b.tolerances, "notes": b.notes}
            for b in benchmarks
        ],
        "hover_point": {
            "throttle": hover.hover_point.throttle,
            "v_bus_v": hover.hover_point.v_bus,
            "per_rotor": {
                "thrust_n": hover.hover_point.per_unit.thrust_n,
                "rpm": hover.hover_point.per_unit.rpm,
                "current_a": hover.hover_point.per_unit.current_a,
                "power_w": hover.hover_point.per_unit.power_w,
                "envelope_flags": hover.hover_point.per_unit.flags,
            },
            "total_current_a": hover.hover_point.total_current_a,
            "total_power_w": hover.hover_point.total_power_w,
            "hover_power_w_per_kg": hover.hover_point.total_power_w / total_mass,
        },
        "endurance": {
            "to_warning_s": hover.endurance_to_warning_s,
            "to_cutoff_s": hover.endurance_to_cutoff_s,
            "energy_used_wh_at_warning": hover.energy_used_wh,
            "min_cell_voltage_v": hover.min_cell_voltage_v,
        },
        "limits": {"issues": hover.limit_issues},
        "trustworthiness": {
            "propulsion_data": {
                "status": "measured bench data (model of record)",
                "source": dataset.provenance,
                "envelope": dataset.envelope(),
            },
            "hover_envelope_flags": hover.envelope_flags,
            "estimated_components": estimated_components,
            "battery_model": {
                "status": "first-order OCV + R model",
                "caveat": battery_spec.source.notes or "",
            },
            "static_only": {
                "caveat": "no forward-flight advance ratio, no wind, no controller "
                "dynamics (M3/M4), no thermal integration; endurance carries the "
                "battery estimates' uncertainty"
            },
            "verdict": "M2 static analysis on sourced bench data — NOT a "
            "flight-worthiness claim",
        },
    }


# ---------------------------------------------------------------- report


def print_report(result: dict) -> None:
    print("=" * 66)
    print(f"AeroForge simulation report — physics {physics_version}")
    print(f"scenario: {result['scenario']}")
    print("=" * 66)

    d = result["design"]
    print(f"\n[DESIGN] {d['name']}  ({d['n_rotors']} rotors)")
    print(f"  mass                 : {d['mass_kg']:.4f} kg")
    print(f"  CoG                  : {np.array2string(np.array(d['cog_m']), precision=4)} m")

    if result["scenario"].startswith("hover-ideal"):
        tr = result["trim"]
        integ = result["integration"]
        rs = result["results"]
        print("\n[TRIM] hover thrusts (ΣF=0, Στ=0)")
        for i, t in enumerate(tr["per_rotor_thrust_n"]):
            print(f"  rotor {i + 1}: {t:.4f} N")
        print(f"  total: {tr['total_thrust_n']:.4f} N  (weight: {tr['weight_n']:.4f} N)")
        print(
            f"\n[SCENARIO] duration {integ['duration_s']} s | dt {integ['dt_s']} s | "
            f"solver {integ['solver']} | g = {integ['gravity_m_s2']} m/s²"
        )
        print("\n[RESULTS]")
        print(f"  final altitude       : {rs['final_altitude_m']:+.6e} m")
        print(f"  horizontal drift     : {rs['horizontal_drift_m']:.3e} m")
        print(f"  final speed          : {rs['final_speed_m_s']:.3e} m/s")
        print(f"  max |net accel|      : {rs['max_net_acceleration_m_s2']:.3e} m/s²")
    else:
        hp = result["hover_point"]
        pr = hp["per_rotor"]
        en = result["endurance"]
        print(f"  powertrain           : {d['powertrain']['motor_id']} + "
              f"{d['powertrain']['propeller_id']}")
        print(f"  battery              : {d['powertrain']['battery_id']} "
              f"(mass consistency: {d['battery_mass_consistency']})")

        print("\n[BENCHMARKS] pre-registered tolerances")
        for b in result["benchmarks"]:
            metrics = ", ".join(f"{k}={v:.3g}" for k, v in b["metrics"].items())
            print(f"  [{b['status'].upper():8s}] {b['name']}: {metrics}")

        print("\n[HOVER POINT] (full charge)")
        print(f"  throttle             : {hp['throttle'] * 100:.1f} %")
        print(f"  bus voltage          : {hp['v_bus_v']:.2f} V")
        print(f"  per rotor            : {pr['thrust_n']:.2f} N @ {pr['rpm']:.0f} rpm, "
              f"{pr['current_a']:.2f} A, {pr['power_w']:.1f} W")
        print(f"  totals               : {hp['total_current_a']:.2f} A, "
              f"{hp['total_power_w']:.1f} W  ({hp['hover_power_w_per_kg']:.0f} W/kg)")
        flags = {k: v for k, v in pr["envelope_flags"].items() if v and k != "note"}
        if flags:
            print(f"  envelope flags       : {flags}")
            if pr["envelope_flags"].get("note"):
                print(f"    note: {pr['envelope_flags']['note']}")

        warn_s = en["to_warning_s"]
        print("\n[ENDURANCE] (stationary hover, perfect altitude hold)")
        if warn_s is not None:
            print(f"  to warning (3.5 V/cell): {warn_s:.0f} s "
                  f"({warn_s / 60.0:.1f} min)")
        print(f"  energy to warning    : {en['energy_used_wh_at_warning']:.1f} Wh")
        print(f"  min cell voltage     : {en['min_cell_voltage_v']:.2f} V")
        if result["limits"]["issues"]:
            print("  LIMIT ISSUES:")
            for issue in result["limits"]["issues"]:
                print(f"    - {issue}")

    print("\n[TRUSTWORTHINESS]")
    for key, entry in result["trustworthiness"].items():
        if isinstance(entry, dict):
            status = entry.get("status", "")
            print(f"  {key:22s}: {status}")
            if entry.get("caveat"):
                print(f"    - {entry['caveat']}")
            if entry.get("evidence"):
                print(f"    - {entry['evidence']}")
        else:
            print(f"  {key}: {entry}")
    if result["scenario"].startswith("hover-static"):
        tw = result["trustworthiness"]
        if tw.get("hover_envelope_flags"):
            print(f"    - hover envelope flags: {tw['hover_envelope_flags']}")
        if tw.get("estimated_components"):
            print(f"    - ESTIMATED (unsourced) components: {tw['estimated_components']}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an AeroForge simulation scenario.")
    parser.add_argument("config", help="Path to a design snapshot JSON.")
    parser.add_argument(
        "--scenario",
        choices=["auto", "hover-ideal", "hover-static"],
        default="auto",
        help="hover-static needs a powertrain block (default: auto-select)",
    )
    parser.add_argument("--duration", type=float, default=2.0,
                        help="hover-ideal duration [s] / hover-static max duration [s]")
    parser.add_argument("--dt", type=float, default=0.002,
                        help="hover-ideal fixed step [s] / hover-static step [s]")
    parser.add_argument("--solver", choices=["rk4", "ivp"], default="rk4",
                        help="hover-ideal integrator")
    parser.add_argument("--json", action="store_true", help="Print the raw result JSON.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"error: design snapshot not found: {config_path}", file=sys.stderr)
        return 2

    design = DroneDesign.model_validate_json(config_path.read_text(encoding="utf-8"))

    scenario = args.scenario
    if scenario == "auto":
        scenario = "hover-static" if design.powertrain is not None else "hover-ideal"

    if scenario == "hover-static":
        result = run_hover_static(design, args.duration, args.dt)
    else:
        result = run_hover_ideal(design, args.duration, args.dt, args.solver)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
