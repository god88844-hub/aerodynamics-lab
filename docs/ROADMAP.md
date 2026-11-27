# Aerodynamics Lab roadmap

**Full standalone software plan (native zero-engine architecture update — 27 November 2026).** Qualification passed and is complete. The primary product transitions cleanly to **`apps/native/`**, our **100% engine-free native C++20 + OpenGL 3.3 + Dear ImGui** standalone CAD & aerodynamics desktop application (keeping `apps/desktop/` frozen only until native CI parity completes, while `apps/web/` remains frozen legacy). [PRODUCT_SPEC](PRODUCT_SPEC.md) defines scope and [ARCHITECTURE](ARCHITECTURE.md) defines the direct C++20 `lab_core` + local Open CASCADE/Python worker execution path without a required HTTP server or third-party game engine. Phase 0 completes multirotors, fixed-wing airplanes, helicopters, VTOL, and custom part design/redesign first; Phases 1–4 remain strictly sequential future phases.

The complete numbered, checkable task breakdown is **[MASTER_PLAN.md](MASTER_PLAN.md)**, generated from [planning/tasks.json](planning/tasks.json). It contains **150 unique tasks: 118 across Phase 0 and 32 across Phases 1–4**, each with dependencies, responsible actor, exact proof artifact, acceptance conditions and a planned verification target where applicable. The generated master issue and every relevant package/phase issue carry synchronized checklists.

## Approval and exact next task

[PR #126](https://github.com/god88844-hub/aerodynamics-lab/pull/126) has conditional owner merge/tag authorization recorded in [P0A-004](acceptance/P0A-004.md). Run the three pre-merge checks and require five green CI jobs before merge and annotated **`v0.0-plan-locked`** publication. Verify clean synchronized main, then stop. **Do not start P0A-005 under this request.** When the owner later resumes implementation, P0A-005 is the first software task: reproduce/freeze M21 cutoff failures, then follow the numbered dependency order.

## Phase 0 slices

| Slice | Product outcome | Required entry | Software exit | Separate physical exit |
| --- | --- | --- | --- | --- |
| 0A | Multirotor CAD/design, environment, missions, corrected coupled physics, learning, evidence and standalone application loop | P0A-004 owner plan approval | P0A-039 | P0A-040 |
| 0B | Full supported wing geometry/CAD-to-aero and fixed-wing mission loop | P0A-039 | P0B-021 | P0B-022 |
| 0C | Helicopter and VTOL mechanisms/transitions plus selected detailed analysis and local/remote workers | P0B-021 | P0C-023 | P0C-024 |
| 0D | Complete supported CAD, weather, autonomy, sensors/swarms, learning, production and release | P0C-023 | P0D-030 | P0D-031; final Phase 0 exit P0D-032 |

A software exit permits dependency-ready software in the next slice with physical gaps visible; it does not turn missing measurements into acceptance. Physical exits need actual matching independent evidence and review. Final Phase 0 acceptance and later-phase entry require their explicit scientific/release gates. Any suitable reference hardware may be used, with the model and each measurement campaign matched to that hardware and its conditions.

The [master plan](MASTER_PLAN.md#work-packages-and-slice-mapping) maps **all 12 work packages** to their slices and issues: WP1 #99, WP2 #100, WP3 #101, WP4 #102, WP5 #103, WP6 #104, WP7 #110, WP8 #105, WP9 #106, WP10 #107, WP11 #108, WP12 #109. Cross-cutting tasks retain one ID even when listed under several packages. WP7 detailed analysis, WP8 advanced weather and WP9 autonomy follow their listed prerequisites; qualification is not reopened.

## Phases 1–4

| Phase / issue | Scope | Prerequisite / entry | Exit |
| --- | --- | --- | --- |
| 1 / #111 | Bio-inspired morphing/flapping/flexible flight | Phase 0 P0D-032 plus owner gate P1-001 | P1-008 |
| 2 / #112 | Human-scale and crewed engineering | P1-008 plus owner gate P2-001 | P2-008 |
| 3 / #113 | Jets, compressible/high-speed flight and turbine/thermal coupling | P2-008 plus owner gate P3-001 | P3-008 |
| 4 / #114 | Rockets, variable mass/staging, orbital/re-entry/recovery models | P3-008 plus owner gate P4-001 | P4-008 |

Each phase has eight concrete checklist tasks covering entry, contracts/sources, implementation, frozen protocols, independent measurements, verification, physical validation/uncertainty and qualified review/release. Until entry is approved, **interfaces and dataset registries only**. Drone results do not automatically validate another flying system. The 60 kg pilot concept remains a later study assumption, including apparatus mass; calculated thermochemistry remains calculated evidence.

## Evidence and completion

Use [ACCEPTANCE_LEDGER](ACCEPTANCE_LEDGER.md), [VALIDATION_TOLERANCES](VALIDATION_TOLERANCES.md), [fundamentals](fundamentals/coordinates_and_units.md), [SOURCES](SOURCES.md) and [hardware/fidelity requirements](HARDWARE_AND_FIDELITY.md). All 20 inspected campaigns remain DEVELOPMENT under the prospective policy. Failure limits, qualified uncertainty, matching hardware and independent review remain required. Owner software-plan approval is not scientific certification.

**Twelve broad Phase 0 package issues and ten legacy M21–M30 acceptance families remain open.** They overlap the task breakdown; they are not 22 sequential tasks or 150 validated milestones. The master plan includes their exact crosswalk and distinct milestone checklists. Preserve M0–M20 reports as history; M31 expansion is split between Phase 0 drone families and later phases.

For a new builder: open `AGENTS.md`, follow the master task ID, record its exact proof, update the canonical task data, regenerate/sync checklists and commit a completed milestone. Require all five final-head CI jobs and unchanged dependency audits. All local work stays in [the canonical workspace](WORKSPACE.md).
