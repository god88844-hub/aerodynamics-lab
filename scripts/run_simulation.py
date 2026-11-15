"""Run an AeroForge simulation scenario from a design snapshot.

Milestone 1 scope — dynamics verification:
  * validates the snapshot against the shared schema,
  * assembles mass / CoG / inertia from parts (parallel axis theorem),
  * computes the analytic hover trim (per-rotor thrusts, ΣF=0 Στ=0),
  * integrates the 6-DOF equations for a stationary-hover scenario,
  * prints an engineering report: Design / Trim / Scenario / Results /
    Trustworthiness (model status, assumptions, caveats).

The actuator model is IDEAL in M1 (commanded thrust == delivered thrust).
Sourced motor/propeller/battery models replace it in M2. Until then, outputs
of this script are dynamics-verification results, NOT flight-worthiness
claims — the Trustworthiness section says so explicitly.

Usage:
    python scripts/run_simulation.py data/designs/quad_example_2kg.json
    python scripts/run_simulation.py design.json --duration 5 --solver ivp
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


def run_hover(design: DroneDesign, duration_s: float, dt_s: float, solver: str) -> dict:
    """Run the M1 stationary-hover scenario and return a result dict."""
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
        times, states = integrate_fixed(
            f, x0, 0.0, duration_s, dt_s, post_step=normalize_state
        )
    elif solver == "ivp":
        times, states = integrate_ivp(
            f, x0, 0.0, duration_s, post_step=normalize_state, max_step=0.05
        )
    else:  # pragma: no cover - argparse restricts choices
        raise ValueError(f"unknown solver {solver!r}")

    # Max |net acceleration| along the trajectory (world frame, includes gravity).
    max_net_accel = 0.0
    for t, x in zip(times, states):
        a = f(t, x)[3:6]
        max_net_accel = max(max_net_accel, float(np.linalg.norm(a)))

    r_final, v_final, _, _ = unpack_state(states[-1])
    return {
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
        "scenario": {
            "type": "hover (stationary)",
            "duration_s": duration_s,
            "dt_s": dt_s,
            "solver": solver,
            "gravity_m_s2": STANDARD_GRAVITY,
        },
        "results": {
            "final_altitude_m": float(r_final[2]),
            "horizontal_drift_m": float(np.hypot(r_final[0], r_final[1])),
            "final_speed_m_s": float(np.linalg.norm(v_final)),
            "max_net_acceleration_m_s2": max_net_accel,
        },
        "trustworthiness": {
            "dynamics_core": {
                "status": "verified",
                "evidence": "unit tests vs analytical solutions (free fall, "
                "spin-up, conservation laws, convergence order) — tests/physics/",
            },
            "mass_properties": {
                "status": "verified",
                "evidence": "parallel-axis assembly tests vs known cases",
            },
            "actuator_model": {
                "status": "idealized placeholder",
                "caveat": "commanded thrust == delivered thrust; no motor/prop/ESC/"
                "battery dynamics. Replaced by sourced propulsion models in M2. "
                "Thrust values are NOT hardware-feasibility claims.",
            },
            "drag_model": {
                "status": "approximation"
                if design.drag_cd_a_m2 is not None
                else "not used",
                "caveat": "first-order CdA model; no wind, no AOA dependence; "
                "CdA value has no experimental source in M1",
            },
            "verdict": "M1 dynamics verification only — not a flight-worthiness claim",
        },
    }


def print_report(result: dict) -> None:
    d = result["design"]
    tr = result["trim"]
    sc = result["scenario"]
    rs = result["results"]
    tw = result["trustworthiness"]

    print("=" * 62)
    print(f"AeroForge simulation report — physics {physics_version}")
    print("=" * 62)
    print(f"\n[DESIGN] {d['name']}  ({d['n_rotors']} rotors)")
    print(f"  mass                 : {d['mass_kg']:.4f} kg")
    print(f"  CoG                  : {np.array2string(np.array(d['cog_m']), precision=4)} m")
    print(
        "  principal moments    : "
        f"{np.array2string(np.array(d['principal_moments_kg_m2']), precision=5)} kg·m²"
    )
    print("\n[TRIM] hover thrusts (ΣF=0, Στ=0)")
    for i, t in enumerate(tr["per_rotor_thrust_n"]):
        print(f"  rotor {i + 1}: {t:.4f} N")
    print(f"  total: {tr['total_thrust_n']:.4f} N  (weight: {tr['weight_n']:.4f} N)")
    print(
        f"\n[SCENARIO] {sc['type']} | duration {sc['duration_s']} s | "
        f"dt {sc['dt_s']} s | solver {sc['solver']} | g = {sc['gravity_m_s2']} m/s²"
    )
    print("\n[RESULTS]")
    print(f"  final altitude       : {rs['final_altitude_m']:+.6e} m")
    print(f"  horizontal drift     : {rs['horizontal_drift_m']:.3e} m")
    print(f"  final speed          : {rs['final_speed_m_s']:.3e} m/s")
    print(f"  max |net accel|      : {rs['max_net_acceleration_m_s2']:.3e} m/s²")
    print("\n[TRUSTWORTHINESS]")
    for key, entry in tw.items():
        if isinstance(entry, dict):
            status = entry.get("status", "")
            caveat = entry.get("caveat", "")
            print(f"  {key:22s}: {status}")
            if caveat:
                print(f"    - {caveat}")
        else:
            print(f"  {key}: {entry}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an AeroForge simulation scenario.")
    parser.add_argument("config", help="Path to a design snapshot JSON.")
    parser.add_argument("--duration", type=float, default=2.0, help="Scenario duration [s].")
    parser.add_argument("--dt", type=float, default=0.002, help="Fixed-step RK4 step [s].")
    parser.add_argument(
        "--solver", choices=["rk4", "ivp"], default="rk4", help="Integrator (default rk4)."
    )
    parser.add_argument("--json", action="store_true", help="Print the raw result JSON.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"error: design snapshot not found: {config_path}", file=sys.stderr)
        return 2

    design = DroneDesign.model_validate_json(config_path.read_text(encoding="utf-8"))
    result = run_hover(design, args.duration, args.dt, args.solver)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
