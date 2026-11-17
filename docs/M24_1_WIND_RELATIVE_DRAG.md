# M24.1 — Explicit air-relative drag and fail-closed thrust input

**Software scope only.** The aircraft's quadratic equivalent-area airframe drag
is now evaluated from velocity relative to **a specified uniform world-frame
wind vector**, rather than automatically using ground velocity. Supplying no
wind preserves earlier zero-wind simulation behavior. This is a first physics
increment towards M24, **not completion of advanced aerodynamics** or
physical verification.

## Governing approximation

For aircraft world velocity \(v\), uniform ambient air world velocity
\(w\), air density \(\rho\) and equivalent drag area \(C_d A\):

\[
F_{d,W} = -\frac{1}{2}\rho C_d A\lVert v-w\rVert (v-w).
\]

Drag force is transformed from world to body using the existing rigid-body
attitude quaternion. Explicit zero wind is identical to omitted wind.

### Implementation

- `AirframeDrag.force_world(velocity_world, wind_world=None)` accepts only
  shape-(3,) finite velocity vectors, rejects numeric overflow, and preserves
  backwards compatibility for callers with one argument.
- `MultirotorPlant(..., wind_world=optional_world_vector)` injects this
  relative airframe drag into the existing 6-DOF force calculation, but
  does not modify motor, rotor thrust, ESC currents or control laws.
- Nonfinite thrust commands are rejected before flight dynamics. Negative
  rotor thrust continues to fail closed.
- Tests verify zero relative wind = zero drag, correct headwind direction,
  Galilean frame-shift invariance, explicit wind in plant force balance,
  invalid vectors and nonfinite thrust rejection.

## What this does NOT establish

- No rotor wake, blade-element/momentum inflow, advance-ratio effect,
  ground effect, multirotor interference, dynamic pressure gradient,
  gust/turbulence spectrum, attitude-dependent CdA, or aeroelasticity.
- The wind field is uniform and prescribed, without measured clock time,
  shear, stochastic uncertainty or fluid/structure coupling.
- A sourced CdA is still required by the existing design; this milestone
  does not invent or independently validate actual airframe CdA.
- No independent actual-aircraft wind-tunnel or flight test was conducted.
- **No complete-drone real-world prediction equivalence, safety certificate
  or manufacturing probability follows from these analytical tests.**

M24 remains open until independently measured wind/propeller/inflow
and environmental experiments are obtained, the numerical solver and
model-form discrepancy are tested, and all critical resulting predictions
meet preregistered uncertainty/error limits. The primary physical blocker
remains [issue #16](https://github.com/god88844-hub/aeroforge/issues/16).

## Verification

```bash
python -m pytest tests/physics/test_wind_relative_drag.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```
