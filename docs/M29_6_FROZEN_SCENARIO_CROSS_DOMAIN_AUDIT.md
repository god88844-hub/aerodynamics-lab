# M29.6 — Frozen-scenario source-to-geometry-to-solver consistency gate

Provides `physics.validation.frozen_scenario_coverage.assess_frozen_scenario_coverage`. Integrates four **operator-reported** inputs against an explicit frozen model Git SHA, design name, critical channel and intended operating-envelope identifier:

1. **M27.7** original source byte + clock/slew hard-bound holdouts: at least two distinct experimental groups, matching channel/model, and no raw-run gate failure.
2. **M28.8** exact operator-declared obstacle inventory and assumed analytic rotor-to-obstacle sphere clearance for the same design.
3. **M29.5** conditional three-grid numerical solver convergence report for the same model/channel.
4. **M29.4** a complete reported critical-decision coverage record for that channel with a matching number of holdout groups and declared envelope inclusion.

A decision metric that reports a *smaller* worst conservative hard error than the linked raw clock/sensor-bounded holdouts is inconsistent and explicitly rejected. Any missing domain or failed flag produces `OPERATOR_FROZEN_SCENARIO_AUDIT_BLOCKED`. Numerically consistent self-reported evidence produces only `OPERATOR_FROZEN_SCENARIO_AUDIT_CONSISTENT_UNVERIFIED`, with a reproducible source-label snapshot digest.

**No physical assurance:** The four submitted reports are not re-executed or cryptographically authenticated here. Even all-green reports might be fabricated. The result always reports `physical_source_attestation_verified=false`, `real_assembled_aircraft_geometry_authenticated=false`, `real_world_predictive_accuracy_validated=false`, `engineering_airworthiness_established=false` and `production_or_flight_release_authorized=false`. No real-world physical validation, product safety approval or success probability is implied.

Synthetic-only tests: `python -m pytest tests/physics/test_frozen_scenario_coverage.py -q`. Issue #16 remains the external independently measured evidence blocker.
