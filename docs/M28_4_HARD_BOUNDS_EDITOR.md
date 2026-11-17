# M28.4 — Rotor clearance hard-bound API and editor

Provides a read-only UI/API to evaluate projected XY rotor clearance under **explicit worst-case absolute geometry bounds** using M28.3's formula. The caller supplies exact current drone design, one installed diameter per rotor, one Euclidean XY center-position displacement **hard bound** per rotor, one absolute propeller diameter **hard bound** per rotor, two provenance strings and a minimum projected clearance.

**Endpoint:** `POST /api/components/bounded-rotor-clearance`.

**Editor:** Rotor geometry hard bounds, under design-side structural screens. Changing input clears previous result.

A result can only indicate *analytical agreement with declared assumptions* and never authenticates physical measurements. Missing, negative, nonfinite, inconsistent and untraceable inputs fail closed (HTTP 422). The backend reports `actual_3d_interference_validated=false`, `source_hard_bounds_independently_authenticated=false`, and `flightworthiness_established=false` regardless of a positive analytical margin.

This is not real CAD mesh interference checking, dynamic blade movement, as-built manufacturing tolerance measurement, nor real-world flight approval. No simulation physics or stored design changes.

Run synthetic regression gates:

```bash
python -m pytest tests/physics/test_rotor_tolerance.py tests/integration/test_rotor_tolerance_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

Physical evidence issue #16 remains unresolved.
