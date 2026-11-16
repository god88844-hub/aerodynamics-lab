# M10.4 — Parametric primitive geometry and analytical inertia

## Scope

Add explicit optional dimensioned primitives to the existing design **snapshot**:
- `part.geometry = {shape: "box", dimensions_m: [x, y, z]}`
- `part.geometry = {shape: "cylinder", dimensions_m: [diameter, diameter, height]}`, axis +body Z.

Both inputs use SI meters. Parts without geometry remain point-mass or user-specified inertia representations exactly as before. A part's existing measured/declared inertia tensor **always takes precedence** over geometry-derived inertia. Mass is never inferred from dimensions or assumed density; the user supplies mass.

## Coupling to simulation

The shared Pydantic schema validates dimensions. The physics design adapter derives solid-uniform-density own-CoG inertia using existing `geometry.primitives.box_inertia` and `cylinder_inertia_z` functions only if no own-inertia tensor is supplied. The existing parallel-axis assembly, rigid-body solver, and API automatically use these inputs. Re-running a saved snapshot is deterministic.

The editor can assign/resize primitive shapes for batteries and payloads, including accurate schematic 3D dimensions. Explicit-inertia parts are locked against geometry or mass changes. Snapshot edits invalidate old simulation results and participate in undo/redo history.

## Geometry warnings

The preflight warns when the axis-aligned bounding boxes of declared primitives intersect. This is **broad-phase only**: cylinder AABBs may overlap without physical contact. No CAD mesh collision, structural connection, realistic battery form factor, material response, certification, aero/rotor effects or physical validation is implied.

## Run checks

```bash
python -m pytest tests/physics/test_parametric_geometry.py -q
python -m pytest -q
cd apps/web
npm ci
npm run build
npm test
```

Browser acceptance: add payload -> choose solid box -> edit X/Y/Z dimension -> verify the actual shape changes in the 3D viewport; observe API preview inertia changes while total mass stays constant; switch to cylinder -> see two dimensions (diameter and height); move into another dimensioned part -> expect approximate overlap warning; undo -> prior geometry returns; save/load -> dimensioned geometry persists.

**Scientific limitation:** The geometry model assumes a homogeneous solid with its entire specified mass, which is generally not an accurate density distribution for real batteries and complex manufactured parts. Independent measurement supersedes this model.
