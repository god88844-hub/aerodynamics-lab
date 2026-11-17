# M27.8 — Original-source operating-regime holdout gates

Implement `physics.validation.regime_holdout_audit.audit_per_regime_holdouts` to prevent favorable global averages from disguising catastrophic failures in an individually declared operating regime.

The operator supplies two or more whole-run originally hashed paired measurement/prediction CSVs, an explicit set of 1–32 operating regime IDs, and one exactly matched `sample_id → regime_id` mapping for *every original sample* in *every heldout run*. Original CSV integrity and whole-run calibration isolation are checked by M27.2 before evaluating the regime partition. Each nonempty experiment/regime cell requires at least 5 observations. Each named regime must occur in at least two distinct declared whole experimental groups, and **every individual cell** must satisfy the predeclared absolute hard measurement residual bound and required fraction of whole measurement error intervals enclosed by the frozen predicted intervals. A failed group/regime cell, incomplete group coverage, altered original source or unlabeled sample blocks the overall result.

This is a **mathematical, operator-reported consistency check**, not a post-hoc statistically validated regime partition. Users may have chosen favorable regimes after seeing errors; there is no independent precommit timestamp authentication or real-measurement provenance verification. All returned physical-release, true-source and future-prediction-success claims remain false, even if every cell passes.

Synthetic regression: `python -m pytest tests/physics/test_regime_holdout_audit.py -q`. No real-world drone evidence is established.
