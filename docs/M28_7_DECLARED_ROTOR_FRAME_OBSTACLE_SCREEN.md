# M28.7 — Conservative rotor-to-declared-frame obstacle clearance

Implements `physics.structures.rotor_obstacle_clearance.screen_rotor_to_obstacle_spheres`.

The M28.6 enclosing-sphere rotor bound now supports explicitly represented **nonrotor obstacles** (body, landing gear, payload, antennae, braces, etc.). Each provided obstacle must be enclosed within an operator-declared rigid sphere, with absolute center-position and radius hard uncertainty bounds. Rotor envelopes are also modeled as enclosing spheres based on installed diameter, full swept height, center travel and diameter uncertainty bounds. The pairwise lower bound on 3D separation subtracts both outer radii and every declared center/radius uncertainty from the nominal Euclidean center distance. A strictly positive lower gap meeting a declared threshold can only establish analytical separation of these assumed envelopes.

**Critical:** Omitting a part from the operator-supplied obstacle inventory means it is NOT checked. The software does not claim that all parts have been registered, and the return always says `obstacle_inventory_completeness_authenticated=false`. Missing/duplicated obstacle records, nonfinite/mismatched values and arithmetic overflow cause refusal rather than a safe verdict. Even for a positive calculated gap, actual assembly collision validation and flightworthiness are unproven.

This screen is conservative, read-only, and is **not** full CAD clash detection, dynamic blade deflection testing, physical interference measurements or airworthiness evidence. Synthetic tests: `python -m pytest tests/physics/test_rotor_obstacle_clearance.py -q`. Unmeasured actual geometry remains a hard blocker.
