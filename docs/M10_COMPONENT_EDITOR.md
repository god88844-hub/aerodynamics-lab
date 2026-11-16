# M10.2 — 3D component selection and dimensional inspector

This increment adds a usable engineering-oriented component editor to the Three.js laboratory.

## Added
- Click part center-of-gravity markers in the 3D viewport to select components, or choose them in a component hierarchy.
- Edit battery and newly added payload point-mass positions (X/Y/Z in meters) and their masses in kilograms.
- Add/remove payload point-mass entries with unique names (payload_1, payload_2, …).
- See center-to-center Euclidean spacing in the inspector and in the 3D scene.
- Undo and redo up to 40 design edits.
- Invalidate previous flight simulation results when the design changes so stale trajectories are not shown as current.
- Prevent independent movement of motors, ESCs, propellers or structural frame parts while their coupled physical-model constraints remain unsupported.
- Guard against accidentally applying the Quad-X arm scaling function to non-quad configurations.

## Science and limits
The displayed markers, battery box, propeller discs and measurement line are schematic renderings. They are NOT CAD-certified solid geometry, clearance measurements, aerodynamic/structural models or collision detection. Added payloads are modeled as *point masses*; the precise CoG and inertia effects enter the backend on the next preview/simulation. Editing batteries changes snapshot mass and position; battery-component-mass consistency checks continue to apply. The current arm-length editor applies only to Quad-X.

The center-to-center separation is not a minimum physical clearance.

## Acceptance checks
`cd apps/web && npm ci && npm run build && npm test`
`python -m pytest`

Browser: select battery in the viewport → edit X → verify center-of-gravity preview moves; add payload → reposition and verify mass/CoG; choose two parts and inspect 3D distance; undo/redo; simulate and then edit to verify the old result disappears; open a non-quad design and verify arm scaling is blocked.

This increment does not add general-purpose mesh CAD, arbitrary rotor rearrangement, CFD, FEA or physical validation. Those remain separate future milestones.
