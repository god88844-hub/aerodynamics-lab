# M28.6 — Orientation-independent rotor outer-envelope separation screen

Function: `physics.structures.rotor_sphere_clearance.screen_orientation_independent_rotor_envelopes`.

M28.5 provides a tighter two-cylinder check only for body-Z-parallel axes. M28.6 makes a deliberately more conservative **orientation-independent** bound: any assumed rigid right circular swept cylinder, centered on its own geometric center and with **hard-bounded maximum** diameter `d+δd` and height `h`, lies entirely inside a sphere of radius `hypot((d+δd)/2,h/2)`, regardless of cylinder orientation.

For each rotor, center movement error is bounded by `hypot(u_xy,u_z)` given a Euclidean XY center-error hard bound and absolute Z error hard bound. For each rotor pair, a conservative separation lower bound is `max(0, Euclidean_nominal_center_distance - radius_i - radius_j - center_error_i - center_error_j)`. The analytical check reports a positive gap only if the lower bound is strictly positive and meets the user's declared minimum. Sphere overlap results in **unknown potential collision**, even when the more precise geometry could still fit: this is a sufficient nonintersection screen, not an exact collision solver.

All dimensions and error bounds must be finite, nonnegative, explicitly sourced, and include true maximum rotor center travel if rotor tilt pivots displace the geometric center. This code does not establish the validity of those assumptions or sources, blade flex/flapping/vibration limits, surrounding airframe clashes, genuine 3D CAD clearances, or actual as-built measurements. The response never claims aircraft flightworthiness or physical collision testing.

Synthetic tests: `python -m pytest tests/physics/test_rotor_sphere_clearance.py -q`. Real-world equivalence and actual rotor clearance remain unproven.
