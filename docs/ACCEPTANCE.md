# Implementation and scientific acceptance

## Baseline

The audited starting commit is `1d841865e61cb76a58f48eae9e107f8ad737fc1e`. [Main CI](https://github.com/god88844-hub/aerodynamics-lab/actions/runs/44372322633) passed.

Existing capabilities include the multirotor rigid-body engine, sourced static powertrain, closed-loop scenarios, schematic/primitive editing, saved design revisions, DXF placement exchange, independent-data comparisons, dependency checks, packaged deployment and database recovery. They require additional work to satisfy the expanded product contract.

Pre-existing work in 21 local files is preserved at local commit `a1d7313146b687e78468df9a5b66a3920120092c` on `feature/production-acceptance`. Its accessibility, load and model-provenance changes require review and verification before promotion.

The repository was renamed from `god88844-hub/aeroforge` to `god88844-hub/aerodynamics-lab` with GitHub repository ID `1459120659`. Historical source and experiment identities remain in their original records.

## Requirement ledger

Implementation states are planned, partial, implemented and software-verified. Scientific states are unvalidated, analytical screening, measured comparison and accepted within a stated envelope. Each promotion needs linked evidence appropriate to its scope.

| Requirement | Implementation baseline | Scientific baseline | Next acceptance evidence |
| --- | --- | --- | --- |
| FND | Project document 1.0, four-family assembly representation, legacy import, normalization API and headless reference runner | Unvalidated product foundation | Project round-trip, invalid-input/backend refusal and legacy execution tests pass locally. Desktop/native and complete foundation acceptance remain pending. |
| CAD | Primitive editing, mounts, clearance, revisions and placement DXF | Analytical screening | Exact geometry/history, drawings, assemblies and engineering round trips. |
| ELEC | Powertrain/battery models and limit checks | Separate measured comparisons | Installed component behavior, uncertainty, dynamics and failure tests. |
| WORLD | Fixed scenarios, core uniform relative-wind drag | Analytical screening | Normal UI/API environment/mission authoring, contact and reproducibility. |
| WEATHER | Partial dry-air model | Separate limited source references | Atmosphere, rain/wet/snow/icing models and applicable held-out measurements. |
| AIRCRAFT | Near-hover multirotor foundation | Full-aircraft acceptance open | Four families, appropriate actuators, missions and independent reference campaigns. |
| ANALYSIS | Numerical tools, screening and offline studies | Separate measured comparisons | Integrated converged analysis workflows and model discrepancy. |
| LEARN | Basic application/manual and offline sweeps | Software workflow pending | Guided and advanced experiments, comparisons and optimization in the application. |
| AUTO | Basic controller and fixed scenarios | Controller/hardware acceptance open | Sensor/autopilot, vision, mapping, avoidance and multi-drone acceptance. |
| VALIDATION | Ingestion, hashes, comparisons and campaign tools | Major scientific gates open | Qualified measurement uncertainty, frozen tolerances, holdouts and independent review. |
| RELEASE | Packaged web/API, security, HTTPS and database recovery | Decision-grade release open | Native installation, compatibility, full acceptance evidence and operating-envelope documentation. |

Link requirements to issues and recorded commits as packages are delivered. Detailed acceptance conditions are in the product specification and roadmap package exits.

The current work packages are [FND #99](https://github.com/god88844-hub/aerodynamics-lab/issues/99), [desktop #100](https://github.com/god88844-hub/aerodynamics-lab/issues/100), [CAD #101](https://github.com/god88844-hub/aerodynamics-lab/issues/101), [WORLD #102](https://github.com/god88844-hub/aerodynamics-lab/issues/102), [ELEC #103](https://github.com/god88844-hub/aerodynamics-lab/issues/103), [AIRCRAFT #104](https://github.com/god88844-hub/aerodynamics-lab/issues/104), [WEATHER #105](https://github.com/god88844-hub/aerodynamics-lab/issues/105), [AUTO #106](https://github.com/god88844-hub/aerodynamics-lab/issues/106), [LEARN #107](https://github.com/god88844-hub/aerodynamics-lab/issues/107), [VALIDATION #108](https://github.com/god88844-hub/aerodynamics-lab/issues/108), [RELEASE #109](https://github.com/god88844-hub/aerodynamics-lab/issues/109), and [ANALYSIS #110](https://github.com/god88844-hub/aerodynamics-lab/issues/110). Future planning is tracked in #111–#114.

## Scientific completion

For each intended decision, freeze the model, configuration, data partition, conditions and numeric error/uncertainty criteria before evaluating held-out measurements. Report measured error, numerical convergence, measurement uncertainty, coverage, repeatability, failure detection and domain boundaries.

Each aircraft family requires an independently measured reference configuration. Claims for rain, snow, icing, autonomy, structures, thermal behavior and electrical failures require their own applicable evidence. New user-created configurations receive explicit model/evidence status.

An applicable physical-limit excursion returns FAIL. Missing information, unsupported mechanisms and insufficient uncertainty coverage yield INCONCLUSIVE or an unvalidated prediction. Preserve observed failures and anomalous records with their interpretation and any exclusion rationale.

Independent review and required measurements remain open when the available public material cannot establish them. The legacy ten M21–M30 acceptance families remain incomplete until their actual exit evidence exists.

## Verification

Exercise project migration and round trips, units/frames, geometry and mass properties, analytical physics, conservation where applicable, convergence, per-component limits, frozen-run reproduction, cancellation/recovery, accessibility, security and installation. Preserve npm audit and backend audit requirements.

Use the normal editor/API/headless entry points for acceptance. CI verifies software and deployment. The physical ledger records experiment-backed claims separately.

Hardware tier support follows [the compatibility matrix and resource/LOD contract](HARDWARE_AND_FIDELITY.md). The initial Windows prototype run is one machine observation. Tier 1/2/3 performance, adaptive LOD, remote scheduling and enforced worker budgets remain unaccepted until their recorded checks pass.
