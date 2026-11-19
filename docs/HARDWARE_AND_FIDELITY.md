# Hardware tiers and aerodynamic fidelity

Accepted product direction, 20 November 2026. These are delivery and benchmark targets. The current prototype has not earned a minimum-system-requirements claim. The recorded developer laptop is one test machine in a future compatibility matrix.

## Hardware targets

| Profile | Intended hardware | Target experience | Work allocation |
| --- | --- | --- | --- |
| Tier 1: baseline | 8–16 GB RAM, integrated graphics | Full supported parametric CAD features, real-time 6-DoF with qualified analytical/BEMT/table models, ArduPilot SITL, capped local studies | Adaptive display tessellation, simple engineering terrain, optional effects off, one budgeted local analysis at a time; deterministic stepped sensor experiments |
| Tier 2: desktop | 16–32+ GB RAM, dedicated GPU | Same engineering capabilities plus detailed terrain/weather rendering, camera/LiDAR experiments and qualified mid-size CFD/FEA studies | Enable features after capability checks and measured scene/job budgets; real-time vision remains conditional on the benchmark |
| Tier 3: workstation/remote | Measured workstation capacity or explicitly configured remote workers | Large CFD/FEA, RANS/LES where the backend supports them, coupled structural/thermal jobs and swarm sweeps | Queued headless workers with declared memory, CPU/GPU, storage and wall-time budgets |

RAM/GPU labels alone cannot determine solver capacity. Mesh topology, equation count, timestep, backend and concurrent processes matter. No tier silently substitutes a different physical model or earns a physical-validation status. All four Phase 0 drone families retain the same scientific gates.

Full CAD on Tier 1 means the same supported editing operations with bounded working sets. It does not promise interactive performance for an unlimited assembly. Oversized work must offer a reduced display, a smaller explicitly chosen study or an eligible remote job.

## Display and engineering separation

Automatic level of detail (LOD) is required for all hardware profiles. Exact CAD stays authoritative for geometry and mass-property computation. A display mesh is a derived asset with an explicit chordal/angular tolerance, units, frame, source identity and hash. Reducing its triangles must not change the solid, flight coefficients, collision-analysis geometry or evidence decision.

The runtime display-mesh path explicitly generates LODs. Godot's automatic scene-import LOD does not automatically cover procedurally created mesh arrays. The initial CAD prototype has bounded tessellation, generated procedural LODs and an explicit display-size refusal. Large-assembly residency and hardware-tier performance remain pending until tested. [Godot mesh LOD](https://docs.godotengine.org/en/stable/tutorials/3d/mesh_lod.html), [ImporterMesh API](https://docs.godotengine.org/en/stable/classes/class_importermesh.html).

Use capability discovery plus a user-selectable profile. Adjust viewport resolution, shadows, effects, terrain detail and sensor-render cadence first. Keep requested and effective values visible. A non-real-time stepped sensor run records simulation time separately from rendering/wall time. Synthetic camera/LiDAR output remains synthetic evidence.

## Worker admission and remote execution

Before launching a heavy job, estimate memory, mesh/equation size, scratch space and runtime using backend-specific estimates. Reserve space for the desktop, OS, integrated-GPU shared memory and other active jobs. A low-memory profile cannot assume that a 6 GB worker is safe on every 8 GB machine.

The versioned job contract must carry requested/effective resources, local or remote execution, backend/capabilities, frozen project/assets, solver settings, seeds, progress, cancellation and result identity. An estimate exceeding available resources queues, refuses with a reason, or offers explicitly configured remote execution. It must not silently coarsen the analysis mesh or reduce convergence criteria. Monitor actual usage; cancellation/failure preserves the last saved project and records an incomplete run.

Remote execution is planned infrastructure. The present desktop launches a local Python process. It has no remote scheduler or enforced OS memory cap yet. Credentials and uploaded project/data access require explicit configuration.

## Geometry-to-aerodynamics bridge

CAD alone supplies geometry. Density/assembly assumptions are needed for mass and inertia. New aerodynamic coefficients need an applicable model or experiment.

| Fidelity | Intended use | Required bridge and limits |
| --- | --- | --- |
| Live flight | Analytical/lumped models, BEMT and qualified lookup/ROM tables | Geometry and component parameters map to a named supported model; unsupported shapes remain unvalidated or refused. Solver rate is measured against the controller and dynamics bandwidth. |
| Design loop | Panel/VLM/vortex methods where applicable | Export aerodynamic surfaces, retain topology/units and compute versioned coefficients/derivatives. Declare attached-flow and other assumptions; arbitrary CAD solids are not automatically supported. |
| Detailed analysis | Qualified CFD/FEA/thermal backends | Record meshing, boundary conditions, convergence, discrepancy and uncertainty. Stall, separated flow, icing and interactions need appropriate models and measurements. Derived reduced models keep their source/envelope. |

These are separate fidelity levels, not the hardware tiers. A Tier 1 user can submit a detailed remote analysis, and a workstation can run the same live model. Computed CFD results are numerical comparisons; independent experimental agreement is still required for physical validation.

## Delivery slices and fault behavior

Keep the complete Phase 0 scope. Deliver dependency-ordered vertical slices: **0A** multirotor design/run/evidence loop, **0B** fixed-wing and geometry/aerodynamic bridge, **0C** helicopters/VTOL and detailed workers, **0D** advanced autonomy and release. Shared interfaces come first. Each slice records software availability and scientific acceptance separately. Full wet/icing and advanced autonomy requirements remain open when evidence is missing.

Physical models must propagate applicable live degradation/fault effects into the authoritative integrator: electrical sag and cutoff, supported thermal derating and actuator loss, and supported structural failures changing load paths/control authority. An exceeded known limit produces FAIL even when post-failure motion is unmodeled. Unknown breakup/reboot/icing behavior cannot be invented. Separate implemented transitions from physically qualified ones.

## Acceptance matrix

Publish CPU/GPU/driver/OS/RAM, renderer, power mode, project/assets, scene counts, viewport resolution, solver/controller rates and cold/warm state. Measure at least one 8 GB integrated-GPU machine, one 16 GB integrated-GPU machine, a dedicated-GPU desktop and an explicit remote worker before advertising the corresponding tier as supported.

For representative projects, record startup/import/rebuild/save latency, frame-time distribution, peak desktop and aggregate worker memory, cancellation cleanup and correctness. The initial editing target is at least 30 FPS on a published 200-part assembly. The 8 GB and 16 GB profiles need distinct resource budgets derived from measurements. Publish actual results and failures; no measured value is available for that assembly yet.

Geometry-to-physics acceptance requires a supported geometry edit to change independently checked mass/inertia and an applicable simulation response. Repeat frozen runs under the same backend/platform and report actual numerical differences. Cross-platform bit identity is not promised. Cold-build time and cancellation reclamation targets require repeatable protocols, with downloads/cache state and process trees recorded.

## Dependency boundary

The current CAD prototype uses pinned prebuilt CadQuery/OCCT Python wheels in a separate worker and Godot's native extension for the independent C++ core. Its constrained rectangle demonstration does not establish a complete sketcher. FreeCAD solver/UI reuse remains subject to an explicit integration/license decision. Autopilots and detailed solvers use separately versioned adapters/processes where selected. Process isolation alone does not establish license compliance; distributions must retain notices, corresponding-source/relinking obligations where applicable, and a reviewed license inventory.
