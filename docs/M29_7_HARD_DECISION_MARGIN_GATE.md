# M29.7 — Conservative critical decision margins under explicitly declared hard uncertainties

Implement `physics.validation.decision_hard_margins.audit_hard_bound_decision_margins`.

Require a single frozen model/protocol and the M29.6 operator-reported frozen-scenario consistency snapshot (matching model, design, channel). For every explicitly listed decision-critical failure threshold, declare the predicted value and whether physical failure occurs by exceeding a maximum or falling below a minimum; also supply separate conservative absolute **hard** error budgets for model-form discrepancy, numerical discretization, input parameters, geometry and measurement, with explicit provenance.

Calculate `U_total = U_model + U_numerical + U_inputs + U_geometry + U_measurement`. Define the nominal distance to failure on the appropriate side of the stated threshold and subtract `U_total`. A strictly positive remaining hard margin means the operator's stated predicted interval would not touch the stated failure boundary **if every source and hard enclosure were valid**. Any missing/duplicate/foreign-channel decision, inconsistent scenario identity, nonfinite/negative uncertainty, arithmetic overflow or nonpositive residual margin causes a negative or rejected analytical screen. This is a deliberately conservative deterministic sufficient condition; it does not produce a failure probability.

**No physical release:** There is no independent proof that model-form uncertainty is a real hard bound, that all physical failure modes are enumerated, that input and measurement budgets were calibrated, or that a future aircraft matches this design. A passing analytical margin is explicitly **not** physical experiment equivalence, a reliability guarantee or flight authorization. All real-world certification and release fields are permanently false.

Synthetic regression: `python -m pytest tests/physics/test_decision_hard_margins.py -q`. Independent real-aircraft data are still required to approach physical decision equivalence.
