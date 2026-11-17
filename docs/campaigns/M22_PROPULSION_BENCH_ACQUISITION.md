# M22 — Exact motor–ESC–propeller qualified bench campaign handoff

**Status: external experiment specification prepared; no original exact-hardware independent bench measurements acquired or authenticated.** This is not authorization for unsupervised rotating propellers, high-power testing or aircraft operation.

**Required team:** exact-hardware owner and configuration custodian, qualified propulsion dynamometer laboratory with protective test facilities, independent engineering safety authority, measurement/uncertainty reviewer. See [Issue #25](https://github.com/god88844-hub/aeroforge/issues/25), [Issue #21](https://github.com/god88844-hub/aeroforge/issues/21), [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16).

## 1. Identify the hardware whose physics must be validated

Reference capstone powertrain is the **T-Motor P80 III KV100 motor + G30×10.5 propeller**, with the **actual selected ESC**, intended electrical bus/harness, mechanical mount and installation geometry. Record genuine motor, ESC and propeller serial/lot/revision and OEM operating limits; identify prop orientation, blade material, original mount, protection hardware, controller firmware/PWM/DSHOT settings, supply source and measurement arrangement. A **G30 experiment with a different motor** is useful method evidence, not validation of this exact motor/ESC/prop combination.

Freeze AeroForge's model commit, component database revision, design BOM and source hashes before held-out bench tests. Do not manufacture source identities or assume manufacturer calibration knot reproduction is an independent benchmark.

## 2. Have a qualified lab sign the experimental scope

Before collecting or examining blind results, the independent reviewer must approve the M20 `ValidationProtocol`, initial calibration versus whole-experiment holdout partition, actual voltage/RPM/load/temperature/airspeed/density operating bounds, installed mechanical constraints, sensor uncertainty budgets, clock alignment method and numerical acceptance thresholds. Predeclare separate **static** and **dynamic/transient** gates: thrust [N], bus current [A], voltage [V], RPM, shaft torque [N·m] if instrumented, ESC/motor/prop temperature, response delay, settling/saturation and continuous-rating constraints. Never treat a static plateau dataset as a transient time history.

A laboratory-signed rig safety and maximum allowable working-load plan must control rotation, protection/shielding, electrical supply and mechanical failure containment. The test team defines safe sequences based on OEM hardware ratings; this handoff deliberately does **not** instruct unqualified users to spin propellers or operate hazardous high-current systems.

## 3. Original evidence package expected from laboratory

For each independently executed run, deliver an immutable original native logger stream, actual hardware serial set, fixture ID, qualified operator/lab, acquisition timestamp and clock-chain basis, source permissions and SHA-256, ambient pressure/air density/temperature, power bus conditions, sample rate, missing samples, and instrument make/model/serial/calibration references.

Requested synchronized channels, where technically feasible: thrust [N], RPM, motor shaft torque [N·m], bus voltage [V], bus current [A], controller commanded throttle/actual ESC state, motor winding/ESC temperature [°C], and electrical/thermal fault and saturation events. State precisely where sensor bandwidth, uncertainty, phase alignment or load-cell geometry prevents inference. Preserve raw native logs before any averaged plateau export.

For the M22 **static plateau** ingestion view, produce `rpm,voltage_v,thrust_n,current_a` rows only from genuinely stable periods, along with original source hashes and a defensible plateau-selection protocol. Preserve a separate timestamped transient source instead of inventing time values for the static rows.

## 4. Independent error evaluation

Run M20 hardware/protocol/uncertainty checks, then M22 static source-pinned propulsion evaluator on exact-hardware holdout plateau measurements, with no tuning to holdouts. Evaluate thrust and current against actual frozen model predictions, and report all unmodeled regions. For dynamic records, establish a separate preregistered comparison of torque/throttle lag, thermal transients and component limits; the existing static model cannot receive a dynamic pass merely from this handoff.

A hard failure or unsupported operating point must produce **FAILED / INCONCLUSIVE / OUT_OF_ENVELOPE**, never forced agreement through rescaling input data. Holdout groups must be separated by whole source recording, calibration role and hardware/fixture identity per the registered protocol.

## 5. Laboratory and reviewer acceptance checklist

- [ ] Exact motor, prop, ESC, firmware, mount and rig identity recorded with serials/revisions and OEM limits.
- [ ] Independent qualified mechanical/electrical safety approval and guarded test environment.
- [ ] Immutable model/protocol/design fingerprints and predeclared static + dynamic acceptance criteria.
- [ ] Calibration and separate whole-experiment blind holdouts with source-license/chain-of-custody records.
- [ ] Original instrument logs (including rejected/failed runs), original SHA-256 and calibrated uncertainty budgets.
- [ ] Per-run and per-regime thrust/current/torque/thermal residual report and any observed component limit violations.
- [ ] Independent reviewer verifies physical origin, model freeze, operating support and all failed scenarios.

**Exit state remains:** `PHYSICAL_PROPULSION_VALIDATION_NOT_ESTABLISHED` until these original exact-hardware observations and qualified reviews exist. No statement about flight safety or entire-aircraft validity follows from a positive static thrust benchmark.
