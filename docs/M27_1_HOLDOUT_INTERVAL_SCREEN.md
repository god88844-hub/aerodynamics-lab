# M27.1 — Conservative independent-run prediction interval screen

**Scope:** Pure, read-only Python validation diagnostic for *reported* blind holdout runs. This is not a physical experiment, not a measured whole-drone accuracy result, and not aviation certification.

## Purpose and acceptance logic

Given frozen model prediction `p`, its stated lower and upper interval `[L, U]`, reported observation `y`, and **externally justified hard absolute instrument-error bound** `u`, score:

- Robust enclosure: `L <= y-u` **and** `y+u <= U`.
- Possible enclosure: `L <= y+u` **and** `y-u <= U`.
- Conservative absolute prediction-error bound: `abs(p-y) + u`.
- Within-tolerance: conservative bound at or below the operator-declared frozen absolute-error threshold.

Both the robust enclosure fraction and the *entire-run* worst residual must satisfy the input thresholds **separately for every holdout run**. Pooling samples could conceal a bad regime. Two or more distinct holdout experimental groups are required and must not overlap listed calibration groups. Duplicate sample IDs and nonfinite/nonsensical measurements are refused.

`minimum_robust_coverage_fraction` is **not statistical confidence**: this function counts deterministic robust enclosures of operator-reported bands. A coverage guarantee about a future observation, a credible probability of success, and correlated-run generalization each require further evidence and a qualified statistical protocol.

## API surface

`physics.validation.holdout_intervals.audit_heldout_intervals(...)` accepts immutable-design identity fields (`frozen_model_git_sha`, `frozen_protocol_sha256`), channel, frozen numeric tolerance and target fraction, calibration group IDs, and reported holdout runs. Every holdout declares original source SHA-256, whole-experiment group, synthetic-vs-physical kind, hardware identity and separation flags; each row declares prediction, lower/upper band, observation and **hard** instrument bound.

This first increment intentionally has **no UI or HTTP endpoint**. Run in a verified Python environment; it does not touch flight physics, saved designs or calibration parameters. Later integration should reuse M19 raw-byte digest checks, M20 externally archived preregistrations, and M26 independent full-aircraft measurements rather than trusting metadata strings.

## Verdict

- `REPORTED_HOLDOUT_REJECTED` if source flags or any run-level tolerance or robust-band gate fails.
- `REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED` otherwise.

Both statuses **always** return `actual_independent_physical_validation_established=false` and `decision_equivalent_to_physical_testing=false`. Model and protocol hash strings alone do not authenticate preregistration timing or source bytes. The reported measurement type and exact hardware match are not third-party verified.

## Release checks

```bash
python -m pytest tests/physics/test_holdout_intervals.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

This is M27.1 **software diagnostic only**; M27 physical decision-credibility assessment and Issue #16 remain open pending genuine independently instrumented experiments.
