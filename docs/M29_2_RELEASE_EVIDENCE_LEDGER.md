# M29.2 — Deterministic source-pinned release evidence ledger

AeroForge's primary purpose remains building simulation predictions that can ultimately be compared credibly to independent physical measurements. Software CI, synthetic analytic checks, and original source digest strings **do not** independently establish that equivalence. M29.2 captures a stable operator-supplied evidence inventory and explicitly refuses an automatic flightworthy/physically validated release.

Function: `physics.validation.release_evidence_ledger.index_release_evidence`

Inputs are a fixed model Git SHA, protocol SHA-256, design SHA-256, and 1–200 declared evidence entries. Each entry must identify a distinct source digest and ID, exact matching frozen model/protocol/design, an experiment and physical-group ID, channel, calibration or holdout role, source kind, and source reference. All fields are explicit; unknown validation claims are prohibited. A single original source SHA cannot be reused as a second independent record.

The normalized inventory is sorted by evidence ID and hashed as canonical UTF-8 JSON, making its digest reproducible when entry order differs. Any duplicate original byte SHA, inconsistent frozen identities, malformed IDs, missing roles or calibration/holdout physical group overlap blocks a complete inventory. A minimum of one calibration and two distinct whole-experiment holdouts is required to avoid a basic independence gap.

**Important limits:** The inventory does not read original file bytes or authenticate submitted SHA strings, cannot confirm real measurement provenance, source custody or external preregistration timing, and never computes independently validated drone prediction error. Even an inventory declared complete by an operator always has:

```
source_bytes_cryptographically_checked = false
external_measurement_origin_authenticated = false
release_physical_decision_equivalence_established = false
flightworthiness_established = false
release_authorized = false
```

The only positive status is `OPERATOR_EVIDENCE_INDEX_COMPLETE_NOT_VALIDATED`, explicitly a metadata completeness statement. Any source or physical-group issues produce `OPERATOR_EVIDENCE_INVENTORY_HAS_GAPS`. An independent review, calibrated test chain, frozen protocol, original licensed measurements, and actual-aircraft blind holdouts remain prerequisites for any future real-world validation claim.

Read-only, no flight commands, no physical testing, no component mutations.

Synthetic regression:

```bash
python -m pytest tests/physics/test_release_evidence_ledger.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

Release evidence blocker: issue #16.
