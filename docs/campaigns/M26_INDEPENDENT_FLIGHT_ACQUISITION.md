# M26 — Independent full-aircraft flight evidence acquisition and acceptance handoff

**Status: qualified flight-campaign planning document, NOT a flight authorization or completed physical test.** End-to-end model fidelity remains unvalidated. The 60 kg hexacopter is an analytical capstone and its simulated single-motor-out scenario is **unrecoverable**. Do not conduct a flight based only on its reported software metrics.

**Prerequisites:** M21 actual pack and M22 actual installed propulsion credibility over the intended envelope; M23 sensor/actuator/controller hardware validation; structural/thermal safety reviews; M20 locked preregistration; qualified test supervisor, applicable local operational permissions, approved test range and professional risk-management plan. No software agent can grant aviation permission or independently perform physical flight tests.

## 1. Freeze one real vehicle and operating envelope

Register exact airframe/propulsion/pack/controller BOM including serials and hardware revisions, measured 3D rotor/airframe geometry, mass/CoG/inertia and all installed payloads, firmware version/configuration, mounting alignment, external environment, true available component continuous/peak ratings and instrument/calibration chain. Preserve a canonical original configuration with physical configuration controls and photos or drawings for a qualified engineering reviewer. The digital copy must be reconciled against the measured actual machine.

Define what the prediction must support: which mission, payload, ambient wind/density/temperature, vehicle state/SoC, altitude/speed/attitude and control inputs. **Every decision-critical output needs a preregistered tolerance and uncertainty/coverage gate**. Unsupported conditions must remain marked outside validated scope. Never infer safe motor-out or emergency recovery from hover-only data.

## 2. Independent safety review before any flight is considered

Qualified aviation operations, structural/electrical/thermal and flight-test specialists must sign applicable design safety, system limitations, range/containment, ground crew roles, redundant fail-safe and emergency action plans; the relevant authorities must grant required permissions. Battery and propulsion lab readiness cannot be bypassed by an apparently successful simulator run. The exact **single-motor-out failure in the 60 kg hexacopter remains a failed simulated case** and must be explicitly addressed by the relevant qualified engineering authority before any use decision. This handoff provides no flight-control procedures, hazardous test sequences or operational clearance.

## 3. Original independent flight evidence required

Under approved professional operation, acquire immutable synchronized original streams recording vehicle/flight identity, clock origin and drift, packet loss, controller and sensor configuration, sensor calibration, and operating context. Requested channels include:
- time bases, command targets and controller output/actuator commands;
- position/altitude/velocity, attitude and rates with stated coordinate frames, filter versions and GNSS/IMU/barometric uncertainty;
- pack current, pack/cell voltage, temperature, protective/saturation events and declared electrical/thermal limits;
- wind/air density/temperature, mass/payload, flight envelope and physical configuration deviations;
- rotor RPM/ESC status if actually instrumented; never synthesize missing channels;
- test safety/event annotations and any off-nominal/aborted/failed conditions.

Retain original logger-native files (with SHA-256 and independent source/clock custody) and separate any derived M19 synchronized CSV. Rejected telemetry, dropped packets, aborts, limit violations and loss of control must be kept in the dataset, not hidden.

## 4. No blind test until model and acceptance criteria are frozen

The reviewer registers model version, protocol hash, full split by independent whole missions/aircraft configurations, predefined per-regime acceptance limits and declared physical sensor/clock uncertainty **before viewing blind holdout flights**. Reserve complete separate missions for holdout; rerecording the same mission or splitting a continuous run into windows cannot claim independent experiments. Qualify any same-aircraft reuse explicitly with a narrower generalization claim.

Across repeat professional-test regimes, compare *frozen* AeroForge predictions with recorded controls and measured trajectory, attitude, altitude, response delay, terminal voltage/current, energy/Wh, thermal behavior, component exceedances and observed endurance. Require numerical convergence/uncertainty coverage and explicit discrepancy budgets, including model form, environment and unmodeled failures. Report worst-case error, RMSE/MAE/bias and prediction-interval coverage by regime; publish all out-of-envelope failures.

## 5. Independent release gating

- [ ] Actual BOM, measured properties, calibration/firmware versions and instrument identities reconciled.
- [ ] M21/M22/M23 evidence independently meets applicable physical acceptance criteria; M25 structural/thermal failures reviewed.
- [ ] Applicable professional operations/range authorization and approved safety plan exist *before* operations.
- [ ] Frozen M20 protocol, model/design/config digests and independently archived blind partition.
- [ ] Genuine separate-flight original telemetry, synchronized clocks, original file hashes and traceable custody.
- [ ] Per-regime simulated versus physical errors and uncertainty coverage satisfy **predeclared** critical thresholds.
- [ ] All failed/aborted tests and unsupported conditions disclosed; no generalization to missing conditions.
- [ ] Qualified external technical reviewers approve the exact intended application, limitations and residual risk.

**Exit gate:** `INDEPENDENT_FULL_AIRCRAFT_PHYSICAL_VALIDATION_NOT_ESTABLISHED` until the complete evidence and independent engineering review exist. A software-only artifact or public unrelated drone flight dataset cannot satisfy this condition. See [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16).
