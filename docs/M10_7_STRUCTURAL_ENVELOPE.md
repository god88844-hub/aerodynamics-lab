# M10.7 — Explicit structural load-case laboratory (analytical verification)

Endpoint: POST /api/designs/structural-envelope

Input:
```json
{
  "snapshot": "<complete DroneDesign object>",
  "cases": [
    {"name": "defined-hover", "thrusts_n": [9.1,9.1,9.1,9.1]},
    {"name": "defined-asymmetric", "thrusts_n": [8,12,7,10]}
  ]
}
```
Replace the quoted snapshot placeholder with a JSON object from the real design record. All forces are input thrusts in N; M10.7 does not invent or assume likely operating loads.

Uses M10.6's effective per-rotor span and the existing circular-tube bending formula to report every case's thrust, effective span, root moment, fiber stress, material allowable, and stress-to-allowable margin, plus the governing case and rotor. The response includes material source and declared uncertainty and an explicit limited-screening verdict.

Fail-closed: missing frame/material, invalid or non-finite loads, mismatched rotor counts, duplicate/empty case names, >32 cases and malformed geometry are rejected. A zero-load case has undefined (null) margin and is never classified as evidence of strength. This analysis has **no persistence** and does not overwrite simulation results or change the reference aircraft.

Validation: `python -m pytest tests/physics/test_structural_envelope.py tests/integration/test_api.py -q`; full suite `python -m pytest -q`; frontend unchanged but GitHub Actions still checks npm build/Vitest.

**Not validated against physical testing**: exact joint boundary conditions, torsion, composite laminate orientation, buckle modes, fasteners, fatigue, aerodynamic load exchange and time-varying excitation are not modeled. No percentage of real-world success is assigned.
