# M28.10 — Continuous-time pairwise rotor swept-envelope clearance

`physics.structures.continuous_rotor_pair_clearance.screen_continuous_rotor_pair_clearance` extends the conservative M28.6 arbitrary-rotor-orientation enclosing-sphere model to **all times between operator-supplied trajectory samples**. It checks every pair of 2–32 rotor swept volumes, not only time-sampled placements.

Each rotor has an installed diameter, a full maximum swept height, a hard diameter error bound, a 3D Euclidean rotor-center-position error bound, and a maximum center-speed hard bound. For each sampled time interval `Δt`, each unknown interior instant lies within `Δt/2` of at least one endpoint. Therefore a conservative rotor-pair distance lower bound is `min(D_start,D_end) - (V_i+V_j)*Δt/2`, minus both entire enclosing sphere radii and declared center errors. Require strictly positive remaining gap above the declared threshold for **every pair**; any uncertain contact blocks a positive screen. The implementation also rejects sampled center jumps impossible under claimed speed limits even after allowing endpoint position errors.

**Assumptions:** Valid only if rigid swept-cylinder dimensions truly bound entire swept motion under arbitrary orientation and declared center speed/position bounds are deterministic upper enclosures across the specified finite horizon. No blade flex, missing airframe objects, unmodeled pivot movement, real as-built dimensions or independent calibration are checked. A positive analytical result is not actual flight clearance validation, aircraft reliability or airworthiness.

Synthetic-only gate: `python -m pytest tests/physics/test_continuous_rotor_pair_clearance.py -q`. Real geometry/flight evidence remains required.
