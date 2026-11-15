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
