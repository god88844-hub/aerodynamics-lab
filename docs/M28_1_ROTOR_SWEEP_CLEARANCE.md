# M28.1 — Projected rotor-tip sweep clearance (software screen)

**Scope:** analytic first-stage multirotor editing/assembly check, not real CAD clash detection or independent physical validation. Implements `physics.structures.rotor_clearance.evaluate_rotor_sweep_clearance`.

Given declared rotor body-frame centers `(x_i,y_i,z_i)`, declared installed propeller diameters `d_i`, and user-declared required tip clearance `c_min`, each projected XY disk pair has margin

```
c_ij = hypot(x_i-x_j, y_i-y_j) - (d_i+d_j)/2
```

Any `c_ij <= 0` reports `PROJECTED_DISK_TOUCH_OR_OVERLAP_POTENTIAL`. A positive gap below `c_min` reports `INSUFFICIENT_DECLARED_PROJECTED_TIP_CLEARANCE`. All projected gaps meeting declared minimum reports `ANALYTIC_PROJECTED_TIP_CLEARANCE_ONLY`. Only the latter gets `screen_passed=true`, and even then *physical-interference validation and aircraft flightworthiness stay false*.

The calculation deliberately **does not waive projected overlap due to rotor height differences**: actual vertical blade thickness, bending, flapping, phase, coaxial layouts, and assembly tolerances are unmodeled. It cannot determine if a different-height system actually collides; it only marks a potential geometric conflict. Every rotor requires an explicit installed diameter with a source, positive finite values, and consistent rotor count. No guessed generic component dimensions.

### Example, synthetic only

```python
from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_clearance import evaluate_rotor_sweep_clearance
result = evaluate_rotor_sweep_clearance(
    design,
    installed_propeller_diameters_m=[0.381,0.381,0.381,0.381],
    geometry_and_diameter_source="Example numbers, not as-built measurements",
    minimum_declared_tip_clearance_m=0.02,
)
```

This is a read-only module, not yet exposed by API/UI. It does not check blade-to-frame or blade-to-landing-gear collisions, CFD interference, transient rotor dynamics, certified tolerances or true installed geometry. The existing quad reference's geometry is estimated and cannot be used as physical build evidence.

### Verification

```bash
python -m pytest tests/physics/test_rotor_clearance.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

This is **M28.1 partial software scope**. Future CAD assembly and qualified geometry measurements remain required for M28 completion and Issue #28.
