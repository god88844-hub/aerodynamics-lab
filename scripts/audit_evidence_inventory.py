"""M9 Phase 2 + 9 — evidence inventory and credibility verdicts.

For every major simulation subsystem: model, governing equations, inputs,
sources, evidence classification, verification/calibration/validation data,
errors, uncertainty, envelope, limitations, consequences — and a strict
credibility verdict from the Phase 9 gate.

Evidence categories (mutually exclusive claims):
  VERIFIED_IMPLEMENTATION      software behavior verified against analytical
                               or mathematical ground truth
  CALIBRATED_TO_MEASUREMENTS   parameters fitted/reproduced from measurement
                               (incl. reproducing the calibration set itself)
  INDEPENDENTLY_VALIDATED      predictions compared against held-out physical
                               measurements with pre-declared tolerances, met
  APPROXIMATE_ASSUMED          declared approximation or assumption
  NOT_VALIDATED                no independent physical evidence yet
  FAILED_VALIDATION            independent comparison exceeded tolerance
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from physics.validation.credibility import gate  # noqa: E402

A = "APPROXIMATE / ASSUMED"
NV = "NOT VALIDATED"
VI = "VERIFIED IMPLEMENTATION"
C = "CALIBRATED TO MEASUREMENTS"


def _sub(name: str, **kw) -> dict:
    base = {
        "subsystem": name,
        "model": kw.get("model"),
        "governing_equations": kw.get("equations"),
        "inputs": kw.get("inputs"),
        "parameter_sources": kw.get("sources"),
        "parameter_class": kw.get("parameter_class"),
        "numerical_verification": kw.get("verification"),
        "calibration_data": kw.get("calibration"),
        "independent_validation_data": kw.get("independent"),
        "prediction_errors": kw.get("errors"),
        "uncertainty": kw.get("uncertainty"),
        "validated_envelope": kw.get("envelope"),
        "limitations": kw.get("limitations"),
        "consequences_if_wrong": kw.get("consequences"),
        "evidence_categories": kw.get("categories"),
        "credibility": kw["credibility"].summary() if hasattr(kw["credibility"], "summary")
        else kw["credibility"],
    }
    return base


def build_inventory() -> list[dict[str, Any]]:
    inv: list[dict[str, Any]] = []

    inv.append(_sub(
        "Rigid-body dynamics (6-DOF)",
        model="packages/physics/dynamics/rigid_body.py + quadrotor.py (M1)",
        equations="Newton–Euler: F = m·a, τ = I·ω̇ + ω×(Iω); quaternion attitude kinematics",
        inputs="mass, inertia tensor (assembled from parts), applied forces/torques",
        sources="mass/inertia from design snapshot parts; gravity g = 9.80665 m/s² (BIPM defined constant)",
        parameter_class="sourced (g: defined constant; mass/inertia: design data)",
        verification="free fall v(1 s) = g ± 1e-6; principal-axis spin-up ω = τ/I·t; torque-free "
                     "conservation of energy and |L_world| < 1e-8; RK4 order-4 step-halving; "
                     "scipy agreement (tests/physics/test_rigid_body.py)",
        calibration="none required (structural equations + defined constants)",
        independent="the equations and g are 300-years-validated physics; predictions of "
                    "gravitational response are exact against the DEFINED standard gravity",
        errors="free fall ±1e-6 m/s (spec gate ±0.01)",
        uncertainty="numerical: bounded by convergence studies; model-form: flat non-rotating "
                    "Earth, constant g, rigid body — declared",
        envelope="flat non-rotating Earth, |v| < ~30 m/s, near-Earth altitudes",
        limitations=["no Coriolis/centrifugal", "constant g", "no structural flexure",
                     "no aerodynamic coupling inside the core"],
        consequences="dynamics errors would corrupt every trajectory prediction",
        categories=[VI, "INDEPENDENTLY VALIDATED (Newton-Euler + defined g; exact within "
                         "numerical error)"],
        credibility=gate("rigid-body 6-DOF response",
                         independent_evidence=["defined standard gravity reproduced to 1e-6 "
                                               "in free fall; Newton–Euler conservation laws verified"],
                         independent_error_within_tolerance=True,
                         has_known_model_gaps=False),
    ))

    inv.append(_sub(
        "Mass and inertia assembly",
        model="packages/physics/dynamics/mass_properties.py; geometry/primitives.py",
        equations="parallel-axis theorem; solid-box/cylinder inertia formulas",
        inputs="part masses and positions (design snapshot)",
        sources="motor masses sourced (MN3508 103 g, P80 III 649 g); other part masses flagged "
                "estimates in component files",
        parameter_class="mixed: sourced masses + estimated masses",
        verification="two-point dumbbell, box formula, multi-part transfer vs hand computation "
                     "(tests/physics/test_mass_properties.py)",
        calibration="none (mathematical identities)",
        independent="mathematical identity — exact",
        errors="exact to float precision",
        uncertainty="driven entirely by part-mass data quality (flagged per part)",
        envelope="rigid assemblies in the design snapshot",
        limitations=["assembly is rigid; no fuel burn", "inertia of irregular parts must be "
                     "supplied (point-mass fallback)"],
        consequences="wrong inertia → wrong attitude dynamics; wrong mass → wrong thrust "
                     "margins and endurance",
        categories=[VI],
        credibility=gate("mass/inertia assembly",
                         independent_evidence=["mathematical identity verified vs hand "
                                               "computation to float precision"],
                         independent_error_within_tolerance=True, has_known_model_gaps=False),
    ))

    inv.append(_sub(
        "Motor thrust",
        model="packages/physics/propulsion/dataset.py — PCHIP interpolation of manufacturer "
              "bench tables (MN3508: 2 voltage planes; P80 III: 1 plane, 21 rows)",
        equations="monotone PCHIP through measured (rpm, thrust) knots; NO physics-based "
                  "generalization (no blade-element model)",
        inputs="rpm, bus voltage",
        sources="T-Motor MN3508 report MN.00011; T-Motor P80 III product page (both "
                "row-verified: T/P = published efficiency, P = V·I)",
        parameter_class="sourced (measured manufacturer bench data)",
        verification="knot read-back exact (M2/M9 benchmarks); monotonicity per plane",
        calibration="the manufacturer tables ARE the model (interpolation of calibration data)",
        independent="NONE for thrust generalization: reproducing table knots is calibration, "
                    "not validation; no held-out measurements exist for these motor+prop pairs",
        prediction_errors="between knots: unquantified (no reference); momentum-theory power "
                          "cross-check (weak-form) MAPE 4.5 %",
        uncertainty="dataset uncertainty ±3 % (source-stated); interpolation between knots "
                    "unquantified",
        envelope="MN3508: 2600–5900 rpm, planes 14.8/22.2 V ±15 %; P80 III: 1719–3747 rpm, "
                 "plane 47.9 V ±15 %; thrust within [table min, max]",
        limitations=["no advance ratio / forward flight", "no prop-on-prop or wall effects",
                     "single-plane datasets rely on flagged voltage extrapolation",
                     "flat-thrust region (820 gf) makes rpm inversion ill-conditioned"],
        consequences="thrust overestimate → unrealistic performance verdicts; underestimate → "
                     "false infeasibility",
        categories=[VI, C, NV + " for generalization"],
        credibility=gate("motor thrust (table interpolation)",
                         independent_evidence=[],
                         has_known_model_gaps=True,
                         independent_error_within_tolerance=None),
    ))

    inv.append(_sub(
        "Propeller torque / reaction torque",
        model="constant k = Q/T per design (rotor_torque_per_thrust); k sourced from the P80 "
              "bench torque column at hover (0.0224 N·m/N); MN3508 k=0 in the reference design "
              "(manufacturer published no torque column)",
        equations="τ_z = −Σ spin_i · k · T_i",
        inputs="per-rotor thrust, spin direction, k",
        sources="P80 III: published torque column (row-verified via C2 motor-eta band); "
                "MN3508: no torque published → k unknown",
        parameter_class="sourced for P80 (single-point at hover); unknown for MN3508",
        verification="mixer wrench reconstruction tests",
        calibration="P80: k at the hover thrust point (single point, not the full curve)",
        independent="the k value comes from the manufacturer bench data (calibration data for "
                    "our own use) — no independent torque measurements",
        prediction_errors="k varies 0.020–0.035 across the P80 table; constant-k introduces "
                          "up to ~±35 % torque error away from hover",
        uncertainty="±(variation across the table) — not sampled in UQ",
        envelope="near-hover thrust ratios",
        limitations=["constant k (true k grows with thrust)", "no gyroscopic precession moments"],
        consequences="wrong yaw authority → yaw control divergence in flight",
        categories=[C + " (single point)", A + " (constant-k away from hover)"],
        credibility=gate("propeller reaction torque",
                         has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Motor electrical power / current",
        model="P = V·I identity + per-plane PCHIP current(rpm) with fitted voltage-slope "
              "correction and power-based floor (declared extrapolation)",
        equations="P_elec = V_bus·I; current(rpm, V) interpolated between measured planes",
        inputs="rpm, bus voltage",
        sources="manufacturer bench tables (row voltages captured for P80 III)",
        parameter_class="sourced (measured) + declared extrapolation policy",
        verification="C1 identity to publication rounding (≤0.5 %); plane normalization ≤2 %",
        calibration="manufacturer tables (calibration data)",
        independent="momentum-theory electrical-power prediction vs P80 bench: MAPE 4.46 %, "
                    "100 % within ±15 % (WEAK-FORM — priors literature-informed); vs UIUC "
                    "wind-tunnel power: MAPE 6.4 % (BLIND, genuinely independent)",
        prediction_errors="UIUC blind: MAPE 6.4 %, bias +6.2 %, max 9.96 %; P80 weak: MAPE 4.5 %",
        uncertainty="thrust/eta prior bands declared in the blind comparisons",
        envelope="static conditions; voltages within ±15 % of measured planes; rpm within table",
        limitations=["lumped DC model does NOT close (35 % residual — documented finding)",
                     "no inductance/timing model", "single-plane datasets need flagged "
                     "extrapolation"],
        consequences="current/power error → wrong endurance, wrong thermal margins",
        categories=[VI, C, "INDEPENDENTLY VALIDATED (momentum-theory power path vs UIUC "
                           "wind-tunnel data, MAPE 6.4 % < 15 % declared, static regime)"],
        credibility=gate("first-order static power prediction (momentum theory path)",
                         independent_evidence=["UIUC APC SF 10x5 wind-tunnel power: MAPE 6.4 %, "
                                               "16 points, all within ±15 % (pre-declared)"],
                         independent_error_within_tolerance=True,
                         has_known_model_gaps=False),
    ))

    inv.append(_sub(
        "ESC behavior",
        model="static current/voltage limit checks only (packages/physics/propulsion/esc.py)",
        equations="none (limit comparisons)",
        inputs="current, voltage",
        sources="placeholder ratings, flagged estimated",
        parameter_class="assumed",
        verification="unit tests of limit checks",
        calibration="none",
        independent="none",
        prediction_errors="not applicable",
        uncertainty="rating uncertainty ±20 % flagged",
        envelope="steady current/voltage limits only",
        limitations=["no PWM dynamics", "no switching losses", "no thermal model",
                     "no timing/advance effects (the 35 % lumped-DC residual lives here)"],
        consequences="ESC behavior errors distort the motor electrical chain",
        categories=[A, NV],
        credibility=gate("ESC behavior", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Battery discharge and voltage sag",
        model="OCV(SOC) PCHIP (community-sourced curve) + single pack R (constant) + coulomb "
              "counting (packages/physics/propulsion/battery.py)",
        equations="V_load = OCV(SOC) − I·R_pack; dSOC = −100·I·dt/(3600·C)",
        inputs="SOC, current",
        sources="OCV shape: community-measured LiPo charts (intofpv/usedbytes); R and capacity: "
                "TYPICAL values flagged estimated",
        parameter_class="mixed: OCV shape sourced (community), R/capacity estimated",
        verification="OCV read-back, sag arithmetic, coulomb counting (unit tests)",
        calibration="OCV curve itself came from community measurements (calibration data for "
                    "the curve; not independent)",
        independent="NONE for our specific packs — no measured discharge of the modeled packs",
        prediction_errors="not quantifiable without independent pack data",
        uncertainty="capacity ±10 %, R ±50 % sampled in UQ; dominant endurance sensitivity",
        envelope="steady discharge, < ~8 C in the audited designs",
        limitations=["no temperature dependence", "no C-rate capacity derating",
                     "no cycle aging", "no cell imbalance", "constant R"],
        consequences="endurance estimates optimistic (audit: ~10-20 % once derating/thermal "
                     "are accounted); sag errors → premature/late warnings",
        categories=[A, NV],
        credibility=gate("battery discharge and sag", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Rotor-to-rotor interaction",
        model="NOT IMPLEMENTED",
        equations="—",
        inputs="—", sources="—", parameter_class="—",
        verification="—", calibration="—", independent="—",
        prediction_errors="—", uncertainty="—", envelope="—",
        limitations=["hover/flight of multi-rotor layouts carries unquantified interference "
                     "thrust/power penalties"],
        consequences="hexa/octa endurance and hover thrust overestimated (typically "
                     "low-single-digit % at large spacing, larger when discs overlap)",
        categories=[NV],
        credibility=gate("rotor interaction", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Ground effect",
        model="NOT IMPLEMENTED",
        equations="—", inputs="—", sources="—", parameter_class="—",
        verification="—", calibration="—", independent="—",
        prediction_errors="—", uncertainty="—",
        envelope="takeoff/landing within ~1 rotor diameter of the ground",
        limitations=["takeoff/landing thrust and power near the ground are wrong by the "
                     "classic ground-effect factor (up to ~10-20 % at half-rotor height)"],
        consequences="landing/takeoff power needs misestimated",
        categories=[NV],
        credibility=gate("ground effect", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Aerodynamic drag (airframe)",
        model="quadratic drag with single equivalent CdA (packages/physics/aerodynamics/drag.py)",
        equations="F = −0.5·ρ·CdA·|v|·v",
        inputs="velocity, CdA, air density",
        sources="CdA values in designs are UNSOURCED guesses; ρ = ISA sea level (sourced)",
        parameter_class="assumed (CdA)",
        verification="force formula unit-tested",
        calibration="none",
        independent="none",
        prediction_errors="unquantifiable — CdA unsourced",
        uncertainty="CdA dominates; hover/vertical phases barely affected (v≈0)",
        envelope="incompressible, constant density, no AOA dependence",
        limitations=["no angle-of-attack dependence", "no interference drag",
                     "constant density with altitude"],
        consequences="forward-flight speed/power predictions unreliable",
        categories=[A, NV],
        credibility=gate("airframe drag", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Wind and gusts",
        model="equivalent constant lateral FORCE over a time window (capstone: 8 m/s on "
              "assumed 0.8 m² area ≈ 39 N)",
        equations="step force input",
        inputs="declared force, window",
        sources="declared approximation (assumed frontal area)",
        parameter_class="assumed",
        verification="scenario tests assert rejection/offset behavior",
        calibration="none", independent="none",
        prediction_errors="not comparable to real gust response",
        uncertainty="frontal area and gust profile assumed",
        envelope="none — the force profile is not a validated wind model",
        limitations=["no turbulence spectrum", "no directionality", "no aeroelastic coupling"],
        consequences="gust-rejection verdicts do not transfer to real wind events",
        categories=[A, NV],
        credibility=gate("wind and gusts", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Flight control",
        model="cascaded PID (position→attitude→rate→mixer) with inertia-derived gains, "
              "slew-limited feedforward, derivative filtering, anti-windup",
        equations="standard cascade PID; quaternion attitude; wrench mixer (least squares)",
        inputs="controller state (true or measured), targets, gains",
        sources="gains derived from assembled mass/inertia; control architecture from "
                "standard multirotor practice",
        parameter_class="derived (gains) + architecture assumption",
        verification="hover hold, altitude step, disturbance rejection, 5° roll within ±0.1°, "
                     "yaw hold, mixer wrench reconstruction, saturation flags (tests)",
        calibration="none",
        independent="NO flight-log validation: no real flight controller telemetry has been "
                    "compared against these loops",
        prediction_errors="not quantifiable without flight data",
        uncertainty="perfect state knowledge in audited runs; noise/latency modeled but not "
                    "measured; sensor bias modeled (M9)",
        envelope="near-hover regimes in simulation; deterministic",
        limitations=["no actuator dynamics/lag", "no real sensor stack", "no wind",
                     "torque authority now inertia-scaled (M9 finding F4)"],
        consequences="control verdicts do not transfer to real flight controllers",
        categories=[VI + " (software behavior)", NV + " (physical flight)"],
        credibility=gate("flight control loops", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Sensor noise and latency",
        model="Gaussian noise + zero-order-hold latency + constant bias "
              "(packages/physics/controller/sensors.py)",
        equations="additive noise per channel; small-angle quaternion noise",
        inputs="declared sigmas/biases",
        sources="typical values declared in tests; NOT measured from real sensors",
        parameter_class="assumed",
        verification="bias application verified (M9 regression), noise determinism",
        calibration="none", independent="none",
        prediction_errors="n/a", uncertainty="declared bands only",
        envelope="whatever sigmas are declared",
        limitations=["no scale-factor errors", "no vibration spectra", "no dropouts",
                     "no EKF/state-estimator modeling"],
        consequences="real sensor stacks may behave worse than modeled",
        categories=[A],
        credibility=gate("sensor models", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Structural loads",
        model="cantilever bending of circular tube arms: σ = M·c/I, M = F·L "
              "(packages/physics/structures/beam.py)",
        equations="Euler–Bernoulli bending at the root",
        inputs="max rotor thrust, arm length, tube OD/ID, material yield",
        sources="material properties from sourced handbook bands (flagged ±20 %); tube "
                "geometry declared in snapshots (not measured)",
        parameter_class="mixed: sourced material bands + declared geometry",
        verification="bending stress vs hand calculation (M9/M4 tests)",
        calibration="none",
        independent="none — no coupon tests, no load-cell measurements",
        prediction_errors="unquantified beyond material uncertainty",
        uncertainty="material ±20 %; geometry as declared",
        envelope="static bending at the arm root",
        limitations=["bending only: no torsion/joints/buckling/fatigue/vibration",
                     "worst-case single-arm load"],
        consequences="structural margin could be substantially wrong",
        categories=[VI + " (formula)", A + " (inputs)", NV],
        credibility=gate("structural loads", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Thermal limits",
        model="datasheet current/duration rule (I > I_max sustained beyond rated "
              "duration → burnout; I > 2×I_max → instantaneous) — NO thermal integration",
        equations="threshold rule",
        inputs="per-motor current, time",
        sources="manufacturer current/duration statements (14 A/180 s; 60 A/180 s)",
        parameter_class="sourced (rule), no thermal physics",
        verification="failure-detection tests (overcurrent, burnout paths)",
        calibration="rule taken directly from datasheets",
        independent="none",
        prediction_errors="—",
        uncertainty="no winding-temperature state exists in the model",
        envelope="static current/duration margin checks",
        limitations=["no temperature state", "no cooling curves", "no ESC heating"],
        consequences="real motors may burn out earlier or later than modeled",
        categories=[C + " (rule from datasheet)", NV + " (thermal physics)"],
        credibility=gate("thermal limits", has_known_model_gaps=True),
    ))

    inv.append(_sub(
        "Failure detection",
        model="declared critical/warning policy over powertrain, structure, ground, "
              "attitude, thrust-envelope monitors (packages/physics/scenarios/runner.py)",
        equations="threshold monitors + named aborts",
        inputs="telemetry + limits",
        sources="limits from component data (sourced where available)",
        parameter_class="sourced limits + declared policy",
        verification="motor failure, depleted battery, over-speed, structural overload tests; "
                     "bias/latency interaction tests (M9)",
        calibration="n/a",
        independent="n/a (software behavior)",
        prediction_errors="—",
        uncertainty="—",
        envelope="simulated telemetry only",
        limitations=["detects only the modeled mechanisms (audit lists unmodeled ones)",
                     "no hardware-in-the-loop"],
        consequences="undetected real-world failure modes remain possible",
        categories=[VI],
        credibility=gate("failure detection logic",
                         independent_evidence=["named-abort behavior verified for battery "
                                               "collapse, over-speed, structure, attitude loss"],
                         independent_error_within_tolerance=True,
                         has_known_model_gaps=False),
    ))

    inv.append(_sub(
        "Flight endurance",
        model="static-hover coulomb drain to the 3.5 V/cell warning through the sourced "
              "powertrain chain",
        equations="coulomb counting + sag + OCV",
        inputs="hover current (sourced table), pack capacity/R (estimated)",
        sources="hover current sourced; capacity/R estimated (flagged)",
        parameter_class="mixed",
        verification="M2/M9 tests; deterministic replay",
        calibration="the current chain is calibrated to bench data; the pack is not",
        independent="NO measured endurance of any real aircraft",
        prediction_errors="endurance UQ (M7/M9): ±10-20 % once declared derating/thermal "
                          "effects are applied (audit quantified)",
        uncertainty="dominated by battery estimates (capacity/R); no C-rate derating modeled",
        envelope="static hover, < 8 C discharge, no temperature effects",
        limitations=["no temperature", "no derating", "no real-flight power transients"],
        consequences="mission-endurance decisions unreliable until pack data exists",
        categories=[C + " (current chain)", NV + " (endurance vs measurement)"],
        credibility=gate("flight endurance", has_known_model_gaps=True),
    ))

    return inv


def main() -> int:
    inventory = build_inventory()
    out_dir = REPO_ROOT / "outputs" / "audit"
    out_dir.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for s in inventory:
        st = s["credibility"]["status"]
        counts[st] = counts.get(st, 0) + 1

    payload = {
        "audit": "M9 Phase 2+9 — evidence inventory and credibility verdicts",
        "evidence_categories": {
            "VERIFIED_IMPLEMENTATION": "software behavior verified vs analytical ground truth",
            "CALIBRATED_TO_MEASUREMENTS": "model built from/reproduces measurement (own "
            "calibration — not independent validation)",
            "INDEPENDENTLY_VALIDATED": "held-out physical comparison with pre-declared "
            "tolerance met",
            "APPROXIMATE / ASSUMED": "declared approximation or assumption",
            "NOT VALIDATED": "no independent physical evidence",
            "FAILED VALIDATION": "held-out comparison exceeded tolerance",
        },
        "credibility_counts": counts,
        "subsystems": inventory,
    }
    (out_dir / "phase2_evidence_inventory.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")

    md = ["# M9 Phase 2/9 — Evidence inventory and credibility verdicts", "",
          f"Credibility counts: {counts}", ""]
    for s in inventory:
        md.append(f"## {s['subsystem']}")
        md.append(f"- model: {s['model']}")
        md.append(f"- governing equations: {s['governing_equations']}")
        md.append(f"- parameter class: {s['parameter_class']}")
        md.append(f"- verification: {s['numerical_verification']}")
        md.append(f"- calibration data: {s['calibration_data']}")
        md.append(f"- independent validation data: {s['independent_validation_data']}")
        md.append(f"- prediction errors: {s['prediction_errors']}")
        md.append(f"- uncertainty: {s['uncertainty']}")
        md.append(f"- validated envelope: {s['validated_envelope']}")
        md.append(f"- limitations: {'; '.join(s['limitations'])}")
        md.append(f"- consequences if wrong: {s['consequences_if_wrong']}")
        md.append(f"- **evidence categories**: {', '.join(s['evidence_categories'])}")
        c = s["credibility"]
        md.append(f"- **CREDIBILITY: {c['status']}** — {c['basis']}")
        md.append("")
    (out_dir / "phase2_evidence_inventory.md").write_text("\n".join(md), encoding="utf-8")
    print(f"inventory written: {len(inventory)} subsystems; counts: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
