# WP1–WP3 contract lock proposal

Bundle `wp1_wp3_1`, 20 November 2026. Machine-checked and content-addressed;
**owner sign-off pending**. These boundaries permit qualification, not new physics or full CAD expansion.
See [architecture](../ARCHITECTURE.md), [prospective tolerances](../VALIDATION_TOLERANCES.md)
and [local admission limitations](../prototypes/LOCAL_CAD_BUDGETS.md).

`python scripts/export_contracts.py --check` verifies generated JSON Schemas,
capabilities, policy values and the raw policy hash against `wp1-wp3-1/lock.json`.
CI runs that check as a regression. A semantic change requires a new version and review;
regenerating a lock does not grant approval. Hashes bind bytes, not authority or registration time.

`python scripts/lab_contract.py CONTRACT input.json checked.json` is the public
machine-validation entry point. `--require-executable` additionally rejects planned
surface solvers. Schema-valid data remain physically unvalidated. Existing project
import/run and supervised CAD inputs also enforce their applicable contracts.

| Boundary | Contract and actual enforcement |
| --- | --- |
| Units/frames | `Frames`: SI, right-handed local Z up; body X forward/Y left/Z up; wxyz body-to-world unit rotations. Stored aero angles are radians. CAD recipes keep explicitly suffixed `twist_deg` at their existing adapter boundary. Godot rendering maps `(x,y,z)` to `(x,z,-y)` only for display. |
| Geometry | `EngineeringProject`, `GeometryAsset`, `BladeRecipe`, `BoxRecipe`, `CadTorqueRequest`; relative asset paths, source hashes, finite inputs and supported ranges. Exact asset bytes are verified by `project_assets`/CAD torque; a declared hash alone does not verify a file. |
| Model/solver | Immutable source/environment/parameter digest fields, version and declared algorithm. `CAPABILITIES` allows only existing legacy Python and isolated single-solid torque paths. Their additional environment/geometry restrictions remain enforced by those adapters. |
| Jobs/resources | `WorkerRequest` is the executable frozen local protocol. `JobRecord` specifies the wider persisted job boundary; no scheduler is added. Local success binds request/result hashes and supervisor resource approval in both clients. `ResourceLimits` and the lightweight stdlib supervisor policy have conformance tests. |
| Evidence | `EvidenceRecord` carries source/license, whole experiment partition, original hash and confirmatory prerequisites. It cannot assert physical acceptance. JSON claims of review/calibration are untrusted metadata requiring independent authentication before any future decision. |

## Geometry to aerodynamic forces

`AeroSurface` binds **exact** CAD geometry and its SHA-256 to a body placement,
reference area/span/chord, moment datum, ordered blade/span stations and polar assets.
Each station carries chord, twist and leading-edge position; each polar declares
Reynolds/Mach/angle envelope, dimensionless Cl/Cd/Cm about quarter chord and source class
(independent measurement/manufacturer/CFD/synthetic). A display mesh/LOD is rejected as
an aerodynamic source. Polar sources are hashed project-relative source assets.

Surface axes are X chord-forward, Y increasing span, Z up; the explicit unit quaternion
rotates them into body axes. Relative-air velocity is **vehicle minus air** in body axes.
`AeroLoads` returns force in N and moment in N·m, both body-axis vectors about the
explicit body-frame datum. Solvers must transform sectional lift/drag/moment consistently:
drag opposes relative-air velocity, lift is perpendicular according to the declared
surface orientation, and datum shifts use `M_new = M_old + (r_old-r_new) × F`.
No global lift-up or thrust-positive assumption overrides installation/flow direction.

`bemt_planned`, `vlm_planned` and `cfd_planned` are **unsupported execution backends**.
This release defines their input/output seam; it does not turn arbitrary invented CAD
into aerodynamic forces. Future adapters must verify asset bytes and units, refuse
out-of-envelope polar interpolation/extrapolation unless explicitly modeled as unvalidated,
publish convergence/model identity and obtain independent geometry/regime evidence.
Body surfaces currently have only the planned CFD seam. Multirotor validation cannot
automatically validate a wing, helicopter or VTOL configuration.

## Acceptance and hold

The 20 previously inspected campaigns remain development evidence under the new policy.
M21–M27 use future preregistered confirmatory whole experiments, joint whole-flight
uncertainty coverage and independently reviewed, matched conditions. Current physical
failures remain recorded. No threshold is retrospectively applied as a blind success.
Stop after the visible/cold-build/cancellation qualification report for owner sign-off.
