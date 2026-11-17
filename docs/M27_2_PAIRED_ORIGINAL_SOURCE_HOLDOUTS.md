# M27.2 — Original-byte-pinned paired blind holdout imports

**Purpose:** Provide a traceable, no-imputation data integrity gate for comparing a frozen model's original prediction CSV with a separately supplied original observation CSV, before running the existing M27.1 hard-uncertainty interval audit.

## Source contracts

For each whole-experiment holdout run (2–60), supply original UTF-8 CSV strings and declared SHA-256 digests. Per-file limit: 1,000,000 bytes; per-file original rows: 5–5,000. Exact headers:

```csv
sample_id,t_s,observed,measurement_hard_bound
```

and

```csv
sample_id,t_s,prediction,lower,upper
```

Every row must have a unique, valid sample ID; finite numeric values; nonnegative timestamp, nonnegative absolute deterministic hard measurement error bound; time starts at zero and strictly increases. The two files must agree on every sample ID and numeric timestamp in original row order. This first increment refuses any time resampling, interpolation, clock shifting, missing data imputation or smoothing. Source hashes are checked against the supplied original bytes; identical or reused original sources across disjoint runs are refused. Multiple scenarios require distinct entire-run groups outside all calibration groups.

Each aligned sample is passed without fitting any parameters to M27.1 `audit_heldout_intervals`; every run is independently gated on its frozen maximum absolute residual and declared fraction of samples whose **entire hard measurement interval** falls inside the supplied prediction band. A failing run cannot be hidden by favorable pooled averages.

## Limitations

SHA-256 comparison only establishes **consistency between data bytes and the claimed digest**. It does NOT prove that an experiment was physically performed, sensors were calibrated, the user-provided source was independently recorded, the model was frozen before the test, or the manufacturer/specimen identity was authentic.

A physical label can be spoofed; tests deliberately exercise a fake 'reported physical' label. `actual_independent_physical_validation_established` and `decision_equivalent_to_physical_testing` always remain **false**, even if the numerical gates accept the self-reported campaign. Future qualified outside review must verify actual source custody, preregistration timing, measurement chain, independent holdout selection, model convergence and predictive error across the intended operating envelope.

Implementation: `physics.validation.source_pinned_holdouts.audit_source_pinned_holdouts` is read-only, not an HTTP endpoint or release certificate.

## Synthetic regression gates

```bash
python -m pytest tests/physics/test_source_pinned_holdouts.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

Original qualified physical experiments and independent review are still open in issue #16.
