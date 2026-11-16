# M10.5 — Parametric frame plates and mechanical attachment anchors

The frame may now declare a body-frame plate bounding box (`plate_dimensions_m`) and named `mount_points`. The 3D view renders those elements and uses the specified outside tube diameter for the arm visuals.

Battery and payload point-mass parts can reference a mount using `mount_id`. The Python design schema refuses dangling, duplicate or misaligned assignments. The editor can attach a selected part at its present center of gravity, move the anchor (automatically moving the attached part in one undoable edit), detach it, or remove the mount without deleting the part.

These are **position constraints**, not modeled fasteners, bolts, stress distributions or true mechanical joints. The assembly's CoG/inertia updates because its part positions change, using existing mass-property physics.

The plate geometry is for visual assembly layout **only**: its mass and inertia are not automatically recomputed, so previously measured part properties remain authoritative.

## Important structural accuracy caveat

Older Quad-X designs scale X/Y rotor offsets by `arm_length_m`, while the root bending monitor uses `frame.arm_length_m` directly as the cantilever length. The true radial rotor distance can therefore be larger. M10.5 now warns about this possible stress-underestimation in preflight instead of incorrectly implying that the structural margin is established. A separate correction of the beam-load model and migration of existing snapshots is required.

No CAD-certified clearances, structural joint FEA, CFD, or physical-validation equivalence is established.

## Regression and browser acceptance

```bash
python -m pytest tests/physics/test_frame_assembly.py -q
python -m pytest -q
cd apps/web
npm ci
npm run build
npm test
```

In browser, create a frame mount for a battery or payload, edit mount coordinates, verify the 3D part follows and the mass/CoG preview updates, confirm independent gizmo movement is disabled until detached, and test undo/redo plus save/reload. Change plate dimensions and arm OD and verify rendered geometry changes, without assuming frame inertia also changed.
