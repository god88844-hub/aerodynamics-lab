# AeroForge Architecture

AeroForge is a modular digital-twin laboratory for multi-rotor drones. It has
four core parts, mirroring the platform specification:

## 1. Component Evidence Database

Every part (motors, ESCs, batteries, propellers, frames, sensors, flight
controllers) has an entry in `data/components/**` with physical and
performance data **and uncertainty**, each datum tagged with `source` and
`uncertainty`. Geometry, mass, inertia, material properties, manufacturer test
curves (thrust vs RPM, current vs torque, discharge vs time), sensor noise
specs, and known failure modes are recorded. If a key parameter is unknown,
the system either forbids the design or requires a user-provided estimate
with a large explicit uncertainty — it never invents numbers silently.

`data/components/materials.json` seeds the structural material properties.

## 2. Simulation Engine (6-DOF Physics)

Located in `packages/physics/`:

- `dynamics/` — Newton–Euler equations (ΣF = m·dv/dt, ΣM = I·dω/dt) with
  quaternion attitude; mass/CoG/inertia assembled from parts via the parallel
  axis theorem.
- `aerodynamics/` — airframe drag, induced velocity, ground effect (only
  validated models, labeled by fidelity).
- `propulsion/` — propeller thrust/torque maps (interpolated from measured
  tables, blade-element refinement as needed), motor electrical and thermal
  models, ESC limits, battery pack OCV/SOC + internal resistance.
- `structures/` — frame stress checks; component limit monitors.
- `integration/` — explicit RK4 fallback + `scipy.integrate` ODE solvers;
  convergence-tested on known cases (free fall, hover equilibrium).
- `validation/` — benchmarks, uncertainty propagation, credibility scoring.

The engine also simulates the flight control loop: sensor sampling with noise
and delay, PID (later MPC) control laws, actuator saturation — so stability
issues such as delay-induced oscillation are captured, not hidden.

## 3. Validation & Uncertainty Module

For each scenario, results are compared against a curated benchmark suite
(static thrust test, throttle step response, hover, glider drop, battery
discharge). Every simulation reports:

1. the predicted outcome (best estimate),
2. quantified uncertainty (Monte Carlo over parameter tolerances, or analytic
   sensitivity where feasible),
3. a credibility rating based on the evidence behind each submodel,
4. explicit assumptions/caveats, including whether the scenario lies inside
   the validated operating domain.

If a requirement falls outside the uncertainty bound, the verdict is
`FAIL` or `INCONCLUSIVE` / `NEEDS FURTHER VALIDATION` — never a false pass.

## 4. User Interface & Data Flow

React + Three.js editor (`apps/web`) for assembling drones from components;
all units SI. The editor shows center of gravity and principal axes. Saving a
design snapshots the full configuration (geometry, parts with data, control
settings, environment). Running a simulation posts that exact snapshot to the
API (`apps/api`, FastAPI), which executes the physics engine and returns time
series plus a structured report: **Design** (masses, CoG, inertia,
propulsion), **Simulation** settings, **Results** (performance vs specs), and
**Trustworthiness** (validation status per submodel, uncertainty, confidence).

## Extensibility

New vehicle classes (fixed wing, VTOL) and physics (aeroelastic wings) are
added as plugins using the same component schema. v1 scope is multi-rotor
only; the quadcopter domain is fully validated before any expansion.
