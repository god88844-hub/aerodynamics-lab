# M29.4 — Explicit per-decision engineering error coverage ledger

Function: `physics.validation.decision_coverage.assess_decision_metric_coverage`.

Cross-link M27.5's declared timeline, M28.6's orientation-independent bounding-sphere geometry and M29.3's preflight report for an explicitly enumerated set of **decision-critical metrics**. Every critical metric must have a unique operator-reported whole-run hard-error maximum, claimed predeclared allowable error, claimed number of disjoint holdout groups and an operating-envelope inclusion flag. Any missing or duplicate decision metric, nonfinite quantity, too few holdouts, exceeded tolerance, out-of-envelope condition, inconsistent frozen model SHA/design identity, failed prior preflight or failed geometry blocks the *operator-reported software preflight* status. Results have a deterministic canonical SHA-256 summary stable under input order.

A positive `OPERATOR_DECISION_COVERAGE_CONSISTENT_UNVERIFIED` only means operator-supplied numeric gates appear mutually consistent. It does not authenticate original measurement values, model predictions, experimental independence, preregistration timing, controlled conditions or genuine physical error distributions. The required critical metric list itself is operator-declared and could omit real failure modes. Thus `independent_physical_metric_coverage_authenticated=false`, `real_world_equivalence_demonstrated=false`, `design_airworthiness_established=false`, and `production_or_flight_release_authorized=false` are unconditional.

Synthetic tests: `python -m pytest tests/physics/test_decision_coverage.py -q`. Real-world evidence blocker #16 remains open. Never substitute the result for qualified external tests.
