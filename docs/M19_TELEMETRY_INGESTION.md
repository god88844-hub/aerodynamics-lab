# M19 — Strict telemetry ingestion and calibration/holdout leakage auditing

## Scope and engineering goal

Advance AeroForge's primary goal of near-physical predictive accuracy by
building the **evidence-infrastructure prerequisite**, rather than pretending
a public dataset or a green regression build establishes physical equivalence.

The new `packages/physics/validation/telemetry_ingestion.py` module provides:

1. Explicit schema for a *whole experiment recording* with original SHA-256,
   source/reference/permission, source type, unique run IDs, vehicle/pack IDs,
   calibration/holdout assignment, time gap limit and declared SI channel list.
2. Strict unchanged UTF-8 CSV with exact header, nonnegative elapsed seconds,
   strictly increasing timestamps, physical positive voltage/current, finite
   optional readings, row/byte limits and digest verification.
3. Conditional measured charge (Ah) and energy (Wh) integration using
   trapezoids across observed timestamps **only** when all observed intervals
   satisfy the operator's predeclared maximum sampling gap. This does NOT
   bound unobserved aliasing or instrument bias.
4. Split auditing by **whole physical experiment**, source recording, battery
   and vehicle. Matching identifiers or source SHA across calibration and
   holdout automatically flags leakage, even when the pointwise error is zero.
5. Explicit `SYNTHETIC_VERIFICATION_ONLY`, `DECLARED_DISJOINT_SPLIT_NOT_INDEPENDENTLY_AUTHENTICATED`,
   `CROSS_PARTITION_LEAKAGE_DECLARED` and sparse sampling statuses.
6. Read-only `POST /api/components/telemetry-audit` for independently supplied
   text manifests/CSVs, and an interactive input panel. Cross-recording
   partition audits are available through the CLI and multi-dataset API.
7. Test fixtures intentionally generated synthetically and marked as such;
   tests include invalid timestamps, NaN/Inf, corrupt bytes, invalid physical
   values, wrong units/header, duplicate group IDs, missing source and path
   traversal/symlink attacks. No external physical data is fabricated.

## Source acquisition and supported workflows

This milestone does **not** silently download any newly published datasets.
The M16 registry preserves candidates and license gaps, and M17's Table 5
shows why even the same propeller geometry can mismatch motor and mounting
conditions. Once a real source recording is obtained with permission,
copy only its unmodified bytes to `data/benchmarks/telemetry/<id>/trace.csv`,
supply a pinned `manifest.json` and run:

```bash
python scripts/audit_telemetry_ingestion.py --root data/benchmarks/telemetry
python scripts/audit_telemetry_ingestion.py --root path/to/independent/bundles --output outputs/telemetry_audit.json
pytest tests/physics/test_telemetry_ingestion.py tests/integration/test_telemetry_ingestion_api.py
pytest
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

The endpoint reads `{"datasets":[{"manifest":{...},"csv_text":"t_s,...\\n..."}]}`.
It does **not** write to disk, update components, fit parameters or override
the immutable model-of-record. Exact hash comparison is conducted against the
UTF-8 bytes represented in `csv_text`, including trailing newline.

### What this milestone has NOT established

- No independently authenticated, pack-specific high-C battery discharge
  under the reference aircraft's actual electrical and thermal envelope.
- No validated identical motor–ESC–propeller thrust/current/thermal measurements.
- No independent fully synchronized, matched aircraft full-mission flights.
- No external validation of sensor uncertainty, clock alignment, genuine
  independent holdout status, or any near-equality probability.

All telemetry manifests and partition claims are **user-supplied metadata**,
not independently audited certificates. A split passing consistency checks
does not prove the model predicts the held-out data. **Issue #16 stays open.**
