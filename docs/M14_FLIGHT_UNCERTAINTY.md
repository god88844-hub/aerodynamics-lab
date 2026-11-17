# M14 — Conservative Uncertainty Bounds for Flight Evidence

## Purpose

Near-physical prediction credibility requires **quantified model discrepancy and measurement uncertainty**, not numerical agreement alone. M14 extends the M13 read-only flight telemetry comparison with an **optional conservative bounded-error assessment**. This is not a statistical confidence interval and cannot authenticate operator-provided instrument tolerances.

## API

Use the existing `POST /api/simulations/{simulation_id}/flight-evidence` endpoint. The M13 request works unchanged. To opt in, add:

```json
{
  "measurement_error_bounds": {
    "altitude_m": 0.1,
    "bus_voltage_v": 0.05
  },
  "clock_error_bound_s": 0.02
}
```

This snippet is a format example, **not authenticated instrument specifications**. Supply one nonnegative finite hard absolute measurement bound for **every** measured channel, in its native SI unit. Declare an absolute bound on measurement-to-simulation clock alignment error (0–2 seconds). These must be established independently by instrument characterization, synchronization tests, and calibration records; not tuned to produce a pass. Set zero only with evidence that error is negligible.

At every observed timestamp, with signed prediction residual `r = predicted - measured`, measurement bound `U_m`, and a conservative local predicted signal slope `L` across the timestamp interval, the combined bound is `U = U_m + L * U_t`. A deterministic enclosure for the absolute residual is:

- Lower bound: `max(0, |r| - U)`
- Upper bound: `|r| + U`

`ROBUST_PASS` requires upper bound <= the predeclared maximum absolute error tolerance. `ROBUST_FAIL` requires lower bound > tolerance. Otherwise the sampled result is `INDETERMINATE`. Missing prediction support anywhere inside the clock interval gives `CLOCK_ENVELOPE_UNSUPPORTED`, never an optimistic clipped result.

Across channels and samples, the report issues `ROBUST_PASS_UNDER_DECLARED_BOUNDS`, `ROBUST_FAIL_UNDER_DECLARED_BOUNDS`, or `INDETERMINATE_UNDER_DECLARED_BOUNDS`. An M13 pointwise physical tolerance success is **downgraded** to `UNCERTAINTY_AWARE_TOLERANCE_NOT_DEMONSTRATED` if the user opted into bounds but cannot establish a robust pass. Legacy M13 requests retain `NOT_REQUESTED` as the new sub-assessment status; an M13 positive status without uncertainty is **not** an uncertainty-aware validation claim.

## Explicit scientific limits

- All observations, bounds, calibration status and hardware identity remain user-declared and unauthenticated.
- Declared hard bounds must really enclose all instrument errors; standard deviations, manufacturer typical accuracy and unverifiable guesses do **not** meet this condition.
- The local slope is calculated from saved piecewise-linear simulation telemetry; it does not bound the true continuous-time numerical integration error between samples.
- Numerical-model discrepancy, airframe structural error, environment mismatch, unmeasured sensors, spatial calibration, controller command differences, and systematic errors remain outside the assessed bound.
- Bound checks do not establish reliability for a distribution of independent missions, extrapolation beyond measured conditions, physical flight readiness, or certification.
- Synthetic tests verify mathematics and API behavior only. Physical equivalence still requires separate traceable physical campaigns and external technical review.
- Requests remain read-only and do not modify simulation predictions or battery/airframe models.

## Verification

```bash
python -m pytest tests/physics/test_flight_evidence.py tests/physics/test_flight_uncertainty.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```
