# M26.14–M26.16 — Frozen flight campaign runner and external-evidence blocker report

**Release status:** software-only source integrity / numerical readiness. **No independently authenticated physical flight evidence or vehicle flightworthiness is established.** These three additions allow the existing M26.11–M26.13 dossier computation to be executed from explicit evidence files instead of requiring Python source modifications.

## M26.14 — Pin exactly the original input JSON bytes

Use `physics.validation.frozen_campaign_inputs.audit_frozen_campaign_inputs` with the exact local source manifest JSON and the frozen campaign configuration JSON and their separately supplied lowercase SHA-256 digests. The helper rejects changed bytes, invalid UTF-8, duplicate keys, nonfinite JSON numbers, unexpected campaign fields and missing native file inventory. A passed check means **only that the operator's pins match bytes already present locally**; it cannot authenticate a publisher, an instrument, hardware serials, original timestamps, legal access, or truly pre-unblinded preregistration.

The campaign configuration has these exact root fields:

- `holdout_case`: the existing M26.7 whole-flight calibration/holdout configuration.
- `required_metrics`: M26.10 exact per-regime quantitative error/coverage acceptance requirements.
- `comparison_cases`: M26.9 immutable original CSV vs externally stored frozen prediction CSV inputs.
- `required_limits`: M26.11 explicit operating ranges and physical hard limits, linked to source references.
- `stress_cases`: M26.12 widened measurement, numerical and discrepancy hard-error budgets for each comparison.
- `review_documents`: M26.16 optional documents that require **manual independent authentication**, not auto-acceptance.

Valid **synthetic** examples for the exact config structure are in `tests/physics/test_m26_campaign_cli_review.py`; these examples are *not* physical observations.

## M26.15 — One-command read-only dossier runner

```bash
python scripts/run_frozen_flight_campaign.py \
  --original-root /evidence/immutable-original-files \
  --source-manifest-json /metadata/source_manifest.json \
  --source-manifest-sha256 <actual-64-char-sha256> \
  --campaign-json /metadata/frozen_campaign.json \
  --campaign-sha256 <actual-64-char-sha256> \
  --output /reports/new_dossier.json
```

This runs M26.14 input byte locking, replays M26.13 numerical errors / hard physical limit / uncertainty budget calculations from real local files, and appends M26.16 evidence gaps. It **never writes to the original source folder, source manifest, configuration, frozen prediction files, or supplied review documents**, and refuses to overwrite any pre-existing report.

**Exit codes:** `2` input/technical error; `3` recorded critical numeric or operator-declared physical hard-limit failure; `4` missing independent evidence / physically inconclusive. No exit code or JSON flag represents authenticated physical validity. The JSON contains the full conditional dossier plus source/pin hashes and a reproducible report hash.

## M26.16 — External evidence and reviewer readiness gap audit

`physics.validation.external_flight_evidence_gaps.audit_external_flight_evidence_gaps` computes a missing-evidence checklist for eight necessary external evidence families:

1. Original recorder custody and laboratory test chain.
2. Dataset license or source permission.
3. Serial and revision matching of actual installed components.
4. Instrument calibration and uncertainty certificates.
5. Independently established clock synchronization.
6. Historically authenticated preregistration and previously blinded holdout splits.
7. Independent competent engineering review.
8. Applicable operational safety authorization.

An operator can attach documents outside the immutable original file root. The software checks **actual local document bytes** against supplied hashes and rejects duplicate kinds, symlinks, invalid bytes and missing files. Crucially, even if all eight document types are present, the software **never decides whether their contents, issuers or historical claims are genuine**. The result therefore remains `INCONCLUSIVE_EXTERNAL_PHYSICAL_VALIDATION_NOT_ESTABLISHED` (or `FAIL_CRITICAL_ANALYTIC_OR_OPERATING_LIMIT_SCREEN` if numerical/hard-limit checks fail) and all `physical_validation_accepted` and `flight_or_manufacturing_release_authorized` fields stay false.

## Tests, required external action and scope

```bash
python -m pytest tests/physics/test_m26_campaign_cli_review.py -q
python -m pytest -q
```

Regression tests cover pristine synthetic data, tampered frozen JSON, duplicate keys, NaN, local hash matches, missing and forged review documents, safe output controls, numerical failures and preventing false success flags.

**The scientific priority is still acquiring usable original independent measurements of compatible physical equipment, not producing more software-only passes.** AeroForge's 60 kg simulated hexacopter is not flight-certified, and the known single-motor-out simulation failure remains a failure. Keep [GitHub Issue #16](https://github.com/god88844-hub/aeroforge/issues/16) open until independently reviewed physical measurements and blind original holdouts pass preregistered acceptance criteria. This software release does **not** reduce the ten unfinished M21–M30 major scientific/product acceptance families.
