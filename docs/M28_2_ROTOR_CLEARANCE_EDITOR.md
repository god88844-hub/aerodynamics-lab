# M28.2 — Rotor clearance API and editor evidence panel

Implements the existing M28.1 projected rotor-tip clearance calculation as a strictly input-validated, read-only API and editor panel.

- `POST /api/components/rotor-clearance-screen` accepts current `DroneDesign`, **one positive finite installed propeller diameter in metres per rotor**, `geometry_and_diameter_source`, and an explicit nonnegative minimum projected clearance in metres.
- The current editor panel requires explicit inputs; it does **not** infer installed propeller diameters from visual rendering, estimated parts or marketing names.
- Uses the unchanged M28.1 projected XY disk screen to report all rotor pairs, minimum clearance and source-declared status.
- A projected collision or insufficient gap cannot be approved. An analytically within-declared-gap result is **not** physical CAD interference validation or flight safety.
- Source and hardware identities are operator-declared, not independently authenticated.
- No mesh/CAD intersection, blade deflection, dynamic clearances, vertical 3D blade collision, support-structure clashes, load-bearing frame verification, or actual measured aircraft clearance tests are provided.
- Neither saved designs nor flight simulation coefficients are modified.

Synthetic-only regression gates:

```bash
python -m pytest tests/physics/test_rotor_clearance.py tests/integration/test_rotor_clearance_api.py -q
python -m pytest -q
cd apps/web && npm ci && npm audit --audit-level=moderate && npm run build && npm test
```

M28.2 is a partial editing/geometry workflow. Physical decision-equivalence and M28 completion remain blocked by exact installed geometry and independent full-aircraft tests. Do not merge before exact-head Python + web CI and post-merge main verification.
