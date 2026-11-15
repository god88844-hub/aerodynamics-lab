# M9 — Independent Scientific Validation Audit

**Commit under audit**: `8ec1eb4` (M0–M8 complete) · audit date 2026-11-16 · auditor: the coding agent, with every command and result recorded in [outputs/audit/](../../outputs/audit/) and reproduced by the test suite.

## 1. Reproducibility

All prior claims reproduced independently before any changes were made (recorded as-found in `outputs/audit/phase1_reproducibility.md`):

- 122 pytest tests PASS (exit 0)
- web build (tsc + vite) PASS, 6 vitest tests PASS
- Docker image builds; API health OK from the container
- API endpoints verified live (health, components, reference design)
- capstone recomputed fresh: **deterministic replay** — hover power 8064.4 W and endurance 360.0 s bit-identical to the committed report

## 2. Evidence inventory and credibility verdicts

Credibility counts across 17 subsystems: **4 VALIDATED_FOR_THIS_DECISION, 13 PROMISING**, 0 FAILED, 0 INCONCLUSIVE. Full inventory: [phase2_evidence_inventory.md](phase2_evidence_inventory.md).

- **VALIDATED_FOR_THIS_DECISION** — Rigid-body dynamics (6-DOF): independent physical evidence within pre-declared tolerance, no relevant unmodeled mechanisms
- **VALIDATED_FOR_THIS_DECISION** — Mass and inertia assembly: independent physical evidence within pre-declared tolerance, no relevant unmodeled mechanisms
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Motor thrust: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Propeller torque / reaction torque: functions and is verified in software, but no independent physical validation evidence exists yet
- **VALIDATED_FOR_THIS_DECISION** — Motor electrical power / current: independent physical evidence within pre-declared tolerance, no relevant unmodeled mechanisms
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — ESC behavior: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Battery discharge and voltage sag: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Rotor-to-rotor interaction: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Ground effect: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Aerodynamic drag (airframe): functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Wind and gusts: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Flight control: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Sensor noise and latency: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Structural loads: functions and is verified in software, but no independent physical validation evidence exists yet
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Thermal limits: functions and is verified in software, but no independent physical validation evidence exists yet
- **VALIDATED_FOR_THIS_DECISION** — Failure detection: independent physical evidence within pre-declared tolerance, no relevant unmodeled mechanisms
- **PROMISING_FURTHER_EVIDENCE_REQUIRED** — Flight endurance: functions and is verified in software, but no independent physical validation evidence exists yet

## 3. Calibration-vs-validation data ledger

| Dataset | Role | Used for | Independence |
| --- | --- | --- | --- |
| T-Motor MN3508 bench (report MN.00011) | **calibration** | thrust/current interpolation model | manufacturer data; model reproduces it — NOT independent validation |
| T-Motor P80 III bench (product page) | **calibration** | thrust/current interpolation + torque parameter | same — NOT independent validation |
| Community LiPo OCV-SOC charts | **calibration** | battery OCV curve | community data; not independent of the model's curve |
| **UIUC APC SF 10x5 wind-tunnel data** (Brandt & Selig / Dantsker) | **independent validation** | momentum-theory power prediction (Phase 5A) | measured at UIUC; never used in any AeroForge calibration |
| P80 III bench electrical power (held-out from the prediction path) | **independent (weak-form)** | momentum-theory electrical power (Phase 5B) | measured by T-Motor; priors literature-informed → weak-form |
| Defined physical constants (g, unit conversions) | **independent ground truth** | rigid-body verification | defined/exact |

## 4. Independent benchmark results (blind comparisons)

- **A: momentum-theory power vs UIUC measured (BLIND)**: n=16, MAPE 6.4 % (tolerance 15 %, declared a priori), bias 6.19 %, max 9.96 %, within ±15 %: 100.0 % → PASS
- **B: momentum-theory electrical power vs P80 bench (WEAK-FORM)**: n=21, MAPE 4.46 % (tolerance 15 %, declared a priori), bias 2.04 %, max 8.23 %, within ±15 %: 100.0 % → PASS

Plots (predicted vs measured, same axes): [phase5_blind_uiuc.png](../../outputs/audit/phase5_blind_uiuc.png), [phase5_weak_p80.png](../../outputs/audit/phase5_weak_p80.png).

## 5. Numerical verification

- quaternion norm 1.0 ± 1e-12 through full missions (regression test)
- force/moment balance vs mixer geometry (random thrust vectors, 1e-12)
- mass constant through flight; energy < pack nominal (bounds test)
- deterministic replay: identical state/thrust arrays; UQ seed reproducibility
- convergence studies (M7) re-verified: analytic, solver tolerance, closed-loop substeps — all converged
- audit finding F1 fixed with regression tests: monotonicity must be checked per voltage plane (cross-plane interleaving produced a false decrease at the 820 gf plateau)

## 6. Uncertainty report and separation

| Type | Covered by | Status |
| --- | --- | --- |
| Parameter | Monte Carlo UQ (capacity ±10 %, R ±50 %, thrust ±3 %, motor mass ±2 %) | quantified |
| Measurement | dataset source uncertainty ±3 % declared; UIUC comparison error quantified | partially quantified |
| Numerical | convergence studies bound integrator error ≪ model error | quantified (negligible) |
| Model-form | NOT quantified — declared qualitatively (no induced velocity, no C-rate derating, no thermal, constant k) | **gap** |
| Environmental | wind/gust = declared equivalent force; no spectra | **gap** |

Capstone energy accounting (independent recompute): **806.5 Wh** consumed to the warning threshold (17.04 Ah at 7.74C, sag 3.07 V) — 83% of the pack's nominal energy. NOT MODELED effects quantified with declared assumptions: C-rate capacity derating and thermal R growth make the modeled 360 s endurance optimistic by ~10–20 % (realistic ≈ 300 s).

## 7. Capstone audit (independent recompute)

- AUW 60.000 kg (60 ± 0.05 ✓); CoG (-0.000, +0.000, +0.073) m
- tip clearance 0.088 m ✓; hover 98.1 N/rotor at 80.9 % throttle (82 % = thin thrust margin, T/W 1.44)
- hover current 170.38 A (7.74C, within the 25C rating); sag 3.07 V
- structural margin at MAX thrust 2.63 — depends on the ±20 % handbook yield band and declared tube geometry
- single-motor failure at hover: NOT recoverable (named attitude-loss abort) — recorded honestly in M8 and re-verified here

## 8. Unsupported assumptions (explicit list)

- Motor thrust: NOT VALIDATED for generalization
- Propeller torque / reaction torque: APPROXIMATE / ASSUMED (constant-k away from hover)
- ESC behavior: APPROXIMATE / ASSUMED
- Battery discharge and voltage sag: APPROXIMATE / ASSUMED
- Rotor-to-rotor interaction: NOT VALIDATED
- Ground effect: NOT VALIDATED
- Aerodynamic drag (airframe): APPROXIMATE / ASSUMED
- Wind and gusts: APPROXIMATE / ASSUMED
- Flight control: NOT VALIDATED (physical flight)
- Sensor noise and latency: APPROXIMATE / ASSUMED
- Structural loads: APPROXIMATE / ASSUMED (inputs)
- Thermal limits: NOT VALIDATED (thermal physics)
- Flight endurance: NOT VALIDATED (endurance vs measurement)

## 9. Prioritized validation-gap backlog

1. **Pack discharge measurement** (highest leverage): measured V/I vs SOC for the actual 12S pack at the 7.7 C hover rate — resolves the dominant endurance uncertainty (R ±50 %) and the unmodeled C-rate derating.
2. **Held-out motor/prop static bench** at a second voltage plane and at thrust points between published knots — converts propulsion from calibrated to independently validated.
3. **Real flight-controller telemetry** (log altitude/attitude/current during a scripted hover-climb-land) — validates the control-loop and drag models.
4. **Blade-element/induced-velocity model upgrade** — needed for thrust generalization beyond measured tables and for climb-power realism (the current model under-predicts climb power: no axial-flow derating).
5. **Thermal model** for motor/ESC/pack (the datasheet rule is a threshold, not physics).
6. **Rotor-interaction and ground-effect models** before any tight-layout or low-hover verdicts.
7. **Material coupon tests** for the frame tube (±20 % yield band).
8. **Measured sensor-noise/bias/latency characterization** for the actual autopilot stack.

## 10. Final credibility verdicts

**Answer to the acceptance question** — the physical engineering decisions AeroForge can currently support with independently validated evidence:

1. **First-order hover/shaft power estimation (±15 % MAPE) for small APC-class propellers in the UIUC test regime** — validated against independent wind-tunnel measurements with a literature FM prior.
2. **Rigid-body response under applied forces and defined gravity** — validated to numerical precision against 300-years-validated physics and the defined standard gravity.
3. **Mass/CoG/inertia bookkeeping** — exact mathematical identities over design data of known provenance.

Everything else — thrust beyond table interpolation, battery endurance for specific packs, flight-control transfer to real hardware, structural margins against real coupons, wind response — is **PROMISING with named, prioritized evidence gaps**, not validated. In particular: the 60 kg capstone is a **simulated feasibility study** (hover/climb/land/gust behavior consistent within the model), NOT a flight-worthiness or human-carrying claim; its endurance is optimistic by ~10–20 % once unmodeled battery effects are accounted for.

No result was manufactured: two audit-script bugs, one sensor-path bug, one controller-scaling gap and two recording refinements were found BY the audit and fixed WITH regression tests after the as-found results were recorded.