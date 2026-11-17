# M21 — Qualified battery laboratory acquisition handoff

**Status: execution package ready for an external laboratory; no physical experiment, pack calibration or blind validation has been performed by AeroForge.**

**Responsible parties:** aircraft owner (identify pack and decision), qualified high-power battery lab (approve safety plan, perform instrumented tests), independent V&V reviewer (freeze acceptance protocol, verify custody, judge failures). See [Issue #23](https://github.com/god88844-hub/aeroforge/issues/23), [Issue #21](https://github.com/god88844-hub/aeroforge/issues/21), and [Issue #16](https://github.com/god88844-hub/aeroforge/issues/16).

## 1. Stop before ordering or testing unless identity is established

Provide a complete **actual pack inventory**, not the generic 6S/12S model: pack manufacturer/part no., chemistry, series/parallel configuration, cell/battery serial and lot, nominal and measured capacity, voltage limits, date of manufacture, storage/cycle history, BMS and cooling/protection arrangement, connector and harness rating, and intended mission environment. Supply images/drawings where applicable. Do not substitute NASA aging data or unrelated public LiPo curves as exact-pack validation.

The nominal 60 kg capstone refers to an approximately **7–8C** hover demand; this is a *simulation workload description*, not an instruction to discharge a real pack at that rate. No operator should attempt hazardous high-current tests without qualified laboratory equipment, an approved electrical/thermal risk assessment, protected facilities and an independent stop/safety plan.

## 2. Frozen protocol before data disclosure

Prepare the actual M20 `ValidationProtocol`, with an independent timestamped preregistration and archived canonical SHA-256, committing all decisions and holdout partitions *before seeing held-out data*. Set **actual application-specific** tolerances and envelope for pack voltage, current, delivered Wh, available capacity, pack/cell temperature, cutoff crossing, high-C usable endurance and initial SOC. Neither this document nor the simulator invents these tolerances.

Record actual instrument manufacturer/model/serial, calibration trace, accuracy and bandwidth, logger synchronisation method, raw timestamp uncertainty and environmental sensors. Distinguish hard absolute measurement limits from standard uncertainties. Predeclare a calibration set and **at least two distinct whole-experiment holdout runs**; separate packs and aging/temperature regimes if independence claims require that. Reusing the same serial does not automatically count as independent hardware; preregister a narrower claim if necessary.

## 3. Original recording deliverable and custody

Laboratory transfers immutable **original, unedited** files with source reference/license, instrument/export format, original file digest, acquisition timestamp/clock evidence, laboratory/operator identity, pack serial, recording ID, experiment ID, calibration/holdout role and test-condition metadata. Minimum raw channels are timestamp [s], terminal pack voltage [V], current [A], individual cell voltages [V], pack/cell temperature [°C], status/protection events, plus a source-calibrated SOC/charge baseline and endpoint event. Include original missing-data indicators, packet drops and sample jitter. Keep original files separate from any normalized M19 CSV extracts.

M19's `t_s,terminal_voltage_v,current_a,temperature_c` is the **software ingestion view**, not proof that original sensors measured all required channels. Preserve raw instrument-native files and original column units alongside the normalized view; never manufacture a missing timestamp, cell voltage, thermistor reading or SOC state.

## 4. Independent comparison and acceptance

Use M19 to check imported file integrity, M20 to reject incompatible protocol/hardware/uncertainty declarations, then M21's read-only battery campaign evaluator. Compare the frozen OCV+R model to each entire held-out discharge. Report RMSE/MAE/max voltage discrepancy, voltage prediction band coverage, delivered Ah/Wh error, observed cutoff/warning crossing, SOC and temperature applicability, endpoint-time error, all out-of-range conditions, failed runs and any model-form unmodeled effects (C-rate, heating, aging, hysteresis). Do not refit on holdouts or suppress failures.

**Actual M21 scientific completion** requires source custody independently authenticated by the reviewer, calibrated instruments, genuine exact-pack holdout measurements in the tested envelope, and demonstrated predeclared error/coverage gates. Until then mark **PHYSICAL_BATTERY_VALIDATION_NOT_ESTABLISHED**.

## 5. Lab handoff checklist

- [ ] Exact pack and protection-system inventory with serials, safe manufacturer limits and actual aircraft/load relationship.
- [ ] Frozen M20 protocol digest and independently archived preregistration before held-out results exist.
- [ ] Qualified lab risk assessment, guarded apparatus and approved stop criteria (no improvised 7–8C tests).
- [ ] Calibrated sensors, full clock chain, cell-level and thermal channels, acquisition settings and instrument uncertainties.
- [ ] Separate whole-run calibration/holdout recording IDs, intact original files and SHA-256s.
- [ ] Reviewer-signed source and protocol reconciliation, including **failed** runs.
- [ ] Per-envelope residual/uncertainty analysis, mismatch disclosures and explicit acceptance/rejection.

**Cannot be completed by a software agent:** procurement, qualified laboratory experiment, sensor calibration certificate, independent custody and physical result authentication.
