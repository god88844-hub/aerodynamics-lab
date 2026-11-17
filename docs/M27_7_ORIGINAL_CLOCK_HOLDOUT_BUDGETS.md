# M27.7 — Original-file verified holdouts + hard clock-error budgets

Provides `physics.validation.original_clock_budgets.audit_original_holdout_clock_budgets`, combining exact raw observation/prediction SHA-256 verification and whole-run disjoint holdout screening from M27.2 with conservative per-sample sensor + clock + signal-rate error bounds from M27.6.

For each whole-run holdout, require the original observation/prediction CSV byte strings and expected SHA-256 digests, a source-declared separate per-sample clock budget keyed by the **same sample ID and exact time** as the original CSV. The raw original measurement hard bound is retained and **cannot be narrowed by the clock-budget metadata**. Compute `|predicted-observed| + sensor_hard_bound + clock_hard_bound*signal_slew_hard_bound` for every original sample, refusing any missing/duplicate run, clock-grid mismatch, altered source bytes, negative/nonfinite uncertainty or poorly bounded residuals. Every holdout must individually satisfy its required coverage; a failed run cannot be hidden through pooled results.

Outputs always retain `clock_calibration_authenticated=false`, `signal_slew_hard_bounds_authenticated=false`, `original_measurement_physical_origin_authenticated=false`, `independent_real_world_fidelity_established=false`, and `flight_release_authorized=false`. This module does not actually calibrate a clock or slew rate, verify acquisition hardware, establish independently witnessed experiment identity or replace required physical validation.

Synthetic-only tests: `python -m pytest tests/physics/test_original_clock_budgets.py -q`. Real source custody and qualified physical experiments remain unresolved in issue #16.
