# M28.5 — Conservative 3D rotor swept-cylinder nonintersection

Implements `physics.structures.swept_cylinder_clearance.screen_3d_rotor_swept_envelopes`.

For rotors with **explicitly assumed body-Z-parallel axes only**, represent each full rigid swept blade envelope as an axial solid cylinder with radius `(declared_diameter + absolute_hard_diameter_error)/2` and full declared worst-case swept height. The operator must separately provide worst-case Euclidean XY center-position error bounds, absolute Z center-position error bounds, a source for all dimensions, axis-alignment source, and required minimum 3D clearance.

For rotor pair (i,j), subtract the combined XY position error from XY center separation, combined Z error from vertical center separation, and subtract maximum cylinder radii/half-heights. Let `gxy` and `gz` be signed conservative axial/radial gaps. The conservative 3D distance between the two assumed swept cylinders is `hypot(max(0,gxy), max(0,gz))`. A positive distance meeting the declared threshold is an *analytical nonintersection within provided assumptions*. If both gaps are nonpositive, intersection or contact is possible and the screen blocks a positive conclusion.

This can resolve a pair whose XY disks overlap but whose **justified** Z separation exceeds full swept blade-height bounds. It does not infer or guarantee that declared swept heights actually cover blade bending, flapping, tilt, thermal growth, mounting vibration, servo motion or worst-case operating conditions.

**Not a CAD or flight validation:** Any unknown tilted-axis model is unsupported. This method does not check blade/frame/landing-gear collision, non-parallel rotor trajectories, real as-built geometry, aerodynamic interaction or component failure. Inputs are operator-claimed and unauthenticated. `original_as_built_measurements_authenticated=false`, `actual_dynamic_rotor_3d_clearance_validated=false`, and `flightworthiness_established=false` on all outcomes.

```bash
python -m pytest tests/physics/test_swept_cylinder_clearance.py -q
python -m pytest -q
```

This is M28.5 *software analysis only*. Independent actual hardware geometry and test evidence remain required before any physical clearance decision.
