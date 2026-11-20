# Prospective validation tolerances — M21–M27

Policy version **1.0.0** · issued **2026-11-20** · **PROSPECTIVE_PENDING_OWNER_AND_QUALIFIED_REVIEW**.
This is a concrete engineering research acceptance policy for owner sign-off, not an experimental result.
The numbers below are project-selected research targets, pending qualified review; NASA and NIST do not prescribe them.
They confer neither airworthiness nor universal equivalence to physical testing, and authorize no physical test.
Further model tuning must wait for the requested owner sign-off on this policy and the prototype/contract package.

## Basis and intended claim

[NASA-STD-7009B (2024), §§1, 4.2.5–4.2.7, 4.3.8](https://standards.nasa.gov/sites/default/files/standards/NASA/B/1/NASA-STD-7009B-Final-3-5-2024.pdf)
supports defining acceptance for an intended use, retaining validation domains, assessing empirical-data quality,
characterizing uncertainty, and reporting limitations and technical review. These principles motivate this policy;
this document does not claim NASA compliance, NASA approval, or source-specified numerical tolerances.

Acceptance, if eventually earned, applies only to the registered hardware, firmware, geometry, mission/decision,
environmental envelope and model version. A different aircraft family, installed component or weather mechanism
needs an explicitly justified extension and relevant independent evidence. A software test is verification evidence.

## Evidence partition and immutable registration

All **20 prior public campaigns already inspected or used for tuning are DEVELOPMENT evidence** under this policy,
including records historically named “holdout.” They cannot retrospectively become predeclared blind acceptance.
Keep their original reports; publish this role alongside later comparisons. No current campaign passes this gate.

Before confirmatory measurements or outcomes are revealed to model developers, archive an immutable registration:

1. Policy version and raw-file SHA-256; model Git SHA, executable/dependency hashes, project/design/controller hashes.
2. Exact hardware/serial/lot/geometry/firmware identity, component limits, intended decision and bounded regimes.
3. Whole independent experiment IDs, source/custody identities, calibration/development/confirmatory partitions,
   cohort membership, trial counts, randomization, recruitment/stopping rules and a data-access/reveal record.
4. Required channels/units/frames, sampling and clock-error bounds, analysis windows, frozen preprocessing,
   allowable exclusions/dropout handling, rated spans, positive relative-error denominator floors and metric code hash.
5. Instruments, traceable calibration records, bandwidth, measurement/clock/conversion uncertainty and correlations;
   numerical-convergence/error estimates, model discrepancy and the predictive uncertainty construction.
6. Every applicable threshold, uncertainty-width cap, fault class/severity, detection deadline, reference outcome
   rule, uncertainty decision rule, independent reviewer and qualified physical-test review where applicable.

For existing sealed files, a custodian registers byte hashes before access; for future recordings, register recording
IDs/acquisition protocol first and have the custodian hash and seal original bytes before developer reveal.
Partition complete recordings/experiments, never adjacent rows or overlapping flight segments. Related repeated
measurements, shared batteries/vehicles and shared calibration create dependence; register grouping and analysis.
The M20 default of one calibration and two disjoint holdouts is a readiness minimum, not statistical sufficiency.
Any same-vehicle alternative needs a predeclared independent justification; pseudoreplication cannot increase N.
Missing independent measurements, calibration, custody, blindness or qualified independent review means INCONCLUSIVE.

## Common metric and decision rules

Compare frozen prediction p_i with independent measurement y_i at registered synchronized timestamps.
For scalar residual e_i = p_i − y_i: MAE = mean(|e_i|), RMSE = sqrt(mean(e_i²)), max error = max(|e_i|).
For vector position/acceleration, use the Euclidean residual norm before these reductions; do not average axes away.
Use uniform registered time steps, or frozen duration weights for irregular sampling; never treat samples as trials.
Report each experiment, each channel and each cohort separately. Every applicable per-experiment limit must pass;
a pooled average cannot erase a failing experiment. Confirmatory trial counts and sampling limits must be registered.

Use SI in stored data: m, s, m/s, m/s², N, N·m, A, V, J, Hz and K; temperature differences in K equal °C differences.
Comparison coordinates are the registered local right-handed z-up frame (altitude and vertical speed positive up).
Record origin, body axes and all source-to-comparison transforms; apply gravity and specific-force conversions explicitly.
Attitude error is the shortest quaternion rotation angle, in degrees; do not subtract wrapped Euler angles.
No inferred timestamps, fitted time shifts, unit guessing, post-reveal trajectory alignment or unregistered filtering.

Relative error = |predicted − measured| / |measured| for a registered strictly positive outcome/floor.
Normalized MAE/RMSE divide by the **frozen positive engineering rated span for that channel**, not the observed range,
sample mean, prediction magnitude or a floor chosen after reveal. Zero/unknown denominators are INCONCLUSIVE.
Compare energy over the identical registered interval as the time integral of consumed electrical power;
register regenerative-power treatment. Endurance is time to the configured study endpoint, not an extrapolated flight.

Report raw residuals and propagate measurement, calibration, clock, conversion and numerical uncertainty separately.
For acceptance, the registered simultaneous 95% reference-uncertainty set must leave the required metric within
its limit under the frozen conservative propagation rule; uncertainty overlapping a limit is INCONCLUSIVE.
An observed reference-value violation still records FAIL and cannot be erased by larger error bars.
Ordinary standard deviations are not hard bounds; absent justified joint propagation, uncertainty is INCONCLUSIVE.

Malformed/missing/nonfinite inputs, unmatched hardware, missing channels, unsupported mechanisms, insufficient
independent trials or an unregistered envelope block acceptance. A failed solver/run cannot be reported as success.
An evaluable numerical violation or applicable component-limit excursion returns **FAIL**, even alongside missing
evidence. Otherwise missing prerequisites yield **INCONCLUSIVE**. Only complete independent evidence and review
can yield **ACCEPTED_WITHIN_REGISTERED_ENVELOPE**; no promotion occurs merely from syntactic validity or CI.

## Numerical research targets

| Gate | Registered quantities and limits (all applicable limits required) |
| --- | --- |
| M21 battery | Each decision-critical cell: voltage MAE ≤0.05 V; maximum optimism max(0, p−y) ≤0.10 V. Consumed energy and endurance absolute relative errors each ≤0.05. Zero late or missed configured study cutoffs. |
| M22 propulsion | Thrust, torque and current each: nMAE ≤0.05 and nRMSE ≤0.10 of its frozen rated span. For sign-resolved observations, zero incorrect signs. |
| M23 controls/sensors | Altitude RMSE ≤0.10 m and max error ≤0.30 m; attitude-angle RMSE ≤2° and max ≤5°; absolute latency prediction error ≤0.005 s. |
| M24 aero/thermal | Inertial vector-acceleration RMSE ≤0.75 m/s² and max ≤1.50 m/s²; thrust-coefficient MAE ≤0.001; power-coefficient MAE ≤0.0005; each critical temperature MAE ≤2 K and max ≤5 K. |
| M25 structures/faults | Failure-load absolute relative error ≤0.10, with zero overprediction beyond reference uncertainty; each matched resonance-frequency relative error ≤0.05. Fault-miss probability one-sided 95% upper bound ≤0.01; healthy false-alarm probability upper bound ≤0.05. |
| M26 complete flight | 3D-position RMSE ≤0.25 m and max ≤1.00 m; altitude/attitude limits as M23; vertical-speed RMSE ≤0.20 m/s and max ≤0.50 m/s; consumed-energy relative error ≤0.05. Zero missed/late cutoff or loss-of-control events. |
| M27 joint uncertainty | Simultaneous whole-flight joint coverage ≥0.95 and its one-sided 95% exact binomial lower confidence bound ≥0.95, separately for every registered hardware/regime cohort. All registered width caps must pass. |

M21: derive per-cell voltage only from an instrumented cell channel or independently justified cell reconstruction;
pack-average voltage cannot establish weakest-cell behavior. Chemistry, temperature, loading and ageing are cohorts.
Cutoff voltage/current/temperature limits come from the registered installed components and study, not these targets.
A predicted cutoff must occur no later than the earliest reference event time allowed by clock/event uncertainty.
Never extend a stopped test, invent a successful landing, or count a missing event/channel as “no cutoff.”

M22: register RPM, voltage, air density, installation and operating regime; static data alone do not validate inflow.
Judge sign only when the independently justified measured 95% uncertainty interval excludes zero.
If it includes zero, label sign UNRESOLVED; keep the point in magnitude metrics and report the unresolved count.
A decision requiring that unresolved sign remains INCONCLUSIVE; “near zero” is not an exemption from magnitude limits.

M23: compare simulated tracking with independent measured tracking under the same registered command/disturbance;
command-following error alone is not model validation. Evaluate applicable sensor-observation residuals and timing
with independent ground truth and declared bias, drift, noise, dropout, saturation and bandwidth conditions.
Latency is command/event-to-observed-response delay under a frozen event rule; never fit it after reveal.

M24: CT = T/(rho·n²·D⁴), CP = P_shaft/(rho·n³·D⁵), with n in revolutions/s, D in m and rho in kg/m³.
Register sign, shaft-power measurement, advance ratio, Reynolds/Mach ranges and nonzero-speed applicability.
Electrical power cannot silently replace shaft power. Match thermal sensor locations and boundaries separately.

M25: failure load is the registered onset of the specified physical failure mode, not nominal material strength.
Require p_load ≤ upper endpoint of its independently justified measured 95% uncertainty interval as well as ≤10%
absolute relative error; report any optimism within that interval. Missing mode/fixture equivalence is INCONCLUSIVE.
Match identified resonance modes before reveal. Unsupported joints, fatigue, buckling or failure modes remain open.
Each independent fault experiment is missed if any required fault is absent, wrong, or detected after its registered
deadline; each healthy experiment is a false alarm if any registered critical false alarm occurs in its fixed window.
Apply probability bounds per fault-class/severity/hardware/regime cohort and per healthy cohort; register durations.

M26: include complete takeoff-to-endpoint records with transients, disturbances and planned fault cases.
Register cutoff/loss-of-control definitions and detection deadlines. Classify recorded aborted/crashed flights by
their observed outcome; successful predictions cannot be substituted for a missing/failed flight or censored ending.

## M27: joint whole-flight coverage and bounded uncertainty

Freeze the critical output set, complete flight window, sample grid/event times and predictive tube before reveal.
A flight is **one joint success** only if its entire simultaneous reference-uncertainty set is inside that predictive
tube for **every** critical output and required time/event, and every width cap passes. Any uncovered output/time
makes that whole flight a coverage failure. Missing required data cannot count as a success; predeclared unusable
records remain disclosed and cannot be silently replaced. Unmet data-quality prerequisites remain INCONCLUSIVE.
Pointwise/per-channel “95% coverage,” pooled timestamps and pooled hardware/regimes do not satisfy this gate.
The observable containment result is conditional on a justified simultaneous measurement-uncertainty model;
per-sample 95% instrument intervals alone do not establish true-state whole-flight joint coverage.

For each output, freeze a maximum predictive half-width no larger than its decision-error tolerance:
cell voltage 0.10 V, position 1.00 m, altitude 0.30 m, attitude 5°, vertical speed 0.50 m/s,
acceleration 1.50 m/s², temperature 5 K; propulsion channels 0.10 of frozen rated span.
For CT/CP use 0.001/0.0005; for integrated energy/endurance and load/frequency use their relative limits above.
Full interval width is at most twice this cap; correlated vector/attitude sets use the corresponding radius.
Any additional decision-critical output needs a signed, registered numeric cap before acceptance is possible.
Caps constrain uncertainty; they do not replace the stricter MAE/RMSE targets. Widening intervals after reveal fails.

Use independent exchangeable whole experiments/flights as binomial trials within each predeclared cohort;
if dependence or nonexchangeability invalidates this assumption, obtain independent trials or preregister a reviewed
alternative before reveal. Fixed-N analysis and stopping rules are mandatory; no repeated peeking until a bound passes.
[NIST exact-binomial reference](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbino.htm)
documents one-sided exact bounds; this policy selects the conservative Clopper–Pearson method and 0.95 confidence.
With alpha=0.05, all n successes give L=alpha^(1/n); zero bad events give U=1−alpha^(1/n).
Thus **59/59** joint successes give L=0.9504923901; **0/299** misses give U=0.0099691468;
**0/59** healthy false alarms give U=0.0495076099. These are boundary examples, not universal sample guarantees.
Nonzero failures need the full exact-binomial inversion and a larger preregistered N if necessary.
The confidence statement is per cohort; a simultaneous claim across cohorts needs a predeclared multiplicity method.

## Machine-readable policy summary

Fractions below are dimensionless; suffixes declare engineering units. Prose prerequisites remain mandatory.

```json
{
  "policy_version": "1.0.0",
  "effective_date": "2026-11-20",
  "status": "PROSPECTIVE_PENDING_OWNER_AND_QUALIFIED_REVIEW",
  "scope": "registered_hardware_regime_decision_only",
  "historical_campaign_role": "DEVELOPMENT",
  "confidence_level": 0.95,
  "criteria": {
    "M21": {"cell_voltage_mae_v": 0.05, "cell_voltage_max_optimism_v": 0.10, "energy_relative_error": 0.05, "endurance_relative_error": 0.05, "late_or_missed_cutoffs_max": 0},
    "M22": {"thrust_torque_current_nmae": 0.05, "thrust_torque_current_nrmse": 0.10, "sign_resolved_error_count_max": 0, "sign_resolution_measurement_confidence": 0.95},
    "M23": {"altitude_rmse_m": 0.10, "altitude_max_error_m": 0.30, "attitude_rmse_deg": 2.0, "attitude_max_error_deg": 5.0, "latency_max_error_s": 0.005},
    "M24": {"acceleration_vector_rmse_m_s2": 0.75, "acceleration_vector_max_error_m_s2": 1.50, "ct_mae": 0.001, "cp_mae": 0.0005, "temperature_mae_k": 2.0, "temperature_max_error_k": 5.0},
    "M25": {"failure_load_relative_error": 0.10, "failure_load_overprediction_beyond_uncertainty_max": 0.0, "resonance_frequency_relative_error": 0.05, "fault_miss_probability_upper": 0.01, "healthy_false_alarm_probability_upper": 0.05, "zero_miss_example_n": 299, "zero_false_alarm_example_n": 59},
    "M26": {"position_3d_rmse_m": 0.25, "position_3d_max_error_m": 1.00, "altitude_rmse_m": 0.10, "altitude_max_error_m": 0.30, "attitude_rmse_deg": 2.0, "attitude_max_error_deg": 5.0, "vertical_speed_rmse_m_s": 0.20, "vertical_speed_max_error_m_s": 0.50, "energy_relative_error": 0.05, "late_or_missed_critical_events_max": 0},
    "M27": {"coverage_unit": "whole_flight_joint_all_critical_outputs_and_times", "cohort_rule": "each_registered_hardware_regime_cohort", "joint_coverage_min": 0.95, "one_sided_lower_confidence_min": 0.95, "confidence_method": "exact_binomial_clopper_pearson", "all_success_example_n": 59, "maximum_half_width_to_decision_tolerance_ratio": 1.0}
  }
}
```

## Sign-off and change control

Archive this file's raw-byte SHA-256 outside the file and retain the owner/reviewer identities, qualifications,
UTC approval times, conditions and referenced policy/model/partition hashes. A digest proves byte identity, not
approval authority or when registration occurred. Until recorded sign-off, this remains a locked proposal.
After sign-off, any threshold, metric, cap, preprocessing, cohort, stopping-rule or model change creates a new
version/hash and registration; retain the old record. Revealed confirmatory data become development data for
subsequent tuning. A changed candidate needs untouched independent confirmation; do not recycle a failed holdout.
Owner sign-off permits the next agreed work; it does not fill measurement/calibration/review gaps or accept M21–M27.
