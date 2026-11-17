# M26.11–M26.13 — Physical limit screening, uncertainty stress and reproducible flight evidence dossier

**Software scope only.** These three additions perform reproducible arithmetic over explicitly supplied original flight source bytes and frozen prediction CSVs; no independent physical measurements, calibrated clock logs, actual component rating certificates, source custody, or pre-unblinded model freeze is supplied by this software. All positive statuses are **conditional analytical checks**, not physical flight validation, certification, or release.

## M26.11 — Component physical limit and supported envelope screen

`physics.validation.flight_envelope_limits.screen_flight_hard_limits` replays the complete M26.5/M26.7 original-file and whole-flight split checks. For each declared operating regime + measured channel it requires:

- `envelope_min`, `envelope_max` — supported or intended model applicability limits.
- `hard_limit_min`, `hard_limit_max` — operating limits asserted for the exact installed component, with hard limits enclosing the declared supported envelope.
- A source reference for those limits, engineering units inherited from the exact supported original CSV channel, and the maximum permitted original timestamp interval.

Every supported original heldout CSV is rehashed and parsed; its actual extrema are checked. If any measured point exceeds its declared physical hard limit the result is `FAIL_DECLARED_PHYSICAL_HARD_LIMIT_EXCEEDED` even if another source or a model prediction appears successful. If the hard limits are not exceeded but an observation is outside the declared model validity envelope, sampling gaps are unsupported, or a required channel has no data, the result is **INCONCLUSIVE**. A contained outcome means only the numbers fall within *operator-reported* component limits. Their authority, true installed-part identity and instrument accuracy are not authenticated.

## M26.12 — Widen-only uncertainty budget stress

`physics.validation.flight_uncertainty_stress.audit_frozen_uncertainty_sensitivity` calls the M26.9 original-byte and prediction-file comparison again for the baseline and **every declared stress scenario**. Each scenario can only maintain or increase the measurement hard error, numerical hard error and additional model discrepancy hard error. It **cannot lower a budget or relax the predeclared acceptance limits** to manufacture a pass. The source and model/prediction SHA-256, frozen split and threshold remain fixed. It reports sample-wise worst-case conservative residual, robust measurement interval coverage, margins, and a deterministic fingerprint.

- Baseline fails: `FAIL_ORIGINAL_DECLARED_NUMERICAL_BASELINE`.
- Baseline passes but any widened scenario fails: `INCONCLUSIVE_UNCERTAINTY_STRESS_LOSES_DECLARED_PASS`.
- All explicitly submitted scenarios pass: `ALL_SUBMITTED_UNCERTAINTY_STRESSES_CONDITIONALLY_PASS_UNAUTHENTICATED`.

A green finite set of user-chosen stress scenarios is **not** proof those assumed upper error bounds are physically correct, or exhaustive over every failure.

## M26.13 — Direct recomputation of all three decision dimensions

`physics.validation.flight_evidence_dossier.build_flight_evidence_dossier` takes original sources and a frozen M26.7 holdout protocol, M26.10 critical metric thresholds, matched M26.11 physical component/envelope limits, and one M26.12 set of stress scenarios per original source. It **does not accept caller-submitted pass flags**. It re-reads original files and recomputes:

1. M26.10 failure, numerical agreement and missing holdout/critical metric decisions;
2. M26.11 original observed signal component-limit violations and out-of-envelope decisions;
3. M26.12 each original heldout source's widened hard-error sensitivity.

**FAIL takes precedence over INCONCLUSIVE, and INCONCLUSIVE takes precedence over a conditional analytical pass.** Missing safety limits, omitted stress cases, mismatched channel/regime declarations and original-byte changes cannot be treated as success. A canonical SHA-256 binds split, original source/prediction digests and the recomputed reports. The dossier marks all independent real-world source, true blind preregistration, physical decision equivalence, manufacturing and flight release flags **false** regardless of numerical outcome.

## Validation and remaining scientific blockers

```bash
python -m pytest tests/physics/test_m26_limits_sensitivity_dossier.py -q
python -m pytest -q
```

All new regression fixtures are **synthetic** and designed to fail on changed bytes, incorrect claimed operating limits, source-metric omission, unsupported measurements, missing whole-flight groups, excessive error bounds or absent required stress cases.

**Still outstanding:** acquire the original instrument datasets with permitted rights; verify exact P80III/prop/ESC/controller/pack hardware, source custody, physical sensor uncertainties, environment and clocks, and preregistered genuinely blind holdouts. [Physical validation blocker #16](https://github.com/god88844-hub/aeroforge/issues/16) remains open. A software-only dossier does not complete the original M26 scientific exit milestone or reduce the ten remaining M21–M30 acceptance milestone families.
