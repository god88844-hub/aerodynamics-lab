"""Milestone 8 capstone: the 60 kg hexacopter mission suite + credibility
report.

Runs the full spec'd suite — hover, climb (takeoff), descent (landing),
maneuver (forward flight), wind gust, motor failure — plus the static
powertrain analysis, the Monte Carlo uncertainty pass, and the V&V
benchmark/convergence report. Everything is combined into a credibility
report with per-submodel validation status and a final verdict against the
design goals:

  G1  hover hold stable under disturbances
  G2  climb to 5 m within tolerance
  G3  gentle controlled landing
  G4  forward maneuver arrives and holds station
  G5  gust rejected within bounds
  G6  motor-failure outcome recorded (survive or named abort)
  G7  hover point inside the measured static envelope
  G8  structural margin >= 1
  G9  endurance reported with uncertainty

Usage:
    python scripts/run_capstone.py --out outputs/capstone_report
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

import numpy as np  # noqa: E402

from aeroforge_schemas.design import DroneDesign  # noqa: E402
from physics.propulsion.dataset import PowertrainDataset  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.scenarios import service  # noqa: E402
from physics.controller.simulation import Disturbance  # noqa: E402
from physics.scenarios.runner import Scenario, run_scenario  # noqa: E402
from physics.validation.report import generate_vv_report, render_markdown  # noqa: E402
from physics.validation.uq import monte_carlo_endurance  # noqa: E402


def _mission_summary(res) -> dict:
    return {
        "aborted": res.aborted,
        "abort_event": res.abort_event.message if res.abort_event else None,
        "events": [
            {"t_s": e.t_s, "kind": e.kind, "critical": e.critical, "message": e.message}
            for e in res.events
        ],
        "success": res.success,
        "final_state": {
            "z_m": float(res.states[-1, 2]),
            "vz_m_s": float(res.states[-1, 5]),
            "x_m": float(res.states[-1, 0]),
            "y_m": float(res.states[-1, 1]),
        },
        "max_altitude_m": res.max_altitude_m,
        "peak_tilt_deg": _peak_tilt(res),
        "energy_wh": res.energy_wh,
    }


def _peak_tilt(res) -> float:
    from physics.dynamics.quaternion import rotation_matrix

    tilts = []
    for s in res.states:
        R = rotation_matrix(s[6:10])
        cos_tilt = max(-1.0, min(1.0, float(R[2, 2])))
        tilts.append(np.degrees(np.arccos(cos_tilt)))
    return float(np.max(tilts)) if tilts else 0.0


def run_capstone(design: DroneDesign, library: ComponentLibrary, uq_samples: int = 150) -> dict:
    t0 = time.perf_counter()
    goals: dict[str, dict] = {}

    # --- static powertrain analysis (hover point + endurance) --------------
    static = service.run_hover_static(design, max_duration_s=3600.0, dt_s=30.0)
    hover_point = static["hover_point"]
    envelope_flags = static["trustworthiness"].get("hover_envelope_flags", [])
    critical_flags = [f for f in envelope_flags if "out_of_envelope" in str(f)]
    goals["G7_hover_in_measured_envelope"] = {
        "passed": len(critical_flags) == 0,
        "detail": {
            "hover_flags": envelope_flags,
            "hover_point": hover_point,
        },
    }

    # --- hover hold with disturbances (G1) ---------------------------------
    hold = service.run_hover_hold(design, duration_s=12.0, control_dt_s=0.004,
                                  data_dir=library.data_dir.parent)
    g1 = (hold["results"]["tail_altitude_error_m"] < 0.10
          and hold["results"]["tail_position_error_m"] < 0.30
          and hold["results"]["oscillation"] == "none detected")
    goals["G1_hover_hold_stable"] = {
        "passed": bool(g1),
        "detail": hold["results"],
    }

    # --- flight: climb to 5 m, hold, land (G2, G3) -------------------------
    flight = service.run_flight(design)
    g2 = flight["results"]["time_to_5m_s"] is not None
    g3 = (abs(flight["results"]["final_altitude_m"]) < 0.10
          and abs(flight["results"]["final_vertical_speed_m_s"]) < 1.0)
    goals["G2_climb_to_5m"] = {"passed": bool(g2),
                               "detail": {k: flight["results"][k]
                                          for k in ("time_to_5m_s", "max_altitude_m",
                                                    "energy_used_wh")}}
    goals["G3_gentle_landing"] = {"passed": bool(g3),
                                  "detail": flight["results"]}

    # --- forward maneuver (G4) ---------------------------------------------
    maneuver = Scenario(
        name="capstone_forward_maneuver",
        duration_s=26.0,
        altitude_waypoints=[(0.0, 0.0), (4.0, 5.0), (14.0, 5.0), (20.0, 0.0), (26.0, 0.0)],
        position_waypoints=[
            (0.0, (0.0, 0.0)), (6.0, (0.0, 0.0)), (11.0, (6.0, 0.0)),
            (12.5, (7.5, 0.0)), (14.0, (7.5, 0.0)), (26.0, (7.5, 0.0)),
        ],
        success_criteria=[
            ("arrived", lambda v: bool(
                np.abs(v.states[v.times >= v.times[-1] - 2.0][:, 0] - 7.5).max() < 0.5)),
            ("no_critical_failure", lambda v: not any(e.critical for e in v.events)),
        ],
    )
    mres = run_scenario(design, maneuver, library, control_dt_s=0.004, substeps=2)
    goals["G4_forward_maneuver"] = {
        "passed": bool(not mres.aborted and all(mres.success.values())),
        "detail": _mission_summary(mres),
    }

    # --- wind gust (G5) ------------------------------------------------------
    # Equivalent constant lateral force over a window (gust approximation,
    # flagged): 8 m/s gust on an assumed 0.8 m^2 frontal area -> ~30 N.
    # The design's CdA (0.10) models parasite drag in flight, not the gust
    # load on the whole airframe; the larger area is the declared assumption.
    GUST_AREA_M2 = 0.8
    gust_force = 0.5 * 1.225 * GUST_AREA_M2 * 8.0 ** 2
    gust = Scenario(
        name="capstone_wind_gust",
        duration_s=16.0,
        altitude_waypoints=[(0.0, 0.0), (2.0, 5.0), (16.0, 5.0)],
        disturbances=[
            Disturbance(t_start=6.0, t_end=7.5, force_world=np.array([gust_force, 0.0, 0.0])),
        ],
        success_criteria=[
            ("gust_rejected", lambda v: bool(
                np.abs(v.states[v.times >= v.times[-1] - 2.0][:, 0]).max() < 1.5
                and np.abs(v.states[v.times >= v.times[-1] - 2.0][:, 2] - 5.0).max() < 0.3)),
            ("no_critical_failure", lambda v: not any(e.critical for e in v.events)),
        ],
    )
    gres = run_scenario(design, gust, library, control_dt_s=0.004, substeps=2)
    goals["G5_wind_gust_rejected"] = {
        "passed": bool(not gres.aborted and all(gres.success.values())),
        "detail": {**_mission_summary(gres),
                   "gust_force_n": round(gust_force, 1),
                   "note": "equivalent constant lateral force for an 8 m/s gust on "
                           "an assumed 0.8 m^2 frontal area (flagged approximation, "
                           "no turbulence spectrum)"},
    }

    # --- motor failure (G6) --------------------------------------------------
    fail = Scenario(
        name="capstone_motor_failure",
        duration_s=14.0,
        altitude_waypoints=[(0.0, 0.0), (4.0, 5.0), (14.0, 5.0)],
        motor_failure_at_s=6.0,
        success_criteria=[],
    )
    fres = run_scenario(design, fail, library, control_dt_s=0.004, substeps=2)
    if fres.aborted:
        outcome = f"NOT RECOVERABLE — aborted: {fres.abort_event.message}"
        passed = True  # goal is a NAMED outcome, not survival
        survived = False
    else:
        tail = fres.states[fres.times >= fres.times[-1] - 2.0]
        held = (np.abs(tail[:, 2] - 5.0).max() < 0.5
                and np.abs(tail[:, 0]).max() < 1.0)
        outcome = ("RECOVERED — controller held altitude/attitude on 5 rotors"
                   if held else
                   "SURVIVED but degraded — did not crash, station-keeping outside tolerance")
        passed = True
        survived = bool(held)
    goals["G6_motor_failure_outcome_recorded"] = {
        "passed": passed,
        "detail": {"outcome": outcome, "survived": survived,
                   "events": [{"kind": e.kind, "critical": e.critical}
                              for e in fres.events]},
    }

    # --- uncertainty (G9) ----------------------------------------------------
    uq = monte_carlo_endurance(design, library, n_samples=uq_samples, seed=42).summary()
    goals["G9_endurance_with_uncertainty"] = {
        "passed": uq["best_estimate"] > 0 and uq["p05"] > 0,
        "detail": uq,
    }

    # --- structural margin (G8) + V&V (benchmarks + convergence) ------------
    struct_margin = _structural_margin(design, library)
    goals["G8_structural_margin"] = {
        "passed": bool(struct_margin is not None and struct_margin >= 1.0),
        "detail": {"structural_margin_min": struct_margin,
                   "basis": "worst-case arm load = max measured static thrust "
                            "at the arm tip (hover margin is higher)"},
    }

    vv = generate_vv_report(design, library, uq_samples=min(uq_samples, 40))

    all_passed = all(g["passed"] for g in goals.values())
    elapsed = time.perf_counter() - t0

    return {
        "report": "AeroForge capstone credibility report (M8)",
        "design": {
            "name": design.name,
            "snapshot_notes": design.notes,
            "mass_kg": static["design"]["mass_kg"],
            "n_rotors": len(design.rotors),
            "powertrain": design.powertrain.model_dump() if design.powertrain else None,
            "frame": design.frame.model_dump() if design.frame else None,
        },
        "design_goals": goals,
        "all_goals_passed": all_passed,
        "static_analysis": {
            "hover_point": hover_point,
            "endurance": static["endurance"],
            "benchmarks": static["benchmarks"],
        },
        "mission_suite": {
            "hover_hold": hold["results"],
            "flight": flight["results"],
            "forward_maneuver": _mission_summary(mres),
            "wind_gust": _mission_summary(gres),
            "motor_failure": _mission_summary(fres),
        },
        "uncertainty": uq,
        "vv_report": vv,
        "elapsed_s": round(elapsed, 1),
    }


def _structural_margin(design: DroneDesign, library: ComponentLibrary) -> float | None:
    from physics.structures.beam import check_arm
    from physics.structures.materials import load_materials

    if design.frame is None or design.powertrain is None:
        return None
    motor = library.motor(design.powertrain.motor_id)
    prop = library.propeller(design.powertrain.propeller_id)
    dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
    rpm_hi = float(dataset.envelope()["rpm_range_merged"][1])
    max_thrust = float(dataset.thrust_n(rpm_hi).value)  # worst-case arm load
    materials = load_materials(library.data_dir / "materials.json")
    material = materials[design.frame.material_id]
    check = check_arm(max_thrust, design.frame.arm_length_m,
                      design.frame.tube_od_m, design.frame.tube_id_m, material)
    return check.margin


def main() -> int:
    parser = argparse.ArgumentParser(description="AeroForge capstone credibility report.")
    parser.add_argument("--design", default=str(REPO_ROOT / "data" / "designs" / "hexa_p80_60kg.json"))
    parser.add_argument("--out", default=str(REPO_ROOT / "outputs" / "capstone_report"))
    parser.add_argument("--uq-samples", type=int, default=150)
    args = parser.parse_args()

    design = DroneDesign.model_validate_json(Path(args.design).read_text(encoding="utf-8"))
    library = ComponentLibrary(REPO_ROOT / "data" / "components")

    report = run_capstone(design, library, uq_samples=args.uq_samples)
    out_base = Path(args.out)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    out_base.with_suffix(".json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human-readable summary.
    lines = [f"# {report['report']}", ""]
    d = report["design"]
    lines.append(f"**Design**: {d['name']} — {d['mass_kg']:.3f} kg AUW, {d['n_rotors']} rotors")
    lines.append(f"**Elapsed**: {report['elapsed_s']} s")
    lines.append("")
    lines.append(f"**All design goals passed: {report['all_goals_passed']}**")
    lines.append("")
    for gid, g in report["design_goals"].items():
        lines.append(f"- [{'PASS' if g['passed'] else 'FAIL'}] {gid}")
    lines.append("")
    lines.append("## Endurance (Monte Carlo)")
    u = report["uncertainty"]
    lines.append(f"- best estimate {u['best_estimate']:.0f} s (5-95 %: {u['p05']:.0f}-{u['p95']:.0f} s)")
    lines.append("")
    lines.append("## V&V verdict")
    vv = report["vv_report"]
    lines.append(f"- needs further analysis: {vv['needs_further_analysis']}")
    for f in vv["gated_failures"]:
        lines.append(f"  - FAIL: {f}")
    md = "\n".join(lines) + "\n\n" + render_markdown(vv)
    out_base.with_suffix(".md").write_text(md, encoding="utf-8")

    print(md)
    print(f"written: {out_base.with_suffix('.json')}, {out_base.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
