# AeroForge M26.5–M26.7 — Original-file completeness, bounded sensor alignment and independent holdout preparation

These three software phases extend merged M26.1–M26.4. They **do not** add, create, guess or authenticate any actual physical flight observations. Source truth, clock and calibration error bounds, flight identity, preregistration history, model generalization and hardware compatibility require separate independent review. Physical-validation blocker [#16](https://github.com/god88844-hub/aeroforge/issues/16) must remain open.

## M26.5 — Whole-archive completeness gate

`physics.validation.source_completeness.audit_source_completeness(root, manifest)` verifies the actual on-disk file set before and after a complete original-file SHA-256 audit, rejecting unmanifested files, absent originals, unsafe symlinks/special entries, and byte-identical streams assigned to allegedly separate flights. It returns an order-stable SHA-256 manifest fingerprint, complete declared flight list, and missing calibration, clock and channel metadata. This is a best-effort read-only filesystem consistency check, **not an atomic filesystem snapshot** or secure chain of custody. A malicious local party controlling both the files and their claimed hashes can still manufacture an internally consistent archive.

## M26.6 — Conservative same-flight multi-sensor alignment

`physics.validation.flight_clock_alignment.audit_same_flight_clock_alignment` accepts two **different original single-channel CSV files** and explicit clock transforms into one claimed shared clock. It revalidates complete archive bytes, requires identical flight IDs, exact channel names/units, nonempty reported calibration/clock references, increasing original timestamps and acceptable source sample gaps.

Given operator-declared clock offsets `o_a,o_b`, hard timing errors `u_a,u_b`, and original times `t_a,t_b`, an original-sample pair is accepted only when:

```
|(t_a + o_a) - (t_b + o_b)| + u_a + u_b <= maximum_joint_time_difference_s
```

Pairing proceeds monotonically and never reuses a row, inserts a sample, interpolates a channel or rewrites original evidence. Fewer than five allowable unique pairs or unknown/contradictory source timing returns a blocked or inconclusive result. The clock offsets, worst-case timing errors and actual synchronization remain unauthenticated operator statements; passing the numerical screen does not independently prove a synchronized measurement was made. The greedy two-pointer pairing is a **sufficient algorithm**, not a maximum-cardinality alignment algorithm. Only exact original CSV source format is supported; original TDMS/MAT files need a separately audited decoder.

## M26.7 — Frozen whole-flight holdout preflight

`physics.validation.flight_holdout_preflight.prepare_whole_flight_holdout_manifest` validates reported frozen Git model SHA, frozen protocol SHA-256, preregistration UTC and freeze UTC, and operator-declared flight-level partition records. It verifies all original file bytes and complete source inventory through M26.5, requires each declared flight to appear once in a calibration or holdout partition, disallows mixing calibration and holdout within one declared experiment group, requires at least one calibration group and two independently *declared* holdout groups, binds each flight to an actual SHA-256 from the original manifest, and refuses holdout reveal timestamps before the reported protocol/model freeze.

The output is an order-stable checksum and an explicit list of heldout groups, not proof that a pre-registration existed or that developers were blind to the observations. A model trained on this dataset **cannot retroactively be declared independently blind** merely because a later file contains an earlier self-reported timestamp. Real independence requires third-party timestamped evidence, hardware provenance, prior model freeze and genuine independent source custody.

## Synthetic CI and next physical requirements

```bash
python -m pytest tests/physics/test_m26_integrity_sync_holdout.py -q
python -m pytest -q
```

Tests use invented **synthetic fixture bytes** only, intentionally keeping `physical_measurements_validated`, `actual_independent_prediction_validation_completed` and all flight release flags false. These phases do not reduce the number of outstanding major acceptance milestones (M21–M30).

Next scientific action remains to obtain the legally accessible, original recordings of the [TU Braunschweig P80III quadcopter study](https://leopard.tu-braunschweig.de/receive/dbbs_mods_00070168) with verified licenses, instrument calibration, original clocks, physical hardware identity, and independent experiment custody; independently benchmark the exact applicable flight channel/regime only after validation.
