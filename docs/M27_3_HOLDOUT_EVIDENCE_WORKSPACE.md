# M27.3 — Original source holdout audit API and evidence panel

Extends M27.2's original-source integrity and exact alignment tests into AeroForge's right-side evidence workspace.

`POST /api/components/source-pinned-holdout-audit` accepts a frozen SHA-1-format 40-hex Git model commit identity, protocol SHA-256, channel, predeclared absolute error and robust coverage targets, declared calibration group IDs, and 2–60 whole-experiment holdout runs. Per-run CSV strings contain original prediction and measured-value rows with separate SHA-256 digests.

The API strictly forbids extra fields and nonfinite typed numerics, and delegates to the read-only M27.2 original-byte and whole-run evidence gates. The panel displays per-run worst residual, observed hard-bound enclosure fraction, and plainly states that physical origin and preregistration are NOT independently authenticated.

Neither a claimed SHA-256 digest nor a physically labelled input proves that actual independently instrumented measurements took place. Every response reports `actual_independent_physical_validation_established=false`, `decision_equivalent_to_physical_testing=false`. No parameter fitting or stored-aircraft model modification occurs.

Synthetic-only tests:

```bash
python -m pytest tests/physics/test_source_pinned_holdouts.py tests/integration/test_source_pinned_holdouts_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

All future actual-hardware validation is external and remains blocked under issue #16. This is no flight-authority or airworthiness certification.
