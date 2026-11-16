# M10.8 — Opt-in arm torsion and mechanical joint capacity screening

Extends the existing `POST /api/designs/structural-envelope` endpoint and the M10.7 static bending results. Legacy requests remain valid; existing flight-physics algorithms, frame geometry, and stored designs are unchanged.

## Explicit inputs

Each named load case may additionally specify `axial_torques_n_m`: **one signed applied torque about each arm's own long axis**, in N·m. A missing torque vector means **unknown**, not zero. Rotor spin/reaction torque is generally about body Z, which is not the radial arm axis; AeroForge never silently converts it into an arm torsion load.

Optional `shear_allowable_pa` and `shear_allowable_source` provide a separately supplied shear allowable for a specific tube material/layup/condition. A material's tensile yield is **not** silently converted to shear strength.

Optional `joint_allowables` must contain `bending_moment_n_m`, `axial_torque_n_m`, and `evidence_source`. These are **user-supplied joint capacities**, not values calculated from bolt geometry or manufacturer documentation.

## Model

For a hollow circular tube (OD and ID in meters):

- Polar moment `J = pi/32 * (OD^4 - ID^4) = 2I`
- Maximum linear-elastic torsional shear `tau = |T| * OD/2 / J`
- Tube torsion margin = independently declared shear allowable / tau
- Joint bending capacity margin = independently declared allowable moment / F*L
- Joint torsion capacity margin = independently declared allowable torque / |T|

Zero applied torque or a missing torque vector does **not** imply a passing torsion check. Missing shear/joint allowables similarly leave their subchecks unassessed.

Bending, torsion, and connection capacities are reported as **separate independent screens**, with **NO combined interaction model**. An exceedance is reported as a known failure of the selected analytical limit; non-exceedance remains `INCOMPLETE_EVIDENCE` even if every selected screen appears below its own allowable.

## Example request

```json
{
  "snapshot": "<full JSON design snapshot object, not a literal string>",
  "cases": [
    {"name": "user_case", "thrusts_n": [9, 9, 9, 9],
     "axial_torques_n_m": [0.2, -0.2, 0.2, -0.2]}
  ],
  "shear_allowable_pa": 30000000,
  "shear_allowable_source": "external measured shear certificate identifier",
  "joint_allowables": {
    "bending_moment_n_m": 6,
    "axial_torque_n_m": 0.8,
    "evidence_source": "external connection test identifier"
  }
}
```

In the UI, optional per-case torques follow a `|` separator: `hover: 9,9,9,9 | 0.2,-0.2,0.2,-0.2`. Enter actual allowables with documentary provenance; absent values remain unknown.

## Verification and limits

`python -m pytest tests/physics/test_advanced_structure.py tests/integration/test_api.py -q`, then the full Python suite and frontend build/Vitest.

This is **analytical software verification**, not joint FEA, stress-interaction prediction, dynamically coupled torsion, calibrated composite strength, fatigue evaluation, proof testing, certification, or a real-world probability. Actual connections need experimentally justified allowables and applicable load cases.
