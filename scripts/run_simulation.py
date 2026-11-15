"""CLI entry point for running AeroForge simulation scenarios.

Thin wrapper over packages/physics/scenarios/service.py (the canonical
runners shared with the API). Usage mirrors the service scenarios:

    python scripts/run_simulation.py data/designs/quad_mn3508_6s.json            # auto
    python scripts/run_simulation.py data/designs/quad_mn3508_6s.json --scenario flight
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
from physics.scenarios import service  # noqa: E402


def print_report(result: dict) -> None:
    print("=" * 66)
    print(f"AeroForge simulation report — physics {result.get('physics_version')}")
    print(f"scenario: {result['scenario']}")
    print("=" * 66)

    d = result["design"]
    print(f"\n[DESIGN] {d['name']}  ({d.get('n_rotors')} rotors)")
    print(f"  mass                 : {d['mass_kg']:.4f} kg")
    print(f"  CoG                  : {np.array2string(np.array(d['cog_m']), precision=4)} m")

    scenario = result["scenario"]
    if scenario.startswith("hover-ideal"):
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
    elif scenario.startswith("hover-static"):
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
            print(f"  envelope flags       : {list(flags)}")
        warn_s = en["to_warning_s"]
        print("\n[ENDURANCE] (stationary hover, perfect altitude hold)")
        if warn_s is not None:
            print(f"  to warning (3.5 V/cell): {warn_s:.0f} s ({warn_s / 60.0:.1f} min)")
        print(f"  energy to warning    : {en['energy_used_wh_at_warning']:.1f} Wh")
        print(f"  min cell voltage     : {en['min_cell_voltage_v']:.2f} V")
        if result["limits"]["issues"]:
            print("  LIMIT ISSUES:")
            for issue in result["limits"]["issues"]:
                print(f"    - {issue}")
    elif scenario.startswith("hover-hold"):
        rs = result["results"]
        print("\n[DISTURBANCES]")
        for d in result["disturbances"]:
            print(f"  t={d['t_s']} force={d['force_world_n']} torque={d['torque_body_nm']}")
        print("\n[RESULTS] (closed-loop hover with disturbances)")
        print(f"  peak |roll|          : {rs['peak_abs_roll_deg']:.2f} deg")
        print(f"  peak |pitch|         : {rs['peak_abs_pitch_deg']:.2f} deg")
        print(f"  tail altitude error  : {rs['tail_altitude_error_m']:.4f} m "
              f"(std {rs['tail_altitude_std_m']:.4f})")
        print(f"  tail position error  : {rs['tail_position_error_m']:.4f} m")
        print(f"  max motor thrust     : {rs['max_motor_thrust_n']:.2f} N")
        print(f"  oscillation          : {rs['oscillation']}")
    elif scenario.startswith("flight"):
        m = result["mission"]
        rs = result["results"]
        print(f"\n[MISSION] {m['profile']} | duration {m['duration_s']:.1f} s | "
              f"aborted={m['aborted']}")
        if m["abort_event"]:
            print(f"  ABORT CAUSE: {m['abort_event']}")
        print("\n[RESULTS]")
        print(f"  time to 5 m          : {rs['time_to_5m_s']} s")
        print(f"  max altitude         : {rs['max_altitude_m']:.2f} m")
        print(f"  energy used          : {rs['energy_used_wh']:.1f} Wh")
        print(f"  max motor current    : {rs['max_motor_current_a']} A")
        print(f"  final SOC            : {rs['final_soc_pct']} %")
        print(f"  final state          : z={rs['final_altitude_m']:.3f} m, "
              f"vz={rs['final_vertical_speed_m_s']:.2f} m/s")
        if rs["structural_margin_min"] is not None:
            print(f"  min structural margin: {rs['structural_margin_min']:.2f}")
        print("\n[EVENTS]")
        for e in result["events"]:
            tag = "CRITICAL" if e["critical"] else "warn"
            print(f"  [{tag}] t={e['t_s']} {e['kind']}: {e['message'][:90]}")
        print("\n[SUCCESS]")
        for name, ok in result["success"].items():
            print(f"  {name:24s}: {'PASS' if ok else 'FAIL'}")

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
    if scenario.startswith("hover-static"):
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
        choices=["auto", "hover-ideal", "hover-static", "hover-hold", "flight"],
        default="auto",
        help="hover-static/flight need a powertrain block (default: auto-select)",
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

    try:
        if scenario == "hover-static":
            result = service.run_hover_static(design, max_duration_s=max(args.duration, 7200.0),
                                              dt_s=args.dt)
        elif scenario == "hover-hold":
            result = service.run_hover_hold(design, max(args.duration, 10.0), 0.004)
        elif scenario == "flight":
            result = service.run_flight(design)
        else:
            result = service.run_hover_ideal(design, args.duration, args.dt, args.solver)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
