# M9 Phase 2/9 — Evidence inventory and credibility verdicts

Credibility counts: {'PROMISING_FURTHER_EVIDENCE_REQUIRED': 16, 'VALIDATED_FOR_THIS_DECISION': 1}

## Rigid-body dynamics (6-DOF)
- model: packages/physics/dynamics/rigid_body.py + quadrotor.py (M1)
- governing equations: Newton–Euler: F = m·a, τ = I·ω̇ + ω×(Iω); quaternion attitude kinematics
- parameter class: sourced (g: defined constant; mass/inertia: design data)
- verification: free fall v(1 s) = g ± 1e-6; principal-axis spin-up ω = τ/I·t; torque-free conservation of energy and |L_world| < 1e-8; RK4 order-4 step-halving; scipy agreement (tests/physics/test_rigid_body.py)
- calibration data: none required (structural equations + defined constants)
- independent validation data: verification evidence only: analytical identities and the DEFINED standard gravity. Independent PHYSICAL validation of an assembled aircraft (measured trajectories) does not exist yet — M9 rev 2 reclassified this from 'independently validated' per external review
- prediction errors: free fall ±1e-6 m/s (spec gate ±0.01)
- uncertainty: numerical: bounded by convergence studies; model-form: flat non-rotating Earth, constant g, rigid body — declared
- validated envelope: flat non-rotating Earth, |v| < ~30 m/s, near-Earth altitudes
- limitations: no Coriolis/centrifugal; constant g; no structural flexure; no aerodynamic coupling inside the core
- consequences if wrong: dynamics errors would corrupt every trajectory prediction
- **evidence categories**: VERIFIED IMPLEMENTATION
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Mass and inertia assembly
- model: packages/physics/dynamics/mass_properties.py; geometry/primitives.py
- governing equations: parallel-axis theorem; solid-box/cylinder inertia formulas
- parameter class: mixed: sourced masses + estimated masses
- verification: two-point dumbbell, box formula, multi-part transfer vs hand computation (tests/physics/test_mass_properties.py)
- calibration data: none (mathematical identities)
- independent validation data: verification evidence only: mathematical identities. Physical validation requires a measured real assembly (weighed vehicle, measured inertia) — M9 rev 2 reclassified from 'independently validated'
- prediction errors: exact to float precision
- uncertainty: driven entirely by part-mass data quality (flagged per part)
- validated envelope: rigid assemblies in the design snapshot
- limitations: assembly is rigid; no fuel burn; inertia of irregular parts must be supplied (point-mass fallback)
- consequences if wrong: wrong inertia → wrong attitude dynamics; wrong mass → wrong thrust margins and endurance
- **evidence categories**: VERIFIED IMPLEMENTATION
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Motor thrust
- model: packages/physics/propulsion/dataset.py — PCHIP interpolation of manufacturer bench tables (MN3508: 2 voltage planes; P80 III: 1 plane, 21 rows)
- governing equations: monotone PCHIP through measured (rpm, thrust) knots; NO physics-based generalization (no blade-element model)
- parameter class: sourced (measured manufacturer bench data)
- verification: knot read-back exact (M2/M9 benchmarks); monotonicity per plane
- calibration data: the manufacturer tables ARE the model (interpolation of calibration data)
- independent validation data: NONE for thrust generalization: reproducing table knots is calibration, not validation; no held-out measurements exist for these motor+prop pairs
- prediction errors: None
- uncertainty: dataset uncertainty ±3 % (source-stated); interpolation between knots unquantified
- validated envelope: MN3508: 2600–5900 rpm, planes 14.8/22.2 V ±15 %; P80 III: 1719–3747 rpm, plane 47.9 V ±15 %; thrust within [table min, max]
- limitations: no advance ratio / forward flight; no prop-on-prop or wall effects; single-plane datasets rely on flagged voltage extrapolation; flat-thrust region (820 gf) makes rpm inversion ill-conditioned
- consequences if wrong: thrust overestimate → unrealistic performance verdicts; underestimate → false infeasibility
- **evidence categories**: VERIFIED IMPLEMENTATION, CALIBRATED TO MEASUREMENTS, NOT VALIDATED for generalization
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Propeller torque / reaction torque
- model: constant k = Q/T per design (rotor_torque_per_thrust); k sourced from the P80 bench torque column at hover (0.0224 N·m/N); MN3508 k=0 in the reference design (manufacturer published no torque column)
- governing equations: τ_z = −Σ spin_i · k · T_i
- parameter class: sourced for P80 (single-point at hover); unknown for MN3508
- verification: mixer wrench reconstruction tests
- calibration data: P80: k at the hover thrust point (single point, not the full curve)
- independent validation data: the k value comes from the manufacturer bench data (calibration data for our own use) — no independent torque measurements
- prediction errors: None
- uncertainty: ±(variation across the table) — not sampled in UQ
- validated envelope: near-hover thrust ratios
- limitations: constant k (true k grows with thrust); no gyroscopic precession moments
- consequences if wrong: wrong yaw authority → yaw control divergence in flight
- **evidence categories**: CALIBRATED TO MEASUREMENTS (single point), APPROXIMATE / ASSUMED (constant-k away from hover)
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Motor electrical power / current
- model: P = V·I identity + per-plane PCHIP current(rpm) with fitted voltage-slope correction and power-based floor (declared extrapolation)
- governing equations: P_elec = V_bus·I; current(rpm, V) interpolated between measured planes
- parameter class: sourced (measured) + declared extrapolation policy
- verification: C1 identity to publication rounding (≤0.5 %); plane normalization ≤2 %
- calibration data: manufacturer tables (calibration data)
- independent validation data: momentum-theory electrical-power prediction vs P80 bench: MAPE 4.46 %, 100 % within ±15 % (WEAK-FORM — priors literature-informed); vs UIUC wind-tunnel power: MAPE 6.4 % (BLIND, genuinely independent)
- prediction errors: None
- uncertainty: thrust/eta prior bands declared in the blind comparisons
- validated envelope: static conditions; voltages within ±15 % of measured planes; rpm within table
- limitations: lumped DC model does NOT close (35 % residual — documented finding); no inductance/timing model; single-plane datasets need flagged extrapolation
- consequences if wrong: current/power error → wrong endurance, wrong thermal margins
- **evidence categories**: VERIFIED IMPLEMENTATION, CALIBRATED TO MEASUREMENTS, INDEPENDENTLY VALIDATED (momentum-theory power path vs UIUC wind-tunnel data, MAPE 6.4 % < 15 % declared — validates the estimation METHOD for this prop class, not an assembled drone)
- **CREDIBILITY: VALIDATED_FOR_THIS_DECISION** — independent physical evidence within pre-declared tolerance, no relevant unmodeled mechanisms

## ESC behavior
- model: static current/voltage limit checks only (packages/physics/propulsion/esc.py)
- governing equations: none (limit comparisons)
- parameter class: assumed
- verification: unit tests of limit checks
- calibration data: none
- independent validation data: none
- prediction errors: None
- uncertainty: rating uncertainty ±20 % flagged
- validated envelope: steady current/voltage limits only
- limitations: no PWM dynamics; no switching losses; no thermal model; no timing/advance effects (the 35 % lumped-DC residual lives here)
- consequences if wrong: ESC behavior errors distort the motor electrical chain
- **evidence categories**: APPROXIMATE / ASSUMED, NOT VALIDATED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Battery discharge and voltage sag
- model: OCV(SOC) PCHIP (community-sourced curve) + single pack R (constant) + coulomb counting (packages/physics/propulsion/battery.py)
- governing equations: V_load = OCV(SOC) − I·R_pack; dSOC = −100·I·dt/(3600·C)
- parameter class: mixed: OCV shape sourced (community), R/capacity estimated
- verification: OCV read-back, sag arithmetic, coulomb counting (unit tests)
- calibration data: OCV curve itself came from community measurements (calibration data for the curve; not independent)
- independent validation data: NONE for our specific packs — no measured discharge of the modeled packs
- prediction errors: None
- uncertainty: capacity ±10 %, R ±50 % sampled in UQ; dominant endurance sensitivity
- validated envelope: steady discharge, < ~8 C in the audited designs
- limitations: no temperature dependence; no C-rate capacity derating; no cycle aging; no cell imbalance; constant R
- consequences if wrong: endurance estimates optimistic (audit: ~10-20 % once derating/thermal are accounted); sag errors → premature/late warnings
- **evidence categories**: APPROXIMATE / ASSUMED, NOT VALIDATED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Rotor-to-rotor interaction
- model: NOT IMPLEMENTED
- governing equations: —
- parameter class: —
- verification: —
- calibration data: —
- independent validation data: —
- prediction errors: None
- uncertainty: —
- validated envelope: —
- limitations: hover/flight of multi-rotor layouts carries unquantified interference thrust/power penalties
- consequences if wrong: hexa/octa endurance and hover thrust overestimated (typically low-single-digit % at large spacing, larger when discs overlap)
- **evidence categories**: NOT VALIDATED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Ground effect
- model: NOT IMPLEMENTED
- governing equations: —
- parameter class: —
- verification: —
- calibration data: —
- independent validation data: —
- prediction errors: None
- uncertainty: —
- validated envelope: takeoff/landing within ~1 rotor diameter of the ground
- limitations: takeoff/landing thrust and power near the ground are wrong by the classic ground-effect factor (up to ~10-20 % at half-rotor height)
- consequences if wrong: landing/takeoff power needs misestimated
- **evidence categories**: NOT VALIDATED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Aerodynamic drag (airframe)
- model: quadratic drag with single equivalent CdA (packages/physics/aerodynamics/drag.py)
- governing equations: F = −0.5·ρ·CdA·|v|·v
- parameter class: assumed (CdA)
- verification: force formula unit-tested
- calibration data: none
- independent validation data: none
- prediction errors: None
- uncertainty: CdA dominates; hover/vertical phases barely affected (v≈0)
- validated envelope: incompressible, constant density, no AOA dependence
- limitations: no angle-of-attack dependence; no interference drag; constant density with altitude
- consequences if wrong: forward-flight speed/power predictions unreliable
- **evidence categories**: APPROXIMATE / ASSUMED, NOT VALIDATED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Wind and gusts
- model: equivalent constant lateral FORCE over a time window (capstone: 8 m/s on assumed 0.8 m² area ≈ 39 N)
- governing equations: step force input
- parameter class: assumed
- verification: scenario tests assert rejection/offset behavior
- calibration data: none
- independent validation data: none
- prediction errors: None
- uncertainty: frontal area and gust profile assumed
- validated envelope: none — the force profile is not a validated wind model
- limitations: no turbulence spectrum; no directionality; no aeroelastic coupling
- consequences if wrong: gust-rejection verdicts do not transfer to real wind events
- **evidence categories**: APPROXIMATE / ASSUMED, NOT VALIDATED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Flight control
- model: cascaded PID (position→attitude→rate→mixer) with inertia-derived gains, slew-limited feedforward, derivative filtering, anti-windup
- governing equations: standard cascade PID; quaternion attitude; wrench mixer (least squares)
- parameter class: derived (gains) + architecture assumption
- verification: hover hold, altitude step, disturbance rejection, 5° roll within ±0.1°, yaw hold, mixer wrench reconstruction, saturation flags (tests)
- calibration data: none
- independent validation data: NO flight-log validation: no real flight controller telemetry has been compared against these loops
- prediction errors: None
- uncertainty: perfect state knowledge in audited runs; noise/latency modeled but not measured; sensor bias modeled (M9)
- validated envelope: near-hover regimes in simulation; deterministic
- limitations: no actuator dynamics/lag; no real sensor stack; no wind; torque authority now inertia-scaled (M9 finding F4)
- consequences if wrong: control verdicts do not transfer to real flight controllers
- **evidence categories**: VERIFIED IMPLEMENTATION (software behavior), NOT VALIDATED (physical flight)
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Sensor noise and latency
- model: Gaussian noise + zero-order-hold latency + constant bias (packages/physics/controller/sensors.py)
- governing equations: additive noise per channel; small-angle quaternion noise
- parameter class: assumed
- verification: bias application verified (M9 regression), noise determinism
- calibration data: none
- independent validation data: none
- prediction errors: None
- uncertainty: declared bands only
- validated envelope: whatever sigmas are declared
- limitations: no scale-factor errors; no vibration spectra; no dropouts; no EKF/state-estimator modeling
- consequences if wrong: real sensor stacks may behave worse than modeled
- **evidence categories**: APPROXIMATE / ASSUMED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Structural loads
- model: cantilever bending of circular tube arms: σ = M·c/I, M = F·L (packages/physics/structures/beam.py)
- governing equations: Euler–Bernoulli bending at the root
- parameter class: mixed: sourced material bands + declared geometry
- verification: bending stress vs hand calculation (M9/M4 tests)
- calibration data: none
- independent validation data: none — no coupon tests, no load-cell measurements
- prediction errors: None
- uncertainty: material ±20 %; geometry as declared
- validated envelope: static bending at the arm root
- limitations: bending only: no torsion/joints/buckling/fatigue/vibration; worst-case single-arm load
- consequences if wrong: structural margin could be substantially wrong
- **evidence categories**: VERIFIED IMPLEMENTATION (formula), APPROXIMATE / ASSUMED (inputs), NOT VALIDATED
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Thermal limits
- model: datasheet current/duration rule (I > I_max sustained beyond rated duration → burnout; I > 2×I_max → instantaneous) — NO thermal integration
- governing equations: threshold rule
- parameter class: sourced (rule), no thermal physics
- verification: failure-detection tests (overcurrent, burnout paths)
- calibration data: rule taken directly from datasheets
- independent validation data: none
- prediction errors: None
- uncertainty: no winding-temperature state exists in the model
- validated envelope: static current/duration margin checks
- limitations: no temperature state; no cooling curves; no ESC heating
- consequences if wrong: real motors may burn out earlier or later than modeled
- **evidence categories**: CALIBRATED TO MEASUREMENTS (rule from datasheet), NOT VALIDATED (thermal physics)
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Failure detection
- model: declared critical/warning policy over powertrain, structure, ground, attitude, thrust-envelope monitors (packages/physics/scenarios/runner.py)
- governing equations: threshold monitors + named aborts
- parameter class: sourced limits + declared policy
- verification: motor failure, depleted battery, over-speed, structural overload tests; bias/latency interaction tests (M9)
- calibration data: n/a
- independent validation data: verification evidence only: software behavior tested in simulation. Hardware-in-the-loop or real-failure validation does not exist — M9 rev 2 reclassified from 'independently validated'
- prediction errors: None
- uncertainty: —
- validated envelope: simulated telemetry only
- limitations: detects only the modeled mechanisms (audit lists unmodeled ones); no hardware-in-the-loop
- consequences if wrong: undetected real-world failure modes remain possible
- **evidence categories**: VERIFIED IMPLEMENTATION
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet

## Flight endurance
- model: static-hover coulomb drain to the 3.5 V/cell warning through the sourced powertrain chain
- governing equations: coulomb counting + sag + OCV
- parameter class: mixed
- verification: M2/M9 tests; deterministic replay
- calibration data: the current chain is calibrated to bench data; the pack is not
- independent validation data: NO measured endurance of any real aircraft
- prediction errors: None
- uncertainty: dominated by battery estimates (capacity/R); no C-rate derating modeled
- validated envelope: static hover, < 8 C discharge, no temperature effects
- limitations: no temperature; no derating; no real-flight power transients
- consequences if wrong: mission-endurance decisions unreliable until pack data exists
- **evidence categories**: CALIBRATED TO MEASUREMENTS (current chain), NOT VALIDATED (endurance vs measurement)
- **CREDIBILITY: PROMISING_FURTHER_EVIDENCE_REQUIRED** — functions and is verified in software, but no independent physical validation evidence exists yet
