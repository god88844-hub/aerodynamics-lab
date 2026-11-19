# Aerodynamics Lab complete roadmap

The approved scope is defined in [PRODUCT_SPEC.md](PRODUCT_SPEC.md). Only Phase 0 is the current implementation focus. Source details and acquisition gaps belong to [SOURCES.md](SOURCES.md). Actual completion belongs to [ACCEPTANCE.md](ACCEPTANCE.md).

## Phase 0 — Drone invention laboratory

Build the shared foundation before expanding individual aircraft families. Each package has an issue, requirements, dependencies and observable acceptance evidence.

| Package | Dependencies | Deliverable and exit evidence |
| --- | --- | --- |
| Foundation and identity | Audited baseline | Renamed repository, preserved history and unfinished work, published specifications, stable versioned project contracts and regression-tested legacy import. |
| Desktop and native prototype | Foundation | Godot application opens/saves projects, edits a representative geometry, selects components, renders reference results and cancels a worker. Publish baseline performance and installation results. |
| CAD and engineering assembly | Prototype | Constrained sketches, features, solids/surfaces, assemblies/joints, blades/wings, drawings, BOM and exchange work through normal application entry points. Validate geometry, mass properties, round trips and revision recovery. |
| Environment and experiments | Foundation, prototype | Save/replay terrain, obstacles, atmospheric fields, missions, disturbances, seeds and analysis settings. Coordinate and unit tests plus reproducible experiment runs pass. |
| Physical models and electrical integration | Foundation, CAD | Component and assembly behavior, per-component limits, thermal and structural mechanisms have declared support and evidence. Invalid limits fail and unknown parameters remain visible. |
| Four aircraft families | Physical models, environment | Multirotor, fixed-wing, helicopter and VTOL reference projects complete their applicable missions. Custom geometry and mechanisms have explicit supported domains. Each family has its own measurement campaign. |
| Interactive and detailed analysis | CAD, environment, physical models | The application runs reference cases and cancellable CFD, structural, vibration, fatigue, thermal and electrical jobs. Results retain backend versions, convergence, discrepancy, uncertainty and reproducible inputs. |
| Rain, snow, wet operation and icing | Physical models, environment | Applicable accumulation/shedding, airflow, sensor, electrical and structural effects have implemented models and qualification cases. Record missing matched tests. |
| Autonomy and multi-drone experiments | Aircraft, environment | Manual/mission control, sensor models, autopilot integration, visual navigation, mapping, obstacle avoidance and coordinated multi-vehicle scenarios pass recorded tests. |
| Learning and invention workflows | CAD, experiment execution | Guided experiments, equations, assumptions, sweeps, comparisons and optimization are usable in the application. Saved hypotheses and results remain reproducible. |
| Scientific acceptance and release | All applicable packages | Predeclared held-out comparisons, uncertainty coverage, failure cases, independent review, desktop packaging, compatibility, security, accessibility, load and recovery acceptance are complete. |

Software availability and physical acceptance are separate. Public data are the first evidence source. A requirement awaiting new measurements or qualified review remains open.

GitHub tracks [Phase 0](https://github.com/god88844-hub/aerodynamics-lab/milestone/1) through foundation #99, desktop #100, CAD #101, world #102, electrical/physical models #103, aircraft #104, weather #105, autonomy #106, learning #107, validation #108, release #109 and detailed analysis #110.

## Phase 1 — Bio-inspired flight

Add morphing/flapping mechanisms, compliant surfaces, flexible structures and aeroelastic coupling. Develop uncrewed demonstrations and compare measured forces, deformations, actuator response, energy and control behavior. Candidate references include PigeonBot II, measured avian morphology and inertia. Completion requires geometry-specific held-out experiments and bounded validity claims.

## Phase 2 — Human-scale and crewed systems

Add human loads, human-machine control, redundancy and recovery systems. Evaluate the original configurable 60 kg pilot scenario with apparatus mass, structure, propulsion, gusts and operating conditions included. Independently reviewed structural and flight evidence establishes each intended use. Drone validation transfers only where a documented similarity argument and additional evidence support it.

## Phase 3 — Jets and high-speed flight

Add compressible flow, turbine propulsion, shocks, flutter and thermal/structural coupling. Use qualified NASA CFD and compressor-rig benchmarks before configuration-matched propulsion and flight campaigns. Completion requires demonstrated behavior across the declared speed, Reynolds number, temperature and installation ranges.

## Phase 4 — Rockets and spaceflight

Add changing mass/inertia, propulsion, staging, atmospheric ascent, recovery, orbital dynamics and re-entry. Candidate tools include NASA CEA, RocketPy and OpenRocket under their individual licenses. Analytical checks, trajectory convergence and measured propulsion/flight evidence qualify each model. Calculated thermochemistry remains classified as calculation.

## Legacy milestone crosswalk

| Legacy scope | Role in the new roadmap |
| --- | --- |
| M0–M10 | Reusable architecture, multirotor physics, controller, scenarios, editor, optimization, V&V and audit foundation. |
| M11, M29 | Dependency security, production, migration, provenance, deployment, recovery and release requirements. |
| M12–M20 | Existing component/flight evidence, ingestion and protocol tooling. Reuse where the normal workflow and evidence support the new requirement. |
| M21–M27 | Outstanding battery, propulsion, controls, aero/thermal, structures, complete-flight and uncertainty acceptance. |
| M28 | Existing placement editing, revision and clearance work feeds the larger full-CAD requirement. |
| M30 | Legacy drone release acceptance maps to the Phase 0 release gate. |
| M31 | Expansion is split between additional uncrewed families inside Phase 0 and later flying-system phases. |

The former ten outstanding M21–M30 families describe the legacy multirotor release scope. The acceptance ledger tracks the expanded requirements individually.

## Builder sequence

Read the acceptance ledger and select the next dependency-ready issue. Inspect its linked code, experiment and source records. Implement its normal user entry point, verify the acceptance conditions, and record current commit/run evidence. Keep independent measurement gaps open. Merge a PR after its current head and required checks pass.
