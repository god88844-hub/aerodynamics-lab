# M20 — Exact-hardware preregistration and uncertainty readiness

## Scientific objective

AeroForge's primary objective remains *near-real-world predictive accuracy of simulation under independently demonstrated operating envelopes*, with quantitatively bounded model discrepancies. **Software verification is not physical validation.** M20 provides a reproducible protocol-readiness audit for that evidence campaign, but does not measure a real rotorcraft, authenticate an instrument, approve physical testing or certify any aircraft.

The [M20 physical-experiment requirement](https://github.com/god88844-hub/aeroforge/issues/21) and [source-data blocker #16](https://github.com/god88844-hub/aeroforge/issues/16) cannot be closed solely because this code passes tests.

## What the protocol records

- Intended decision, immutable model Git SHA, design SHA-256 and flight-controller configuration SHA-256; independently archived preregistration evidence must exist **before physical data are revealed**.
- Exact physical frame, motor, propeller, ESC, battery and controller identities, quantities, serial/lot IDs and firmware/geometry revisions. Relevant sensors and payloads may be registered too.
- Bounded temperature, air density, wind, payload and altitude envelopes.
- For each decision-critical quantity: explicit SI unit, **predeclared** maximum absolute prediction error, minimum holdout samples and maximum allowable sampling interval.
- Instrument manufacturer/model/serial, calibration record and date, bandwidth and clock alignment bound.
- Source-identified contributions to measurement uncertainty. Distinguish *hard absolute bounds* from *standard uncertainties*. A standard deviation does **not** imply a deterministic hard error bound. No uncertainty contribution is automatically authenticated or treated as a certificate.
- Independent whole-experiment calibration and blind-holdout partitions. The default conservative gate requires at least one calibration and two separately identified holdouts, with disjoint recording, experiment, battery and vehicle IDs. Alternative same-vehicle designs require a separate, independently reviewed protocol.
- References to solver numerical convergence, preregistration archive, qualified safety review and external technical reviewer. **Their existence/authority is user-declared only.**

This schema is strictly validated: duplicate metrics/instruments/source terms/experiment IDs, invalid hashes, unphysical operating intervals, negative uncertainty, missing required protocol entries, unsupported imported telemetry, sampling limits and group collisions block readiness.

## Deterministic protocol hash

`protocol_sha256()` takes the normalized schema, serializes its JSON with sorted keys, compact separators, UTF-8 and finite values, and computes SHA-256. Supply `expected_frozen_sha256` from a separately archived preregistration; missing or changed digests block readiness. This is an integrity check, **not cryptographic proof of author identity, approval or preregistration time**.

## Measurement uncertainty

The reported worst-case hard measurement bound is the sum of separately declared *absolute hard bounds* on the same output channel. If the total bound consumes the entire acceptable prediction-error limit, M20 blocks a readiness conclusion. Any ordinary statistical/standard uncertainty causes a separate missing-coverage-model warning; it is **not** converted to a guaranteed measurement error bound. A future experimental analysis must address correlations, traceable calibration, clock drift, uncertainty propagation, solver/model-form error and actual validation coverage.

Instrument bandwidth checks are only minimal consistency checks, not guarantees that measured dynamics are faithfully resolved.

## M19 integration

The read-only endpoint `POST /api/components/validation-protocol-audit` accepts:

```json
{
  "protocol": { "schema_version": "1.0" },
  "expected_frozen_sha256": null,
  "imported_manifests": []
}
```

This snippet is a **request-shape illustration, not a valid complete protocol**. For a full synthetic example of every required field, see `tests/physics/test_validation_protocol.py`, and replace all illustrative references with original real-world evidence before using it for engineering.

Optional M19 `TelemetryManifest` declarations are checked against the locked planned recording, experiment, battery and vehicle IDs; source type, sample count, required channels, and sampling constraints. They do **not** cause the original CSV bytes to be loaded or authenticated here. To verify actual data bytes and timing, run the separate M19 source audit. Neither tool fits or modifies a physics model.

The right-hand application pane now contains a preregistration audit that takes the full JSON and optional frozen hash and M19 manifest list; it displays all blockers and never a false physical-validation green light.

## CLI

```bash
python scripts/audit_validation_protocol.py --protocol registered_protocol.json \
  --expected-sha256 FROZEN_SHA256 \
  --manifests original_m19_manifest_list.json --output protocol_audit.json
```

Exit 0 means only that the **declared metadata passed this software audit**. Exit 2 means gaps/invalid input. It is not approval to conduct experiments, and never a claim of aircraft readiness.

## Verification

```bash
python -m pytest tests/physics/test_validation_protocol.py tests/integration/test_validation_protocol_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

All M20 unit/API/UI test fixtures are **synthetic**, including deliberately adversarial metadata labelled `reported_physical_measurements`. They test non-promotion of self-reported sources, not experimental outcomes. A result can reach `OPERATOR_DECLARED_PROTOCOL_COMPLETE_EXTERNAL_REVIEW_REQUIRED`, but the status `independently_approved`, `independent_physical_accuracy_demonstrated` and `decision_equivalent_to_physical_testing` **always remain false** in this module.

## Remaining physical-validation evidence

Before **any** near-real-world decision-equivalent prediction claim: precommit actual exact-platform models and error budgets, obtain instrumented pack/motor/ESC/propeller and controlled flight datasets under qualified supervision, verify hardware and source chain of custody, register genuinely independent holdouts, calculate actual blind model-vs-measured error with uncertainty and assess every decision-critical failure mechanism. Out-of-envelope conditions must remain unvalidated.
