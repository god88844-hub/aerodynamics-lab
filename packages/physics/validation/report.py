"""V&V report generator (M7): benchmarks + convergence + uncertainty in one
document, with an explicit needs-further-analysis flag when any gated metric
deviates beyond its declared tolerance.

Output shape (JSON) feeds both the CLI and the API/UI; a markdown rendering
is written alongside for humans.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aeroforge_schemas.design import DroneDesign
from physics.dynamics.design_adapter import build_multirotor
from physics.propulsion.dataset import PowertrainDataset
from physics.propulsion.loader import ComponentLibrary
from physics.validation.benchmarks import run_propulsion_benchmarks
from physics.validation.convergence import (
    analytic_convergence,
    closed_loop_convergence,
    solver_tolerance_study,
)
from physics.validation.uq import monte_carlo_endurance


def generate_vv_report(
    design: DroneDesign,
    library: ComponentLibrary,
    uq_samples: int = 200,
    uq_seed: int = 42,
) -> dict[str, Any]:
    gated_failures: list[str] = []

    # --- propulsion benchmarks (gated) ------------------------------------
    propulsion: list[dict] = []
    if design.powertrain is not None:
        motor = library.motor(design.powertrain.motor_id)
        prop = library.propeller(design.powertrain.propeller_id)
        dataset = PowertrainDataset(motor, prop.motor_test_data_key or prop.id)
        for b in run_propulsion_benchmarks(dataset):
            propulsion.append({
                "name": b.name, "status": b.status,
                "metrics": b.metrics, "tolerances": b.tolerances, "notes": b.notes,
            })
            if b.status == "fail":
                gated_failures.append(f"propulsion: {b.name}")
    else:
        propulsion.append({"name": "propulsion benchmarks", "status": "skipped",
                           "notes": "no powertrain attached to this design"})

    # --- dynamics verification (analytic, gated) ---------------------------
    dynamics: list[dict] = []
    plant, mass_props = build_multirotor(design)
    trim = plant.hover_trim()
    weight = mass_props.mass_kg * 9.80665
    total_trim = float(sum(trim))
    err = abs(total_trim - weight) / weight
    dynamics.append({
        "name": "hover trim equals weight",
        "status": "pass" if err <= 1e-9 else "fail",
        "metrics": {"relative_error": err},
        "tolerances": {"relative_error": 1e-9},
    })
    if err > 1e-9:
        gated_failures.append("dynamics: hover trim equals weight")

    conv_analytic = analytic_convergence()
    conv_solver = solver_tolerance_study()
    conv_closed = closed_loop_convergence(design, library)
    convergence = [conv_analytic.summary(), conv_solver.summary(), conv_closed.summary()]
    for c in convergence:
        if not c["converged"]:
            gated_failures.append(f"convergence: {c['name']}")

    # --- uncertainty quantification (informational, no gate) ---------------
    uq = None
    if design.powertrain is not None:
        uq = monte_carlo_endurance(design, library, n_samples=uq_samples, seed=uq_seed).summary()

    report: dict[str, Any] = {
        "design": {
            "name": design.name,
            "mass_kg": mass_props.mass_kg,
            "n_rotors": len(design.rotors),
        },
        "benchmarks": {"propulsion": propulsion, "dynamics": dynamics},
        "convergence": convergence,
        "uncertainty": uq,
        "needs_further_analysis": len(gated_failures) > 0,
        "gated_failures": gated_failures,
        "validated_vs_assumed": {
            "validated": [
                "dynamics core (analytical solutions: free fall, spin-up, conservation laws)",
                "mass-property assembly (parallel-axis hand calculations)",
                "propulsion static table (manufacturer bench data, read-back gate)",
                "full-throttle chain reproduction",
            ],
            "assumed_or_estimated": [
                "rotor reaction torque k (sourced from the bench torque column when "
                "published — e.g. P80 III; otherwise derived with assumed eta=0.8)",
                "battery capacity/mass/IR (flagged estimates)",
                "propeller mass (flagged estimate)",
                "ESC rating (placeholder)",
                "airframe drag CdA (unsourced approximation)",
                "quasi-static bus solve; no thermal integration; no wind",
            ],
        },
    }
    return report


def render_markdown(report: dict) -> str:
    lines: list[str] = []
    lines.append("# AeroForge V&V Report")
    lines.append("")
    d = report["design"]
    lines.append(f"**Design**: {d['name']} — {d['mass_kg']:.3f} kg, "
                 f"{d['n_rotors']} rotors")
    lines.append("")
    verdict = ("NEEDS FURTHER ANALYSIS" if report["needs_further_analysis"]
               else "all gated metrics within tolerance")
    lines.append(f"**Verdict**: {verdict}")
    if report["gated_failures"]:
        for f in report["gated_failures"]:
            lines.append(f"- FAIL: {f}")
    lines.append("")

    lines.append("## Benchmarks")
    for section in ("propulsion", "dynamics"):
        for b in report["benchmarks"][section]:
            metrics = ", ".join(f"{k}={v:.3g}" for k, v in (b.get("metrics") or {}).items())
            lines.append(f"- [{b['status'].upper()}] {b['name']} — {metrics}")
    lines.append("")
    lines.append("## Convergence")
    for c in report["convergence"]:
        state = "converged" if c["converged"] else "NOT CONVERGED"
        lines.append(f"- [{state}] {c['name']} (tolerance {c['tolerance']})")
    lines.append("")
    if report.get("uncertainty"):
        u = report["uncertainty"]
        lines.append("## Uncertainty (Monte Carlo)")
        lines.append(
            f"- {u['quantity']}: best estimate {u['best_estimate']:.0f} s "
            f"(mean {u['mean']:.0f} s, std {u['std']:.0f} s, 5–95 %: "
            f"{u['p05']:.0f}–{u['p95']:.0f} s, n={u['n_samples']})"
        )
        lines.append("- sensitivities (endurance at parameter edges):")
        for name, s in u["sensitivities"].items():
            lines.append(f"  - {name}: {s['endurance_low_s']:.0f} – "
                         f"{s['endurance_high_s']:.0f} s (Δ {s['delta_s']:.0f} s)")
    lines.append("")
    lines.append("## Validated vs assumed")
    lines.append("- **validated**: " + "; ".join(report["validated_vs_assumed"]["validated"]))
    lines.append("- **assumed/estimated**: " + "; ".join(report["validated_vs_assumed"]["assumed_or_estimated"]))
    lines.append("")
    return "\n".join(lines)


def write_vv_report(report: dict, out_base: Path) -> None:
    out_base.parent.mkdir(parents=True, exist_ok=True)
    out_base.with_suffix(".json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    out_base.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
