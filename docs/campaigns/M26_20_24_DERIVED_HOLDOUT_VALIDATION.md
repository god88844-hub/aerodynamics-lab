# M26.20–M26.24 — Provenance-aware derived flight measurement validation

**Scientific scope: software preflight only.** This batch connects the original-instrument CSV conversions from M26.17–19 to frozen simulation prediction comparisons. It never relabels a converted file as original physical evidence. It cannot authenticate a real experimental recording, sensor calibration, aircraft hardware serials, prior blindness or a safe flight release.

## Five implemented steps

**M26.20 — Replay and admit a derived channel.** `derived_observation_admission.admit_derived_observation` replays the original-byte-linked conversion and checks exact engineering channel, source/derived hashes, original declared clock/calibration references and bounded observed sample gaps. Source labels are explicitly *derived*, not instrument-original. Missing clock/calibration references remain blockers.

**M26.21 — Declared aircraft and test-condition compatibility.** `derived_hardware_screen.screen_declared_hardware_match` checks aircraft type, installed rotor count, motor, propeller, ESC, battery pack, mount, takeoff mass and ambient temperature against an explicit reference. Any mismatch marks the proposed full-vehicle comparison incompatible. Names and mass comparisons are only operator claims; actual serials/assembly are not authenticated. In particular, a published 25 kg quadcopter is not the AeroForge 60 kg hexacopter.

**M26.22 — Source-replayed frozen prediction residuals.** `derived_holdout_comparison.compare_derived_holdout` checks that the original source is a declared whole-flight holdout, replays conversion, rehashes the frozen prediction CSV, and demands identical source/prediction timestamps and sample counts. It directly calculates RMSE, hard-error-bounded residual and robust interval coverage. No interpolation, backfilled samples, unit guessing or self-reported “pass” flags. A conditional numerical pass does **not** establish physical validity.

**M26.23 — Distinct declared holdout groups.** `derived_holdout_coverage.audit_derived_holdout_group_coverage` recomputes each comparison and counts distinct reported experimental groups for a single regime and channel. Missing groups are inconclusive; any failed declared critical metric overrides missing coverage. Duplicate source/prediction paths cannot count twice. The origin and independence of the physical flights remain unverified.

**M26.24 — Reproducible conditional dossier.** `derived_flight_dossier.build_derived_flight_dossier` combines M26.21 compatibility and M26.23 recomputed group-level error/coverage results. A failed declared numerical metric overrides mere incompatibility, incompatibility or missing holdouts block a conditional numerical result, and positive output is explicitly labeled **external evidence missing**. A canonical digest binds source, conversion and prediction hashes, hardware settings and conditional metrics. Release and physical-equivalence flags remain false.

## Verification

```bash
python -m pytest tests/physics/test_m26_derived_holdout_dossier.py -q
python -m pytest -q
```

All fixtures are **synthetic data made for regression testing**, never actual external flight measurements. The next indispensable step is obtaining licensed original measurements and independently verifying source custody, instruments, timebases, installed hardware and a genuinely frozen blind model. The scientific physical-validation blocker [#16](https://github.com/god88844-hub/aeroforge/issues/16) remains open.

This batch implements five numbered **software subphases**, not five independently completed top-level scientific acceptance milestones. The ten original M21–M30 major acceptance families remain outstanding through Drone v1.
