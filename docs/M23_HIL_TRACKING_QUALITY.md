# M23.2 — Frozen controller telemetry and hardware-loop evidence (software audit)

## Scientific purpose

AeroForge needs independently held-out test data from the **actual**
flight controller/actuators/sensors before claimed simulation predictions
could become decision-equivalent to physical measurements. This milestone
does **not** acquire, manufacture, spoof or authenticate such experiments.
The existing multirotor simulation and control equations are unchanged.

## Implemented source integrity / conservative tracking audit

- Original, SHA-256 verified UTF-8 telemetry with the **exact SI header**:
  `t_s,command_roll_deg,observed_roll_deg,command_pitch_deg,observed_pitch_deg,saturation_flag`.
- Finite and physically supported angle values; elapsed time begins at zero,
  strictly increases, and is checked against a predeclared maximum gap.
  The saturation field is strictly 0 or 1, never guessed or silently filtered.
- Frozen M20 protocol ID and externally supplied SHA-256, exact controller
  configuration digest, hardware serial/firmware revision, source SHA, declared
  sensor serial and calibration references. Metadata is operator controlled.
- Require separately declared whole-experiment calibration and at least two
  holdouts. Cross-partition recording, experiment, vehicle, battery, sensor,
  controller and source-file reuse is reported as possible leakage.
- Compute roll/pitch tracking absolute error, worst sample, RMS and saturation
  count. Add declared deterministic measurement hard bound conservatively to
  the worst observed error before comparing against the frozen
  `attitude_error_deg` acceptance limit.
- Nonzero/unknown clock misalignment blocks a **continuous-time** tracking
  enclosure. Sensor noise, model discrepancy and controller internal timing
  are not automatically resolved by this check.

### Critical distinction

The **commanded** and **observed** angles are reported from a controller
trace. Comparing those tells us how *that reported controller* tracked
the reported command, **not** whether AeroForge's model predicted the
trajectory. There is no time-aligned frozen simulator prediction input in
this milestone. Accordingly, the status remains
`HIL_PHYSICAL_VALIDATION_NOT_ESTABLISHED`, and the audit always reports:

- `simulation_prediction_error_measured: false`
- `independent_controller_hardware_validation: false`
- `aircraft_flight_readiness: false`

A user-selected `reported_physical_hil` label is not proof of an
independent physical experiment. Synthetic tests intentionally exercise
label spoofing, source-byte tampering, group leakage, firmware digest
mismatch, out-of-range values and actuator saturation. Green tests
are **software verification only**, never sensor calibration or flight
authorization.

## Interface and verification

`POST /api/components/hil-tracking-quality` accepts a frozen M20
`ValidationProtocol`, its precommitted SHA-256, and 1–16
`HILRecording` declarations containing their original, unchanged
source CSV strings. The HIL panel is in AeroForge's right-side
evidence workspace.

```bash
python -m pytest tests/physics/test_hil_evidence.py tests/integration/test_hil_evidence_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

## Still required to complete actual M23

Independently authenticated identical controller firmware/parameters,
calibrated instrumented hardware-in-the-loop and in-flight recordings,
external time-sync uncertainty budgets, test rig/actuator timing,
saturation/failure conditions, **frozen simulator predictions** for the
same commanded mission, independent full-run holdouts, and an
independent professional engineering review. See
[issue #27](https://github.com/god88844-hub/aeroforge/issues/27).
None of these dependents can be replaced by more synthetic fixtures.
