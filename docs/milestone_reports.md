# AeroForge Milestone Reports

Running changelog per the build specification's "Reporting Progress" section:
after each milestone — what was implemented and tested, new files/modules,
commands used, test results, remaining known issues and next steps.

---

## Milestone 0 — Environment Setup (done)

**Implemented**
- Monorepo scaffold with the exact required tree (`apps/web`, `apps/api`,
  `packages/{physics,geometry,shared-schemas,optimization}`, `data/**`,
  `scripts/`, `tests/{physics,integration,regression,e2e}`, `docs/`).
- FastAPI app (`apps/api`) with `/api/health` route skeleton.
- React 19 + TypeScript + Vite 7 app shell (`apps/web`) that calls the API
  health endpoint; deps installed for the full stack (three.js/R3F/drei,
  zustand, TanStack Query, recharts, vitest, testing-library).
- Sourced materials database (`data/components/materials.json`) — Al 6061-T6,
  quasi-isotropic CFRP, PA12, PLA, each with density/stiffness/strength,
  source, and uncertainty.
- Docs set (architecture, validation strategy, dev guide, user manual stub),
  GitHub Actions CI, Dockerfiles + docker-compose, `.gitignore`, root
  `pyproject.toml` (pytest `pythonpath`).

**Verified**
- `python -m pytest` — 3 passed (package importability smoke tests).
- `python -m uvicorn app.main:app` from `apps/api` → `/api/health` returns
  `{"status": "ok", "service": "aeroforge-api", "version": "0.1.0"}`.
- `npm run build` (tsc --noEmit + vite build) — clean.
- `vite` dev server — HTTP 200.

**Deviations / notes**
- Workspace folder was read-only (ACL); write access granted to the account
  via user-approved elevated `icacls`; repo lives at the workspace root.
- `packages/shared-schemas` contains package `aeroforge_schemas` (module names
  cannot contain `-`).
- Tailwind lands with the M5 editor; SQLAlchemy/Alembic env initialized with
  design persistence (M5). Both pinned/available already.

---

---

## Milestone 1 — 6-DOF Dynamics & Component Models (done)

**Implemented**
- `packages/physics/constants.py` — sourced constants (g = 9.80665 m/s² BIPM;
  ρ_sea = 1.225 kg/m³ ISA). No magic numbers elsewhere.
- `packages/physics/dynamics/quaternion.py` — [w,x,y,z] unit quaternions,
  Hamilton product, rotate/rotate_inverse, axis-angle, rotation matrix,
  kinematics derivative dq/dt = ½ q⊗(0,ω).
- `packages/physics/dynamics/mass_properties.py` — Part/MassProperties,
  parallel-axis assembly of mass/CoG/inertia; fail-closed validation
  (negative eigenvalues rejected; triangle inequality on principal moments
  enforced; zero eigenvalues allowed for idealized assemblies). RigidBody
  additionally requires strict positive definiteness (it must invert I).
- `packages/physics/dynamics/rigid_body.py` — 13-state Newton–Euler with
  gravity (world +z up, flat non-rotating Earth assumption documented).
- `packages/physics/dynamics/quadrotor.py` — MultirotorPlant: per-rotor thrust
  → net body force/torque (thrust along body +z at CoG-relative positions;
  reaction torque −spin·k·t with k=0 default until the M2 propulsion DB;
  explicit list of NOT-yet-modeled effects in the module docstring);
  `hover_trim()` least-squares static trim (ΣF=0, Στ=0) — fail-closed when
  the layout cannot be trimmed (e.g. all-same-spin props with k>0).
- `packages/physics/aerodynamics/drag.py` — first-order CdA model, labeled
  approximation with explicit validity limits.
- `packages/physics/integration/rk4.py` (fixed-step fallback/reference) and
  `scipy_solver.py` (adaptive RK45, tolerances recorded for M7 convergence).
- `packages/geometry/primitives.py` — box/cylinder/point inertia formulas.
- `packages/shared-schemas/aeroforge_schemas/design.py` — design snapshot
  schema v0.1 (parts w/ mass+inertia, rotor placements, drag CdA, notes);
  `data/designs/quad_example_2kg.json` — labeled synthetic verification quad.
- `packages/physics/dynamics/design_adapter.py` — snapshot → physics objects
  (rotor positions re-expressed CoG-relative).
- `scripts/run_simulation.py` — full M1 flow: validate snapshot → assemble
  mass properties → analytic hover trim → integrate hover scenario → printed
  engineering report with Design/Trim/Scenario/Results/Trustworthiness
  (actuator model explicitly flagged as idealized placeholder; verdict is
  "dynamics verification only — not a flight-worthiness claim").

**Verified** (`python -m pytest` → **42 passed**)
- Quaternions: 90° rotation composition, inverse identity, matrix agreement,
  constant-spin integration to the expected angle.
- Mass properties: two-point dumbbell (CoG/Iyy/Izz hand values), box inertia
  formula, multi-part parallel-axis transfer vs hand computation, triangle-
  inequality and negative-eigenvalue rejection, symmetric-tensor enforcement.
- Rigid body: free fall v(1 s) = 9.80665 ± 1e-6 (spec gate ±0.01 exceeded),
  principal-axis spin-up ω = τ/I·t, torque-free conservation of energy and
  |L_world| < 1e-8 drift over 5 s of tumbling, RK4 order-4 step-halving on
  nonlinear dynamics, scipy solver agreement.
- Integration: RK4 exactness for constant acceleration, endpoint landing,
  order-4 convergence on x' = −x, scipy/RK4 agreement.
- Hover (M1 acceptance): trim = m·g/4 per rotor exactly; 2 s hover → drift
  < 1e-6 m, max |net accel| < 1e-9 m/s² (net force ≈ 0); +0.3 kg payload →
  trim 2.3·g; −battery → 1.6·g; CoG-offset design → unequal trim thrusts
  still exactly stationary; all-same-spin props with reaction torque → trim
  refused (fail-closed); negative thrust and wrong-length thrust vectors
  rejected.
- `scripts/run_simulation.py data/designs/quad_example_2kg.json` (RK4 and
  scipy) — report prints as specified above.

**Commands**
- `python -m pytest` (repo root) — 42 passed.
- `python scripts/run_simulation.py data/designs/quad_example_2kg.json [--solver ivp]`.

**Known issues / next steps**
- Actuator model is ideal (documented); M2 replaces it with sourced
  motor/prop/ESC/battery data and interpolation benchmarks (<0.5 % gate).
- Rotor reaction torque uses a uniform k until per-component data lands.
- No wind/turbulence model yet (M4); no sensor/controller loop yet (M3).

---

## Milestone 2 — Static Propulsion Models (done)

**Implemented**
- **Sourced component database** (transcribed from the manufacturer test
  report, every datum carrying source + uncertainty):
  - `data/components/motors/tmotor_mn3508_kv380.json` — T-Motor MN3508 KV380:
    specs (205 mΩ, idle 0.4 A @ 10 V, 14 A / 310 W @ 180 s, 103 g, 12N14P,
    3–6S) plus the full load-test table for T-MOTOR 15*5CF at **14.8 V and
    22.2 V** and 14*4.8CF at 22.2 V (throttle / current / power / thrust / RPM
    per row; every row verified internally consistent: thrust ÷ power equals
    the published efficiency). Source: T-Motor test report MN.00011
    (modelavia.pro PDF mirror of the datasheet), retrieved 2026-11-15.
  - `data/components/propellers/tmotor_p15x5_cf.json` — geometry sourced;
    **mass flagged estimated** (±30 %) until measured.
  - `data/components/batteries/generic_6s_lipo_16000mah.json` — OCV-SOC curve
    sourced from community-measured LiPo charts; capacity/mass/IR flagged
    estimated with wide uncertainty.
  - `data/components/controllers/generic_esc_20a.json` — placeholder rating,
    flagged estimated.
- **Schemas** (`aeroforge_schemas/component.py`): MotorSpec / PropellerSpec /
  BatterySpec / EscSpec / SourceInfo / TestDataPoint; `DroneDesign` extended
  with an optional `powertrain` block (additive, schema-compatible).
- **Propulsion models** (`packages/physics/propulsion/`):
  - `dataset.py` — *model of record*: monotone PCHIP interpolation of the
    measured table. Thrust(rpm) merged across voltage planes (static thrust is
    rpm-driven; cross-plane scatter 3.9 % recorded as dataset scatter).
    Current(rpm, V): per-plane PCHIP; linear-in-voltage between planes;
    fitted-slope correction beyond the outer planes (flagged); ±15 % voltage
    excursion hard limit; throttle↔rpm mappings implemented as exact inverses
    of each other (composite inversion); **thrust is never extrapolated** —
    out-of-envelope queries raise `OutOfEnvelopeError`.
  - `battery.py` — OCV(SOC) + pack-R sag + coulomb counting; fail-closed when
    internal resistance unknown; warning (3.5 V/cell) / cutoff (3.3 V/cell).
  - `esc.py` — current/voltage limit checks. `powertrain.py` — N-unit static
    powertrain: bus-voltage fixed-point solve, thrust→throttle inverse,
    `static_hover` endurance sim (thrust re-trimmed to m·g each step),
    ESC/motor limit monitoring, envelope-flag collection.
  - `loader.py` — `ComponentLibrary` with schema validation on load.
- **Validation framework** (`packages/physics/validation/benchmarks.py`) —
  pre-registered tolerances, pass/fail vs informational "reported" status.
- **CLI** (`scripts/run_simulation.py`) — `--scenario {auto, hover-ideal,
  hover-static}`; the static report includes benchmark table, hover point
  with envelope flags, endurance, limit issues, and a trustworthiness section
  (provenance, estimated components, battery caveat, static-only caveat).
- Design snapshot `data/designs/quad_mn3508_6s.json` — 3.708 kg quad on 4×
  MN3508+15×5CF+6S16Ah with battery-mass consistency cross-check.

**Key V&V finding (documented, not hidden):** a lumped DC motor model using
the datasheet Kv and winding resistance does **not** reproduce the loaded
bench points (calibrated on 14.8 V, validated on 22.2 V: current RMSE 2.13 A,
max error 35 %) — BLDC+ESC inductance/timing effects dominate. The measured
table is therefore the model of record; the lumped model is a reported
cross-check benchmark only.

**Verified** (`python -m pytest` → **66 passed**; 24 new)
- Knot read-back within 5e-15 % (gate 0.5 %) at all 20 points; full-throttle
  chain reproduces the 22.2 V table row exactly; cross-voltage scatter 3.89 %
  (gate 5 %).
- Envelope enforcement: rpm/throttle/voltage excursions refused or flagged
  (never silently extrapolated); single-plane dataset refuses foreign voltage.
- Battery: OCV read-back, sag arithmetic, coulomb counting, warning/cutoff
  states, fail-closed on unknown IR.
- Static hover (3.708 kg): thrust held at m·g (rel. err < 1e-4); 4091 rpm,
  2.91 A/rotor, 291 W total (78 W/kg), 64.3 min to the 3.5 V/cell warning;
  over-load (100 N) and depleted-battery starts fail closed; ESC over-current
  detection works.
- Full suite (M0+M1+M2) green; both CLI scenarios produce full reports.

**Commands**
- `python -m pytest`
- `python scripts/run_simulation.py data/designs/quad_mn3508_6s.json --duration 7200 --dt 10`
- `python scripts/run_simulation.py data/designs/quad_example_2kg.json --scenario hover-ideal`

**Known issues / next steps**
- Prop mass, ESC rating, battery capacity/mass/IR are flagged estimates —
  replace with measured data before trusting endurance numbers.
- Hover operating point sits below the lowest measured throttle knot (45.7 %
  vs 50 %) and above the 22.2 V plane (full-charge 6S) — both are flagged
  extrapolations; a second bench voltage (e.g. 18.5 V) would tighten them.
- No thermal model, no motor dynamics/lag, no forward-flight advance ratio
  (M3/M4 scope).

---


Running changelog per the build specification's "Reporting Progress" section:
after each milestone — what was implemented and tested, new files/modules,
commands used, test results, remaining known issues and next steps.

---

---

## Milestone 3 — Flight Controller and Stability (done)

**Implemented**
- `packages/physics/controller/pid.py` — discrete PID with derivative-on-
  measurement and **integral-tracking anti-windup** (when the output
  saturates, the integral is held at the value that produces the saturated
  output — no stored windup, instant recovery on error reversal).
- `packages/physics/controller/mixer.py` — geometry-aware wrench mixer:
  [total thrust, tx, ty, tz] -> per-rotor thrusts via the plant's A matrix
  (same equations as hover_trim); iterative negative-clip re-solve, optional
  per-rotor thrust ceiling (from the sourced dataset when attached), and
  status flags (clipped_negative / saturated_max / torque_residual).
- `packages/physics/controller/attitude.py` — cascade controller:
  position hold (yaw-compensated, tilt-capped) -> attitude P -> rate PI ->
  mixer; altitude PID with tilt compensation (1/cos(tilt)). Gains derived
  from the assembled mass/inertia (ControlGains.for_plant) — the 2 kg and
  3.7 kg quads both stabilize without hand tuning. Integral authority is
  deliberately zero for altitude with ideal actuators (no bias to integrate;
  any climb-integrated windup cannot unwind quickly) — documented, and
  reserved for the battery-sag bias case (M4), clamped to ±1.5 m/s².
- `packages/physics/controller/simulation.py` — deterministic closed-loop
  harness: fixed control period (default 250 Hz) with RK4 substeps, scheduled
  disturbance forces (world) / torques (body), full telemetry, controller
  reset per run.
- CLI `--scenario hover-hold`: 10 s closed-loop hover with a torque impulse
  (t=4 s) and a force push (t=6 s); reports peak attitude, tail errors,
  oscillation metric, mixer thrust ceiling.

**Verified** (`python -m pytest` → **83 passed**; 17 new)
- PID: P-only offset = kp/(1+kp)·target exactly; integral eliminates steady-
  state error; derivative reduces overshoot >4x on a double integrator;
  anti-windup recovers immediately on error reversal.
- Hover hold (2 kg): 1 m hold, tail error < 5 cm, std < 1 cm, attitude < 1°;
  altitude step reaches target within 5 cm.
- Disturbance rejection: 0.05 N·m roll impulse — visible response (0.4°),
  return to level < 0.5°, altitude hold maintained; 2 N force push —
  excursion then position-hold recovery (< 5 cm, |v| < 5 cm/s).
- **Spec checkpoint (Prompt 5)**: 5° roll command held within ±0.1°
  (measured mean error < 0.05°, std < 0.05°); returns to level within ±0.1°
  when released. Pitch command held symmetrically.
- Yaw hold 30° on the MN3508 design (reaction torque k=0.015 N·m/N derived
  from bench data P/ω, flagged estimate ±30 %).
- Mixer: exact wrench reconstruction at zero saturation; negative-demand
  clipping and max-thrust saturation flagged; gains scale with inertia.

**Commands**
- `python -m pytest`
- `python scripts/run_simulation.py data/designs/quad_mn3508_6s.json --scenario hover-hold`

**Known issues / next steps**
- Perfect state knowledge (no sensor noise/latency) and ideal actuators —
  M4 adds sensor models, delay, and failure detection; powertrain-in-the-loop
  (battery sag feeding the mixer ceiling) is wired in M4 scenarios.
- Hover trim (spec M3 item) is the M1 hover_trim() least-squares solve, now
  also used implicitly through the mixer.

---

## Milestone 4 — Flight Scenarios and Failure Cases (done)

**Implemented**
- `packages/physics/scenarios/runner.py` — scenario framework:
  - piecewise-linear altitude/position profiles **with per-segment velocity
    feedforward** and accel-shaped climb/deceleration segments,
  - `LoopPowertrain`: sourced bench data in the loop — thrust -> rpm -> current
    via the measured table (strict in-envelope path + **declared-extrapolation
    path** for the descent regime below the table minimum: static-scaling rpm
    and power-floored current, flagged per tick), battery SOC drain and bus
    sag per tick, ESC/motor limit checks,
  - failure monitors with a **declared policy** (runner docstring): CRITICAL
    aborts = thrust above measured max (over-speed equivalent), current > 2x
    continuous rating (instantaneous), current > continuous rating sustained
    beyond the datasheet duration (thermal burnout), battery cutoff, ESC
    over-voltage, arm bending at/above yield, hard ground impact, attitude
    loss (>45 deg); warnings logged = battery land-now warning, structural
    margin < 1.5,
  - metrics: time-to-altitude (95% held >= 1 s), energy (Wh), max current,
    final SOC, structural margin, success criteria (pre-registered callables).
- `packages/physics/structures/{materials,beam}.py` — sourced materials DB
  loader + cantilever-tube arm bending check (M = F·L, sigma = M·c/I);
  model limits (no torsion/fatigue/buckling) documented. `DroneDesign`
  extended with an optional `frame` block (fail-closed: declared frame with
  unknown material or missing library refuses to run).
- `packages/physics/controller/sensors.py` — seeded, deterministic sensor
  model: Gaussian noise per channel + zero-order-hold latency.
- Controller fixes found by the scenario tests (all documented in code):
  proper PD altitude structure `a = kp*e + kd*(vz_des - vz) + ki*∫e` (the
  velocity error must NOT go through a derivative channel — sustained
  velocity errors produce zero derivative response), slew-limited (4 m/s²)
  velocity feedforward, derivative low-pass (tau = 50 ms) against sensor
  noise, ground-crash monitor distinguishes hard impact from gentle
  touchdown, PID integral-tracking anti-windup.
- CLI `--scenario flight`: takeoff -> 5 m hold -> land with full metrics.

**Verified** (`python -m pytest` → **94 passed**; 11 new)
- Takeoff-climb (5 m): completes, time-to-5 m = 2.34 s, overshoot 0.34 m,
  energy 1.5 Wh, no critical events, all success criteria PASS.
- Landing: gentle touchdown (|vz| < 1 m/s), settles on ground, no abort.
- Forward flight (5 m at 2 m/s): arrives within 0.3 m and holds.
- **Motor-failure injection** (spec Prompt 6): killing motor 0 at hover
  aborts the run with a named unrecoverable-state event — never silently
  completes.
- Battery depleted (0 % SOC): immediate battery-cutoff abort.
- **Forced over-speed** (spec M4): 25 N/rotor command above the measured
  static max (18.44 N) reported as a critical failure — not silently accepted.
- Structure yield: a 5x4.5 mm tube design fails closed under flight loads
  (STRUCTURAL FAILURE, margin < 1); unknown frame material refuses to run.
- Sensor robustness: 2 cm GNSS noise, 0.5 deg attitude noise, 20 ms latency —
  hover remains stable (after the derivative-filter fix).
- Flight CLI scenario: full mission report with metrics + success table.

**Commands**
- `python -m pytest`
- `python scripts/run_simulation.py data/designs/quad_mn3508_6s.json --scenario flight`

**Known issues / next steps**
- Motor thermal model is the datasheet current/duration rule (no winding
  temperature integration); ESC thermal cutoff is a declared I/t policy.
- Sensor model has no bias/drift/dropouts; bus solve is quasi-static.
- Scenarios defined in code; scenario JSON persistence deferred to the
  API/UI milestone (M5).

---


