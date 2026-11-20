# Aerodynamics Lab product specification

Approved planning decisions, 19 November 2026. This document defines the product. Implementation and measured acceptance are recorded in [ACCEPTANCE_LEDGER](ACCEPTANCE_LEDGER.md).

## Purpose

Build an open-source desktop engineering application where people learn by creating, modifying and testing flying machines in a physics-driven 3D environment. Phase 0 covers multirotors, fixed-wing drones, helicopter drones and VTOL. Users can invent configurations and explore unsupported conditions, with their uncertainty and validation status visible.

The intended scientific result is agreement with independent physical measurements within declared error limits for an identified hardware configuration, decision and operating envelope. Geometry, material properties, manufacturing variation, actuator behavior, flow and measurement uncertainty affect that agreement.

## Phase 0 requirements

| ID | Required capability |
| --- | --- |
| FND | Shared versioned project, assembly, environment, experiment, model, solver, job and evidence contracts. Windows desktop application and headless engineering interfaces. |
| CAD | Built-in constrained sketches, feature history, solids and surfaces, joints, assemblies, materials, custom wings and propeller blades, drawings, BOM and geometry exchange. Geometry changes feed applicable mass, inertia and physical models. |
| ELEC | Batteries, motors, ESCs, wiring, power distribution, sensors, controllers and actuators, including relevant limits, losses, timing, heating and failure behavior. |
| WORLD | Editable engineering test grounds, terrain, obstacles, ground contact, landing surfaces and reproducible missions. |
| WEATHER | Manual wind vector, gusts, turbulence, temperature, pressure and humidity, plus rain, wet operation, snow and icing. Applicable accumulation, shedding, aerodynamic, electrical, structural and sensor effects require models and evidence. |
| AIRCRAFT | Appropriate models and controls for all four drone families, supported custom layouts and per-component configurations. |
| ANALYSIS | Interactive experiments and queued aerodynamic, structural, vibration, fatigue, electrical and thermal analyses, with numerical convergence and uncertainty. |
| LEARN | Guided and advanced workflows, equations and assumptions, hypotheses, parameter experiments, design comparisons and optimization. |
| AUTO | Manual and programmed flight, autopilot integration, vision-based navigation, mapping, obstacle avoidance and coordinated multi-drone experiments. |
| VALIDATION | Source-linked measurements, independent calibration/holdout partitions, predeclared acceptance criteria, uncertainty coverage, failure detection and independent review. |
| RELEASE | Reproducible installation and deployments, project compatibility, accessibility, performance, security, recovery and documented operating limits. |

An implemented visual effect, an implemented physical model and an independently validated prediction have separate statuses. An applicable component-limit excursion produces FAIL. Missing information produces INCONCLUSIVE or an explicitly unvalidated prediction.

## Product boundaries

The first installation is a Windows desktop application. Design for baseline laptops, dedicated-GPU desktops and workstation/remote workers through [hardware profiles and fidelity levels](HARDWARE_AND_FIDELITY.md). Ordinary projects and experiments run locally within measured resource budgets. Heavy analyses use capped local workers or explicitly configured remote execution. Engineering test environments take priority over cinematic scenery.

Invention Lab remains the separate electronics, chip, processor and quantum-design product. Aerodynamics Lab owns flight-system electrical integration. A future component exchange can carry identity, units, behavior, limits, assumptions, uncertainty, model version and evidence between the products.

Phase 0 is the implementation focus. The complete expansion roadmap appears in [ROADMAP.md](ROADMAP.md). The original 60 kg human-pilot concept belongs to later human-flight research. Total flying mass must include the apparatus. The existing 60 kg hexacopter is a separate simulated reference study.

## Architecture decisions

1. Use Godot as the desktop scene, interaction and application shell. Use typed GDScript for application behavior.
2. Use independent C++20 libraries for exact CAD and demonstrated performance-critical computation. Integrate through GDExtension and headless interfaces.
3. Retain Python for existing models, data ingestion, calibration, optimization and research. Migrate a numerical path after profiling and agreement tests establish the benefit.
4. Use Open CASCADE for exact geometry. Qualify constrained-sketch and drawing integrations behind application interfaces before choosing FreeCAD solver reuse or another implementation. Preserve each dependency's license obligations.
5. Use ArduPilot as the initial broad autopilot adapter and add applicable PX4 integrations. Each run has one authoritative vehicle-state integrator.
6. Use double-precision engineering state, explicit units and coordinate transforms. Rendering and simulation clocks operate independently.
7. Keep detailed analysis in cancellable workers with explicit resource admission and local/remote execution contracts. Publish the inputs, backend versions, convergence and evidence associated with each result.
8. Preserve legacy design snapshots, component identities and stored reports through explicit adapters and migrations.

## Foundation interfaces

The project document carries stable identities, family, component/geometry references, assembly placement, materials and mass properties. The environment records atmosphere, terrain and weather. Experiments record mission commands, disturbances, controller/sensor configuration, seeds and solver settings. Model capabilities declare supported inputs, outputs, assumptions and domains. Job state records progress, cancellation and failure. A run manifest binds these inputs and model/data versions to outputs, failures and evidence.

Interactive and offline backends consume the same project definition. Optional future mechanisms extend versioned contracts. Their support is earned through implementation and validation.

### Implemented project document 1.0

`aeroforge_schemas.project.EngineeringProject` supports the four family identities, stable project/assembly/asset IDs, SI units, finite positions, unit quaternions, acyclic hierarchy, project-relative geometry references, atmosphere/weather settings and experiment settings. Geometry assets retain their declared SHA-256 and role. Asset bytes and their physical applicability require separate verification.

The legacy adapter preserves the validated 0.1 multirotor snapshot as its authoritative design representation. Generic assembly projects use a separate tagged representation. The legacy backend accepts its fixed default environment and seed. Changed atmosphere/weather, generic assemblies and unassigned backends receive an explicit refusal.

API callers use `POST /api/projects/import-legacy` with `{"snapshot": ...}` or `POST /api/projects/validate` with the project document. The response contains normalized `project` and `project_sha256`. Existing design/simulation routes retain their contracts.

Headless callers run `python scripts/lab_project.py import-legacy source.json project.json`, `validate project.json checked.json`, or `run project.json run.json`. Import/validation output a project document. A run includes the frozen project, digest, backend, existing simulation inputs/result and explicit physical status. Output publication is atomic and uses a separate path from the input.

## Completed qualification and full implementation plan

The standalone Godot/OCCT/worker qualification passed. Its [retained report](prototypes/QUALIFICATION_GATE_FOLLOWUP.md) and original graphical receipts remain bounded historical evidence. It is not the current product scope or another prerequisite to repeat.

The [MASTER_PLAN](MASTER_PLAN.md) defines all Phase 0 software tasks and separate physical gates, plus later-phase entry/exit checklists. After owner approval of PR #126, merge and `v0.0-plan-locked`, execute Slice 0A beginning with P0A-005. Complete supported CAD, all four aircraft families, engineering worlds/weather, electronics, analysis, learning, autonomy and production acceptance through 0A–0D.

The [hardware acceptance matrix](HARDWARE_AND_FIDELITY.md) remains a product delivery requirement across baseline laptops, dedicated-GPU systems and remote workers. Automatic display LOD cannot alter engineering inputs. Qualification of one measured machine is not the full compatibility matrix. Numerical/physical model support and accepted measurement envelopes remain explicit.

## Basis

[Godot license](https://godotengine.org/license/) · [Native extension interface](https://docs.godotengine.org/en/stable/engine_details/engine_api/gdextension/index.html) · [OCCT](https://www.occt3d.com/dev/doc/overview/html/index.html) · [FreeCAD](https://github.com/FreeCAD/FreeCAD) · [ArduPilot external physics](https://ardupilot.org/dev/docs/sitl-with-JSON.html) · [NASA modeling and simulation standard](https://standards.nasa.gov/standard/NASA/NASA-STD-7009)
