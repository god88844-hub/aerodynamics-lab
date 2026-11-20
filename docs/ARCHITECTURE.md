# Desktop architecture and legacy boundary

The standalone Godot 3D application is the primary product. Foundation qualification passed and is complete. The current stage is the full [master software plan](MASTER_PLAN.md), pending owner approval of PR #126 and `v0.0-plan-locked`. After approval, execute the numbered Phase 0 dependencies; there is no new qualification stage before normal feature work.

## Authoritative execution path

```text
Godot desktop (GDScript)
  ├─ GDExtension → independent C++ engineering library
  └─ local process protocol → Python project / supervised CAD workers
       ├─ shared Python physics and engineering schemas
       ├─ CadQuery / Open CASCADE exact geometry
       └─ shared service functions currently located in apps/api/app/services

Legacy HTTP deployment → FastAPI routes → the same shared service / physics code
Legacy React client   → legacy HTTP deployment
```

The Godot desktop **does not require a running FastAPI HTTP server**. It invokes `scripts/lab_project.py` and `scripts/lab_worker.py` locally. Those workers currently import shared service functions from `apps/api/app/services`, including project, asset and simulation services. That source directory is therefore part of the present shared execution implementation, not dead server-only code. Its location does not imply a desktop HTTP dependency. A later package extraction requires compatibility tests and profiling; this change does not perform that migration.

`simulation_service.run_simulation` remains shared core behavior and serves persisted legacy API runs. Its provenance must describe the actual installed source/components/dependencies. Project and CAD wrappers retain their own environment checks. Engineering state is double precision with explicit SI/frame contracts. Verified engineering JSON remains authoritative; the rendering dictionary and display LOD cannot replace engineering inputs.

## Frozen legacy web application

**`apps/web` is frozen/legacy.** Do not add web UI features or duplicate desktop product work there. Security fixes and minimal compatibility corrections explicitly needed to preserve the existing CI/legacy interface remain allowed. Keep its required npm audit, unit tests, packaged application and HTTPS checks intact. Accessibility/UI/load WIP is archived, not silently promoted as a new web feature programme.

`apps/api` remains a maintained legacy HTTP adapter and contains currently reused service functions. There is one shared simulation behavior, not a separately tuned web physics engine. Changes to shared services must preserve existing saved inputs and reports, with explicit provenance/schema compatibility.

## Preserved pre-rename work

The full checkpoint `a1d7313146b687e78468df9a5b66a3920120092c` is retained without merging at [archive/aeroforge-wip-2026-11](https://github.com/god88844-hub/aerodynamics-lab/tree/archive/aeroforge-wip-2026-11). This branch is preservation evidence, not an accepted release. Its old CI may differ from current main.

The original checkpoint has 21 changed paths. Before provenance reconciliation, two exact utility/test files were already present on main and 19 paths had unpromoted changes. Integrating the two missing provenance-hook/test edits reduces the remaining unpromoted path count to 17; it does not change or merge the full archive. All unrelated changes remain quarantined.

The exact path dispositions and Git blob identities are recorded in [LEGACY_WIP_MANIFEST](LEGACY_WIP_MANIFEST.md).

## Planning lock and execution boundary

Leave PR #126 open for owner review. Merge/tag and Slice 0A begin only after approval (P0A-004); the first software task is P0A-005. CAD, detailed analysis, weather and autonomy follow their master-plan prerequisites. Phases 1–4 remain interfaces/registries only until their entry gates. Scientific acceptance still requires independent matching measurements and qualified review; green CI and a plan tag do not grant it.
