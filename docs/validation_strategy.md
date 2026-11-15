# AeroForge Validation Strategy

This document is the law of the platform: it defines when a simulation result
may be trusted, and what must always be reported alongside it. It follows
ASME V&V 10, NASA-STD-7009 (credibility assessment), and standard aerospace
V&V practice (independent validation data, risk-based maturity models).

## 1. Verification vs Validation

- **Verification** — "do we solve the equations right?" Unit tests against
  analytical solutions (free fall at g = 9.81 m/s², hover thrust = m·g,
  parallel-axis inertia of a known geometry), grid/time-step convergence
  studies, solver order verification.
- **Validation** — "are the equations the right ones for this regime?"
  Comparison against independent physical data **not used for calibration**:
  motor/propeller thrust benches, battery discharge curves, flight logs of
  similar quadcopters. Simulated thrust, current draw, hover power, climb
  rate, and stability response must match measurements within pre-declared
  tolerances before predictions in that regime are labeled credible.

Calibration data and validation data are **never the same dataset**. The
benchmark registry (`packages/validation/`) enforces this split.

## 2. What every result must report (NASA CAS)

1. **Best estimate** — the predicted outcome.
2. **Uncertainty** — prediction intervals from Monte Carlo sampling of
   component tolerances (motor constant, battery resistance, air density,
   sensor noise, controller delay) plus numerical error estimates.
3. **Credibility rating** — evidence-based score per submodel: which parts
   are grounded in measured data, which are physical theory, which are
   labeled approximations, and at what fidelity.
4. **Caveats** — assumptions in force, and whether the operating point lies
   inside the validated envelope. Outside it, the result is reported as
   "model not validated here" — never as success.

If the uncertainty band crosses a requirement's threshold, the verdict is
`INCONCLUSIVE` or `NEEDS FURTHER VALIDATION`, not "safe".

## 3. Component failure = project failure

Every motor, ESC, propeller, battery, frame member, and sensor has documented
limits. During simulation, exceeding any limit (over-current, ESC thermal
cutoff, battery undervoltage, motor thermal limit, structural yield) **fails
the design**. The simulator also catches system-level failure modes that
appear only when parts are integrated: rotor–rotor coupling, control
instability, vibration — via flight-controller and sensor models in the loop.

A design "passes" only if **all** components operate within spec **and** the
integrated drone meets its flight requirements.

## 4. Benchmark suite (target: grows every milestone)

| Benchmark | Validates | Acceptance (declared before running) |
| --- | --- | --- |
| Free fall | integrator + dynamics | v(1 s) = 9.81 m/s ± 0.01 |
| Point-mass inertia assembly | mass properties | exact parallel-axis result |
| Hover equilibrium | thrust model + trim | net acceleration ≈ 0, thrust = m·g |
| Motor + prop static thrust table | propulsion model | interpolation error < 0.5 % on known data points |
| Throttle step response | motor electrical + ESC | matches measured current/thrust within declared tolerance |
| Battery sag under load | battery model | matches discharge curve within declared tolerance |
| Attitude step (5° roll) | controller | final angle within ±0.1° of command |
| Motor-out recovery / detection | failure logic | explicit failure report, no silent continue |
| Scenario regression | whole engine | outputs match saved baselines within tolerance |

Each benchmark stores its reference data under `data/benchmarks/` with
provenance. A benchmark run emits RMSE / max-error and a pass/fail against
the pre-declared tolerance.

## 5. Convergence and numerical error

Time-step (and any discretization) refinement until results stabilize is part
of every published simulation. The default integrator is adaptive
(`scipy.integrate.solve_ivp`, RK45 with tight tolerances); the fixed-step RK4
fallback exists for verification of the integrator itself.

## 6. Decision-equivalence claim

Simulation evidence is treated as decision-equivalent to physical testing
**only within the proven validity envelope** of the models. Any excursion
(much higher speed, novel geometry, untested component) produces an explicit
"not validated" marker instead of a number.
