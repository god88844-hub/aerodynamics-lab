# M26.2 — Complete original-file manifest draft

**Implemented software stage:** `physics.validation.flight_inventory_scaffold.draft_native_flight_manifest` and offline CLI `scripts/audit_flight_evidence_channels.py draft`.

This is an evidence-acquisition and data custody tool. It does not create measurements, retrieve a licensed dataset, authenticate a published recorder, validate an aircraft, or authorize flight.

**What it does:** recursively enumerate *every* actual on-disk original file under a specified evidence directory, require **exactly one explicit operator-provided flight ID, sensor family and source assignment for every actual file**, then hash original bytes as SHA-256 and record byte counts. Any extra/unassigned file, missing file, symlink, traversal attempt, unsupported file extension or invalid recorded source metadata blocks the manifest. Original filenames, native formats and original bytes are preserved. It then runs the M26.1 complete-archive audit again before yielding a manifest.

**What it never guesses:** publisher identity, physical source license, which files belong to which flight, sensor channel names, calibrations, clock origins, instrumentation uncertainty or permission to redistribute. For unknown channels use `[]`; for unknown calibration, clock, source rights or notes use `null`. Use actual official record documentation to fill them later without rewriting the source files.

**Command:**
```bash
python scripts/audit_flight_evidence_channels.py \
  --root /read-only/original-native-files \
  --output /separate/audits/draft.json draft \
  --assignments-json /separate/metadata/explicit_assignments.json
```

The assignments JSON has exactly `archive_id`, `publication_reference`, `archive_record_reference`, `declared_vehicle_identity`, `source_permission`, and `assignments`. Each assignment uses the `relative_path`, `flight_id`, `sensor_family`, `declared_channels`, `calibration_reference`, `clock_reference`, `source_notes` fields. Synthetic runnable examples are in `tests/physics/test_flight_inventory_scaffold.py`. Save metadata **outside** the immutable original source root.

**Acceptance:** all declared on-disk originals match their SHA-256, but this is still self-asserted original file custody, not independent original-data authentication or completed M26 physical validation.
