# M10.3 — Interactive 3D translation and geometry preflight

The Three.js design viewport now provides on-canvas translation handles for selected batteries or payload point masses. Select a part using the component hierarchy or click its center marker; the XYZ handles move it in the physical body frame. A snap dropdown supports off, 5 mm, 10 mm, 50 mm and 100 mm increments. Mouse release commits exactly one design-store edit that can be undone/redone. Orbit camera control is disabled during drag.

The view is locked for translation when replaying a stored flight result to prevent mixing world-flight coordinates with body-design coordinates. Motor/ESC/propeller/frame parts remain locked: editing them independently would break the rotor/motor/frame model coupling.

The geometry preflight checks input validity, tube inner/outer diameter order, and projected rotor-disc overlaps when a sourced propeller diameter is available. An insufficient projected gap is a warning. It does **not** constitute measured physical clearance, collision detection, rotor wake CFD or airworthiness evidence.

## Verify

```bash
cd apps/web
npm ci
npm run build
npm test
```

Full regression: `python -m pytest -q` from the repository root after installing the documented Python environment.

Browser acceptance: select battery -> enable gizmo -> drag X/Y/Z -> observe snapshot and mass/CoG preview refresh; undo/redo; toggle snap; run flight then verify editing handles aren't mixed with replay; select prop from the evidence DB and inspect disc-proximity warnings. Ensure a selected motor has no translate gizmo.

All positions and distances are SI meters. The rendered drone remains a schematic representation, not a geometry-accurate CAD/FEA model.
