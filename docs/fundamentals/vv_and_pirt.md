# Verification, validation and PIRT

Use [NASA-STD-7009B, 2024](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)
as the primary credibility framework: intended use, acceptance criteria, input pedigree,
numerical errors, validation domain, uncertainty and review (§§4.2–4.3).
This project does not claim NASA compliance, certification or NASA-prescribed error percentages.
Project numerical thresholds live once in [VALIDATION_TOLERANCES](../VALIDATION_TOLERANCES.md).

## Required workflow

1. **Define intended use.** Register decision, aircraft/configuration, regimes, failure
   criteria, observables, source identity and required uncertainty before accepting evidence.
2. **Code verification.** Check equations are implemented correctly with analytical
   rotations, forces/torques, conservation where applicable, units/frames, manufactured
   cases where appropriate, rejection behavior and regression tests. Passing tests is
   evidence about software, not agreement with a physical aircraft.
3. **Solution verification.** Quantify timestep, mesh, iteration and finite-precision
   effects for the actual case; report convergence, observed order and residual error.
   A stable-looking trajectory or solver residual alone is insufficient.
4. **Physical validation.** Freeze executable/model/dependencies, actual hardware,
   geometry, controller, environment, experiment partitions, scoring and tolerances
   before independent confirmatory reveal. Compare matching physical measurements;
   retain calibration/clock uncertainty, exclusions, discrepancies and failures.
5. **Uncertainty and credibility review.** Combine measurement, parameter, numerical,
   environmental and model-discrepancy uncertainty with documented dependencies.
   Assess joint whole-flight channel coverage and width limits by independent cohort,
   reject unsupported extrapolation, and obtain independent qualified review.

The distinction between code and calculation/solution verification is also explained
in NASA/NPARC's [verification and validation guidance](https://www.grc.nasa.gov/www/wind/plans/Policies_and_Plans.pdf).
Repeatable synthetic outputs verify a path; synthetic sensor or CFD values are not
physical measurements. Manufacturer calibration and a reused fit cannot become a
new independent validation campaign by changing labels.

All **20 previously inspected campaigns are DEVELOPMENT** under policy 1.0.0,
including historical holdouts. Preserve their original frozen partitions/reports.
Partition complete experiments, not adjacent rows; account for repeated tests on the
same vehicle/pack and common calibration. A hash establishes byte identity, not
independence, instrument accuracy or approval. Missing prerequisites yield INCONCLUSIVE;
an exceeded applicable limit yields FAIL. No future flight is authorized by a software report.

## Draft project PIRT

Phenomena Identification and Ranking Tables organize importance to a declared figure
of merit and state of knowledge; see [US NRC PIRT](https://www.nrc.gov/reactors/power/atf/pirt).
The following is project triage, **not an expert-panel qualification**. Priority/knowledge
rankings are `UNVERIFIED_ESTIMATE` judgments for mission prediction and failure detection;
observed historical results remain linked separately. Reassess per intended use.

| Phenomenon / gate | Importance / knowledge | Current evidence/gap | Next discriminating evidence |
| --- | --- | --- | --- |
| Battery sag, cutoff, usable energy / M21,M26 | High / limited | [SIT misses](../campaigns/M21_11_15_SIT_CUTOFF_FORECAST.md); replay is measurement-conditioned | Independent load/temperature/SOC/endpoint experiments with causal predictions |
| Thrust sign/inflow/installation / M22,M24 | High / limited | [UIUC sign disagreement](../campaigns/M24_2_6_UIUC_AXIAL_SWEEPS.md), limited installed data | Signed thrust/torque/RPM/electrical measurements, calibrated near-zero uncertainty |
| Electrical/thermal losses / M21,M22,M24 | High / limited | Effective fits; limited closed-loop thermal/electrical coupling | Synchronized loss, surface/core temperature as instrumented, cooling and load tests |
| Sensor/actuator/controller delay/saturation / M23 | High / limited | Offline response studies, incomplete exact firmware/sensor dynamics | Timestamped commands, bus/current/RPM and independent motion sensing; HIL |
| Fault detection and propagation / M25 | High / limited | [Misses/false alert](../campaigns/M25_7_11_UAV_FD_ESC_POWER.md) | Independent healthy/fault whole trials with predeclared detection deadlines |
| Joint strength, vibration, fatigue / M25 | High / limited | Analytical screens; apparatus-specific experiments | Material/assembly load and vibration/fatigue measurements with independent review |
| Coupled voltage/control collapse / M26 | High / limited | [QDrone transfer](../campaigns/M26_50_54_QDRONE_VOLTAGE_TRANSFER.md) is not a complete causal plant | Same-configuration voltage/current/thrust/control/trajectory records |
| Correlated mission discrepancy / M27 | High / limited | [2/5 whole flights covered](../campaigns/M27_11_15_DRONEPROPA_TRANSFER.md) | Preregistered independent joint whole-flight coverage by cohort |
| Wet/icing/sensor degradation / WP8 | Intended-use dependent / insufficient | Implementation held, no general coupled validation | Mechanism-specific measured experiments after hold release |

Record results in [ACCEPTANCE_LEDGER](../ACCEPTANCE_LEDGER.md), sources in
[data/registry.json](../../data/registry.json). Neither a PIRT rank, equation, green CI
nor a larger mesh closes a physical acceptance gate.
