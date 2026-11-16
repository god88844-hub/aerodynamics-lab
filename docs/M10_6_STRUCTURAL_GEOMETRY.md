# M10.6 — Structural geometry consistency

## Correction of a known modeling error

Prior AeroForge versions used frame.arm_length_m as the structural cantilever
span even for Quad-X rotor coordinates at (±L, ±L), where the actual horizontal
distance from the assumed body-frame arm root is **sqrt(2) × L**. They also
applied max(rotor thrusts) to one declared span, missing the possibility that
different rotors carry different loads on differently sized arms.

### Corrected static-bending model

For each rotor i, in body coordinates, and rotor thrust along body +Z:

- Horizontal geometric moment arm: R_i = hypot(x_i, y_i).
- Effective conservative static arm: L_i = max(R_i, declared frame.arm_length_m).
- Static bending moment: M_i = thrust_i × L_i.
- Cantilever root stress: sigma_i = M_i (OD/2) / [pi/64 × (OD^4 − ID^4)].
- Minimum reported structural margin: min_i(material yield strength / sigma_i).
- A structural-yield abort names the responsible rotor and effective arm length.

The model uses the design **body-frame origin as the assumed arm root**, not
the moving mass center. The maximum span is deliberately conservative for
legacy mismatches. Do not interpret these equations as proof of exact physical
root connections or a validated beam model.

### Editor and legacy compatibility

The "rotor radial span" control now operates on the true XY radius of an
ordered symmetric Quad-X. Scaling a rotor assembly retains the original
motor/ESC/propeller relative placement and individual Z offsets. Other layouts
cannot be edited with the Quad-X-specific control.

Existing snapshots are **not silently migrated**: old coordinates and
declared frame spans remain in saved files. Simulation reruns now use the
corrected per-rotor conservative bending stress and can yield lower structural
margins than reports produced by earlier versions. Warnings and run notes
identify these geometry mismatches. Historical simulation reports should not
be regarded as comparable without reviewing the calculation/model version.
Editing the Quad-X radial span explicitly synchronizes its frame declaration.

### Limits of structural credibility

This is an analytical static-cantilever **verification update**, not physical
validation of joints, clamps, stress concentrations, composite fiber direction,
fatigue, rotor aerodynamic interactions, crash impacts, torsion, flutter, or
structural deformation. It assumes identical circular tube sections on each arm,
all rotor thrust along body +Z and a common body-origin cantilever root. Any
unmodeled structure needs further engineering analysis.

### Tests

```bash
python -m pytest tests/physics/test_structural_geometry.py -q
python -m pytest -q
cd apps/web
npm ci
npm run build
npm test
```

Verify in the editor that an existing Quad-X reference with rotor XY offsets
0.25 m shows ~0.354 m true radial span, not 0.25 m. Change it to 0.40 m:
each rotor XY coordinate should become ~0.283 m and the declared frame span
0.40 m. Check that ESC placement scales proportionally and that an unrelated
frame-material edit does not silently rewrite the span.

This milestone does not provide visual browser acceptance or physical
flightworthiness evidence.
