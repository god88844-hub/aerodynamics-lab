# M27.6 — Conservative clock and sensor uncertainty in validation residuals

Implements `physics.validation.clock_residual_bounds.audit_clock_bounded_residuals`.

For each time-ordered observation, supply a prediction and recorded observation, a **deterministic absolute sensor error bound** `u_y`, a hard clock synchronization/timestamp offset bound `u_t` in seconds, and an absolute bound `L` on the true observable's rate of change over the **entire possible shifted time interval**. The conservative residual bound is `|prediction - observation| + u_y + L*u_t`. This follows from the Lipschitz inequality; it is not a statistical confidence interval or a physical measurement of fidelity.

The results report per-sample conservative bounds, the maximum, and the fraction meeting an explicitly provided allowable error. Nonfinite inputs, missing provenance, nonincreasing timestamps and uncertainty overflow fail closed. No parameter fitting, time interpolation, clock shifting or data mutation takes place.

All bound sources are **user-supplied**. The module does not check actual hardware synchronization, sensor delay, drift calibration, logger timing or whether the rate-of-change bound covers the whole offset interval. It never independently authenticates physical measurements or grants flight approval, even for perfect mathematical inputs.

Synthetic tests: `python -m pytest tests/physics/test_clock_residual_bounds.py -q`. Issue #16 remains the independent physical-evidence blocker.
