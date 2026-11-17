# M28.3 — Conservative rotor clearance under declared geometry hard bounds

The existing M28.1 and M28.2 screens only use nominal rotor centers and nominal propeller diameters. This increment gives a conservative *projected XY* clearance **lower bound**, provided that independently established absolute hard geometry bounds are supplied.

For rotor pair (i,j), center-separation nominal XY distance `L_ij`, bound `u_i` on Euclidean XY displacement of installed center i, nominal diameter `d_i` and absolute hard diameter error `delta_i`:

```
L_min_ij = max(0, L_ij - u_i - u_j)
C_lower_ij = L_min_ij - 0.5*(d_i+delta_i + d_j+delta_j)
```

**These must be genuine deterministic hard error enclosures**, not one-sigma estimates or unspecified manufacturing tolerances. Inputs without explicit bounds or provenance are rejected. Every rotor pair must have strictly positive projected lower gap and meet the user's declared minimum required clearance. A nominal clean gap does not override failure in the conservative lower bound.

The result retains immutable design input, per-pair uncertainty decomposition, governing conservative lower clearance and an analytical gate. `source_hard_bounds_independently_authenticated`, `actual_3d_interference_validated`, and `flightworthiness_established` are **always false**.

This is *not* a 3-D mesh collision, propeller flex/flap/sweep, motor mount wobble, landing-gear or body intersection or flight test. Positive results do not yield a success probability. No structural fatigue, aerodynamics, actual hardware calibration or independent empirical accuracy assessment is performed.

Module: `physics.structures.rotor_tolerance.evaluate_bounded_rotor_clearance`. It is read-only and intentionally not yet surfaced as a safety approval endpoint.

Synthetic tests:

```bash
python -m pytest tests/physics/test_rotor_tolerance.py -q
python -m pytest -q
```

M28 remains incomplete for real hardware geometry; independent physical evidence blocker #16 remains open.
