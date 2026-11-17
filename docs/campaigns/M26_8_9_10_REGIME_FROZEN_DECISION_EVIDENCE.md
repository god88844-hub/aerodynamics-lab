# M26.8–M26.10 — Regime coverage, frozen prediction agreement, and decision-grade *software preflight*

**Software implementation scope only.** These modules compute rigorous quantities over **locally supplied original bytes**; they do not establish that any experiment truly occurred. No TU Braunschweig original data, hardware serial verification, instrument certificates, actual blinding protocol, or externally measured full aircraft results are included in this change. Global physical evidence issue [#16](https://github.com/god88844-hub/aeroforge/issues/16) must remain open.

## M26.8 — No pooling unrelated regimes

`physics.validation.flight_regime_coverage.audit_regime_holdout_coverage` repeats the complete original-source and M26.7 whole-flight partition check and requires exact, readable original CSV channel availability, calibration and clock references, and declared source permission. It evaluates each required `operating_regime_id/channel` separately, counting distinct **reported holdout experimental groups**, not calibration flights, extra time windows of a single flight, or flights in another regime. Insufficient channel/group/regime coverage returns `REGIME_HOLDOUT_CHANNEL_COVERAGE_INCOMPLETE`. A positive numerical screening only means that operator-supplied source files and group declarations agree; separate physical identity verification is needed.

## M26.9 — Frozen predictions compared with actually supplied original observations

`physics.validation.frozen_flight_comparison.compare_frozen_flight_channel` requires:

- Original M26.1–M26.5 native archive manifest and on-disk original **single-channel** UTF-8 CSV with exact `t_s,<channel>` header, SHA-256, byte count, calibration and clock references.
- M26.7 frozen model/version SHA, frozen protocol, whole-flight calibration vs holdout partitions, preregistration and user-reported reveal times.
- A *separate* frozen prediction file (outside original-measurement directory), SHA-256 and exact `t_s,prediction,lower,upper` header, with identical sample count and clock values to the original measured CSV.
- An explicit engineering channel/unit, maximum source sample gap, hard measurement uncertainty, hard numerical uncertainty and an additional **declared** model discrepancy budget; thresholds for maximum conservative absolute error and robust interval coverage.

For each sample, the conservative absolute error screen uses

```text
absolute_error_upper =
    abs(prediction - original_observation)
    + declared_measurement_hard_error
    + declared_numerical_hard_error
    + declared_extra_model_discrepancy_bound
```

The robust interval coverage numerator counts only samples whose **entire** reported measurement interval `[observation ± hard_measurement_error]` is contained within the frozen model interval `[lower, upper]`. The model prediction itself must lie inside that interval. It also reports nominal RMSE, nominal interval coverage, source hashes and canonical split digest.

**Absolutely no time interpolation, sample filling, unit conversion, unverified cross-flight join, altered original bytes or calibration-as-holdout substitution**. Unmatched time bases are rejected; source-specific clock decoders must be handled separately. Passing these numerical comparisons still does **not** demonstrate external physical accuracy: source/clock provenance, true prefreeze blindness and hard model discrepancy bounds remain unauthenticated.

## M26.10 — No declaration-only critical performance pass

`physics.validation.flight_decision_reports.assess_original_flight_decisions` recomputes every supplied M26.9 comparison **from the source and prediction files**, not from submitted green flags. Before comparing, each critical `operating_regime_id/channel` must define one fixed set of error and coverage limits used for every holdout in that regime. Passing held-out experimental-group counts must meet each requirement separately, and calibration sources cannot appear in comparisons.

It makes three distinct decisions:

| Result | Meaning |
| --- | --- |
| `FAIL_DECLARED_CRITICAL_NUMERIC_LIMIT_VIOLATION` | At least one directly recomputed holdout group violated a declared hard error or coverage requirement. A failure dominates missing coverage. |
| `INCONCLUSIVE_ORIGINAL_HOLDOUT_COVERAGE_MISSING` | No evaluated numerical failure, but the required distinct heldout groups or metric(s) are missing. |
| `ANALYTICALLY_CONSISTENT_NOT_PHYSICALLY_AUTHENTICATED` | All required operator-supplied numerical cases meet their declared thresholds, but no independent experiment certification, actual flight equivalence or release is established. |

A deterministic SHA-256 fingerprint covers the canonical split, metric requirements, original source hashes, prediction hashes and recomputed results. The result intentionally leaves independent original measurement source, clock calibration, true preregistration and physical decision-equivalence flags **false for every outcome**.

## Regression and scientific blockers

```bash
python -m pytest tests/physics/test_m26_regime_prediction_decisions.py -q
python -m pytest -q
```

All tests are based on explicitly **synthetic original-byte fixtures**. This code is ready to compare **real, separately acquired** evidence when the hardware, license, native encoding, source clock, instrument uncertainty, operating envelope and independent test custody are actually verified. It cannot source those external experiments from an inaccessible repository. It does not change the 10 major acceptance milestone families M21–M30 still scientifically outstanding through Drone v1.

**Do not use a reported numerical pass as flightworthiness evidence or to authorize hardware flight.**
