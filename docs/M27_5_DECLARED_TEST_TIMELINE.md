# M27.5 — Declared preregistration and blind-holdout chronology audit

Function: `physics.validation.preregistration_timeline.audit_declared_preregistration_sequence`.

Check exact canonical UTC `YYYY-MM-DDTHH:MM:SSZ` timestamps and source-model/protocol identities across the claimed protocol archive, frozen model, frozen predictions, calibration experiments and whole-run blind holdouts. The internal sequence must have `protocol archive <= model freeze <= prediction freeze < every holdout start`. All calibration must be completed no later than the model freeze, each run start must precede completion, calibration and holdout experiment groups must be disjoint, and the holdout recording identities must match the M27.4 original-source linkage. At least two disjoint holdout runs are required. Format mismatch, duplicate IDs, missing frozen metadata, group collisions and false chronology fail closed.

**Scientific limitation:** Time strings, commit hashes, source labels and archive locations are **operator declarations**. No trusted archive service, clock attestation, calibrated hardware, signed source, third-party preregistration record or truly blind experiment is authenticated by this code. Even an internally consistent timeline returns `DECLARED_SEQUENCE_CONSISTENT_UNAUTHENTICATED`, `archive_timestamp_authenticated=false`, `actual_physical_validation_established=false`, and `release_authorized=false`.

Synthetic tests: `python -m pytest tests/physics/test_preregistration_timeline.py -q`. The global independent physical evidence blocker #16 remains open.
