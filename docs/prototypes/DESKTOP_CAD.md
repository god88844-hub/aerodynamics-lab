# Desktop and exact-CAD prototype evidence

20 November 2026. Related issues: #100 and #101. This is software prototype evidence. Physical qualification and the full interface migration gate remain open.

## Delivered slices

- [Desktop integration PR #116](https://github.com/god88844-hub/aerodynamics-lab/pull/116), tested head `4ccaa17c77beb68e9bbaca59758db1d8b804096c`, [green CI](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44605932650), merge `9171e9c5e0047992e091b9685b0a13a366f70168`. Godot shell, independent C++ mass/CoG, Python reference worker, selection, reference replay, project persistence and process cancellation.
- The CAD extension to that prototype adds a pinned prebuilt CadQuery/OCCT worker, a constrained rectangle check, recipe-driven blade loft, STEP round trip, hash-bound display mesh with automatic LOD and portable asset save/reopen. The exact tested CAD commit and all required checks are recorded by its GitHub PR/CI.

## Checks and scope

Local kernel tests require a valid single solid, positive volume, correct radial extent, dimensional sketch agreement, STEP volume agreement within 1e-7 relative error, SI display coordinates and asset byte integrity. Changing a station chord changes the constructed volume and STEP hash. Supplied density yields only a uniform-density estimate; absent density leaves mass unknown.

The actual desktop smoke path starts the application, loads the legacy reference through a worker, selects a component and cancels an active reference worker. A separate headless run exercises the reference simulation. With `LAB_TEST_CAD=1`, the same application builds a blade, requires generated mesh LODs, packages its assets, reopens it and checks that a generic CAD flight run is refused.

Focused local checks passed: 22 Python tests across CAD, asset integrity, project migration/execution, model provenance and release-CI verification; native CTest and the Godot/worker smoke path. The CAD dependency audit found no known vulnerabilities at execution. GitHub requires its own current-head checks, including backend audit and npm audit, before merging.

A rendered Windows inspection used Godot 4.7.2, OpenGL Compatibility and Intel integrated graphics. The rendered blade was inspected for actual geometry, usable labels and explicit physical status. This establishes one rendering observation. It does not establish the 200-part/30-FPS benchmark, Tier 1 support or a cold-build time. No frame-time or memory result is claimed.

## Limits still open

- Interactive sketch constraints, editable feature history, arbitrary wings/assemblies/joints/drawings and qualified material/mass/inertia integration.
- Geometry-to-aerodynamics bridge and supported geometry-to-flight response. A solid blade cannot be treated as a calibrated propeller.
- Cross-language contract coverage beyond the initial project/native interface.
- Hardware-tier benchmark matrix, large-assembly residency, aggregate memory admission, descendant-process cancellation and remote scheduling.
- Cold installation and distributable license acceptance. Python binary wheels speed developer setup but are not a finished Windows installer.
- Real physical measurement agreement and uncertainty for any new generated shape.

The constrained rectangle is a separate solver demonstration. The blade uses explicitly sampled section coordinates. The prototype does not claim that its blade is edited through a complete constrained sketcher.

See [desktop operation](../../apps/desktop/README.md), [hardware/fidelity contract](../HARDWARE_AND_FIDELITY.md), [acceptance ledger](../ACCEPTANCE.md) and [source custody](../SOURCES.md).
