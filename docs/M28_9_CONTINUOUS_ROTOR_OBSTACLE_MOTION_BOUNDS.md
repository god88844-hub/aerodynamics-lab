# M28.9 — Continuous-time rotor-obstacle clearance from sampled hard motion bounds

Implement `physics.structures.continuous_motion_clearance.screen_continuous_motion_clearance`.

For explicitly declared rotor swept cylinders, enclosing sphere radii, obstacles, source references and Euclidean center-position hard errors, calculate a **conservative lower bound for every time between sampled checkpoints**, not just at sample instants. Each rotor and obstacle must have a claimed maximum 3D center speed `v` (m/s) that truly encloses its motion throughout each time interval. For interval width `Δt`, relative center distance is bounded below by `min(distance_at_start, distance_at_end) − (rotor_speed+obstacle_speed)·Δt/2` because every intermediate time is within half an interval of at least one known endpoint. Subtract both conservative enclosing sphere radii and absolute center position error budgets to obtain a nonnegative separation lower bound. Require strictly positive separation above the declared minimum for **every rotor–obstacle pair and every time interval**.

Refuse nonfinite input, missing obstacle or rotor centers, unknown object identifiers, ill-ordered samples, absent provenance, accumulated radius/speed overflow, or sampled position jumps inconsistent with a claimed speed bound after accounting for endpoint hard-position errors. The sample timeline begins at t=0 and has at least two points.

**Limit:** The mathematical guarantee is conditional on genuinely valid continuous-time hard center-speed, shape, height, diameter and position enclosures. An operator may supply incorrect speeds or omit an actual airframe obstacle. This code neither authenticates a physical trajectory nor covers undocumented hardware, flexible blade deformation or flight safety. All physical validation and release flags remain permanently false.

Synthetic regression: `python -m pytest tests/physics/test_continuous_motion_clearance.py -q`. No real rotor collision test is provided.
