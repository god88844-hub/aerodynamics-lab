# M13 — Independent Flight Telemetry Comparison Lab

## Goal and honesty standard

AeroForge's primary purpose is simulation evidence **approaching the reliability of
real-world measurements within quantified, independently validated envelopes**.
This milestone adds one missing instrument for that goal: comparison of a
**frozen, persisted simulation run** to actual operator-supplied flight logs.
**No real hardware measurements are supplied or asserted by this feature.**
The software's synthetic fixtures verify the implementation, not accuracy
of aircraft predictions. Only independent real measurements can provide that.

## Workflow

1. Save a design and run the existing **Flight** takeoff/hover/land scenario.
   Its recorded prediction must exist in the database and have completed.
2. Acquire physical flight telemetry from the actual vehicle using
   instrumented and professionally supervised testing appropriate to the
   vehicle and applicable regulations, **not from a demonstration prompted
   by the software's result**. Preserve raw flight controller logs and
   instrument calibration externally; the app does not authenticate them.
3. Record the aircraft/vehicle ID, flight-log ID, source, and manually
   declared clock offset. Declare if hardware matches the simulated design
   and whether data were used during calibration. The declared comparison
   must use identical mission commands, loads, environment and time origin
   or the numerical errors have limited scientific meaning.
4. Predeclare a maximum absolute error **per measured channel**, with SI
   units, before inspecting measured-vs-predicted errors. Enter CSV rows
   using the format below; each measured channel must have ≥5 samples.
5. Compare. The endpoint retrieves the original prediction by simulation ID
   and linearly interpolates to observed timestamps without extrapolating,
   shifting, scaling, or optimizing the log to get a better fit. It reports
   MAE, RMSE, bias and worst error for each measured channel, sampling and
   duration coverage, one reproducibility digest, provenance and caveats.
6. External, independent engineering review remains mandatory before treating
   passing observations as physical validation, let alone airworthiness.

## API

`POST /api/simulations/{simulation_id}/flight-evidence`

Example **synthetic-only format** (numbers are not flight measurements):

```json
{
  "dataset_kind": "synthetic_fixture",
  "vehicle_id": "synthetic_vehicle",
  "flight_log_id": "synthetic_log_B",
  "log_source": "analytic software verification data",
  "hardware_matches_simulated_design": false,
  "unused_for_model_calibration": true,
  "measurement_to_sim_time_offset_s": 0,
  "tolerances": { "altitude_m": 0.25, "bus_voltage_v": 0.5 },
  "observations": [
    { "t_s": 0, "altitude_m": 0, "bus_voltage_v": 24 },
    { "t_s": 2, "altitude_m": 4, "bus_voltage_v": 23.8 },
    { "t_s": 4, "altitude_m": 8, "bus_voltage_v": 23.6 },
    { "t_s": 6, "altitude_m": 12, "bus_voltage_v": 23.4 },
    { "t_s": 8, "altitude_m": 16, "bus_voltage_v": 23.2 }
  ]
}
```

Optional CSV header:

` t_s,altitude_m,vertical_speed_m_s,bus_voltage_v,battery_current_a `

**Coordinate convention:** simulation uses NED `z` and `vz` positive DOWN.
The comparison API converts these to flight-log relative altitude/vertical
speed **positive UP** from the same takeoff origin. Time is in elapsed seconds
from scenario start after the explicitly entered offset. `bus_voltage_v`
is the electrical bus measurement; `battery_current_a` is compared to the
*sum of modeled per-motor currents* (auxiliary loads may be omitted).
No GPS/geodetic conversion is supplied. Missing channels stay missing, never
zero-filled or inferred.

## Hard evidence gates

- 404 if no stored simulation; 422 for failed/non-flight simulations, bad
  channel data, invalid timestamps, unmeasured channels, or missing/invalid
  predeclared tolerances.
- No extrapolation outside the simulated interval, no implicit time offset.
- Mission coverage must be at least **80%** and original simulation
  telemetry samples spaced no more than **0.5 seconds**, or the quality
  check refuses a positive conclusion.
- All supplied channels must meet the operator's individually declared
  maximum-absolute-error thresholds for a positive *reported tolerance*
  outcome. A few sample points do not establish unseen transients.
- Synthetic fixtures always return `SYNTHETIC_VERIFICATION_ONLY`, no matter
  how close their equations match; calibration-dependent log data cannot
  count as independent validation; missing hardware-match declarations
  do not yield any reported tolerance success.
- Even physical, held-out, in-tolerance submissions say
  `REPORTED_FLIGHT_TOLERANCES_MET_NOT_INDEPENDENTLY_AUTHENTICATED` — never
  `CERTIFIED`, `SAFE` or a probability of real-world mission success.
- Endpoint is read-only: no new fit, no overwritten components, models,
  simulations or prior evidence records.

## Known limitations / next milestones

This is a strict **comparison tool**, not physical validation by itself.
Measurement instrumentation, calibration, real hardware identity, treatment
of environmental uncertainty, controller commands, measurement covariance,
latency/bias, repeatability across multiple vehicles and environmental
conditions, and independent provenance remain unverified. The existing
flight scenario also assumes sensor ideality and missing physical effects.

To approach the primary reliability goal, the next steps require:
independently supplied 12S pack high-C discharge datasets, blind motor/prop
bench samples, raw flight-controller telemetry from multiple separately held
out flights, measurement uncertainty intervals, model-discrepancy bounds,
independently assessed applicability envelopes, and externally reviewed
engineering validation gates. Until these exist, AeroForge reports where
simulation differs from logs but **cannot assert near-equality to physical
validation**.

## Test commands

```bash
python -m pytest tests/physics/test_flight_evidence.py tests/integration/test_flight_evidence_api.py -q
python -m pytest -q
cd apps/web
npm ci
npm audit --audit-level=moderate
npm run build
npm test
```
