# M29.3 — Cross-domain evidence/release preflight

Implements `physics.validation.release_readiness.assess_release_readiness`.

Combine **operator-reported** M27.4 original-file/ledger cross-links, M28.5 assumed 3D rotor swept-cylinder analytical screen, and two named claimed GitHub CI checks (`python-tests` and `web-build`). Strictly compare frozen model Git SHA and ledger SHA-256 across the original provenance report and review snapshot. Reject missing job names, nonboolean states, mismatched model/digest, incomplete provenance, unknown design identity and absent geometry pair data. Create an order-independent canonical SHA-256 fingerprint of the sanitized preflight snapshot.

The only software-positive state is `REPORTED_SOFTWARE_GATES_CONSISTENT_EXTERNAL_VERIFICATION_REQUIRED`. This is self-reported **consistency**, not a trusted CI status or an engineering approval; any negative subgate yields `REPORTED_RELEASE_PREFLIGHT_BLOCKED`. The preflight does not use GitHub's authenticated check-run API or external measurement authority, and it does not verify the provenance snapshots were produced by their modules. An attacker could supply fabricated report flags. Such flags never make it safe to release.

Every result, including numerically perfect assumed cases, explicitly states:
- `ci_status_cryptographically_authenticated = false`
- `physical_source_authenticity_established = false`
- `independent_flight_prediction_validated = false`
- `design_decision_equivalent_to_physical_validation = false`
- `manufacturing_or_flight_release_authorized = false`
- `release_authorized = false`

The blocked manufacturing/flight release is the deliberate safe behavior. Actual independent physical validation, expert review, calibrated hardware, authenticated original custody, and qualified approvals remain external blockers in issue #16.

```bash
python -m pytest tests/physics/test_release_readiness.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

No flight commands, component mutations, automatic approvals, or claimed physically certified drone designs are included.
