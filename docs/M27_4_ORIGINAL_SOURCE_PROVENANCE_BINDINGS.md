# M27.4 — Byte-verified holdout-to-ledger provenance reconciliation

Implements `physics.validation.provenance_bindings.audit_provenance_bindings`. Integrates M27.2 original UTF-8 CSV digest verification and identical sample/time-grid checking with M29.2 deterministic frozen source inventory reconciliation. Each held-out run must identify one observation and one independently hashed frozen prediction file in the ledger. Both entries must match their exact original SHA-256 digest, whole experiment/group ID, channel, role and frozen model/protocol/design identity. No source can be used for two independent original holdouts.

The observation source label is `reported_physical_measurements`, while the prediction source is `software_verification`. These are **operator labels**, not evidence of actual experiments or a trustworthy simulator; the regression fixtures deliberately spoof physical origin. Any mismatched original digest, repeated reference, group identity, run/source assignment, or holdout numerical acceptance gate causes refusal or a failing report.

**Security and scientific limits:** Comparing supplied file bytes to supplied hashes establishes only exact byte/manifest consistency. The software does not trust a cryptographic key, validate a signed attestation, confirm calibration certificates or timestamps, check capture-device identities, or establish the origin of a purported physical measurement. Every result states `external_physical_source_authenticity_established=false`, `external_preregistration_or_independence_authenticated=false`, `simulation_equivalent_to_physical_validation=false`, and `release_authorized=false`.

M27.4 provides **read-only standalone Python audit logic**; no live GitHub CI or hardware instrumentation is created.

```bash
python -m pytest tests/physics/test_provenance_bindings.py -q
python -m pytest -q
```

M26 physical flight evidence and the overarching independent validation blocker #16 remain outstanding.
