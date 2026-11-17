# M29.5 — Three-grid numerical solver convergence diagnostics

Implements `physics.validation.three_grid_convergence.audit_three_resolution_convergence`.

Given explicitly declared frozen model Git SHA, solver order `p`, coarse timestep `h`, fixed refinement ratio `r>=2` and *same-sampled-time* predictions from three alleged independent runs at steps `h, h/r, h/r²`, the screen calculates `D1=|u_h-u_h/r|`, `D2=|u_h/r-u_h/r²|` and the observed difference ratio `D1/D2`. An asymptotic order-p regime predicts `r^p`. Only samples with observed ratio within the declared bounded relative tolerance of `r^p` and conditional fine-grid Richardson error estimate `D2/(r^p-1)` below the declared threshold may pass. Inconclusive zero differences, missing samples, unknown order and any overflow are fail-closed.

**Limitations:** This compares **supplied** numerical values and does not run the solver itself; no verification that the declared nominal timestep, solver order, common observation times or the as-built code commit match is performed. A model can converge perfectly to an incorrect physics solution; even convincing convergence is never equivalent to independent measured physical validation. Reported numerical convergence is not a safety or airworthiness certification.

Synthetic tests: `python -m pytest tests/physics/test_three_grid_convergence.py -q`. The real-world evidence blocker remains issue #16.
