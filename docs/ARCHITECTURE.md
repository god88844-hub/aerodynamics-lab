# Desktop architecture and legacy boundary

The standalone native C++20/OpenGL desktop application (`apps/native/`) is the primary product. It is a **100 % standalone, local, offline, zero-game-engine desktop application**: a normal user installs it once and can design, redesign custom parts, invent, simulate and learn with **zero server, Docker, or third-party game-engine runtime**. Legacy `apps/desktop/` (Godot 4.7 bridge) remains temporarily frozen only until `apps/native/` completes full CI parity, and will then be retired. See [SIMULATION_VISION_AND_REFERENCE_STACK](SIMULATION_VISION_AND_REFERENCE_STACK.md) for the Godot 4.7 Forward+ PBR / `gl_compatibility` dual visual profile, Dual Digital-Twin percentage scoring, and reference-platform mapping. The installer bundles everything needed for that: the desktop executable, the native/CAD runtime, the built-in component and material libraries, starter designs, lessons and compact reference benchmarks. Large multi-gigabyte raw external research datasets are **optional downloadable offline data packs** — never forced into the base installer and never required for the core offline workflow. Foundation qualification passed and is complete. The current stage is executing the numbered Phase 0 dependencies of the [master software plan](MASTER_PLAN.md); the plan is locked (`v0.0-plan-locked`) and Stage 0A is active. There is no new qualification stage before normal feature work.

## Authoritative execution path

```text
Native Desktop Workbench (apps/native/, C++20 + OpenGL 3.3 + Dear ImGui)
  ├─ direct C++20 link → independent lab_core engineering library (packages/engineering-core)
  └─ local process protocol → Python project / supervised CAD workers
       ├─ shared Python physics and engineering schemas
       ├─ CadQuery / Open CASCADE exact geometry & custom part designer
       └─ shared service functions currently located in apps/api/app/services

Legacy Desktop Bridge (apps/desktop/, Godot) → frozen transition compatibility until native CI exit

Legacy HTTP deployment → FastAPI routes → the same shared service / physics code
Legacy React client   → legacy HTTP deployment
```

The native desktop (`apps/native/`) **does not require a running FastAPI HTTP server or Godot runtime**. It links `lab_core` directly and invokes `scripts/lab_project.py` and `scripts/lab_worker.py` locally. Those workers currently import shared service functions from `apps/api/app/services`, including project, asset and simulation services. That source directory is therefore part of the present shared execution implementation, not dead server-only code. Its location does not imply a desktop HTTP dependency. A later package extraction requires compatibility tests and profiling; this change does not perform that migration.

`simulation_service.run_simulation` remains shared core behavior and serves persisted legacy API runs. Its provenance must describe the actual installed source/components/dependencies. Project and CAD wrappers retain their own environment checks. Engineering state is double precision with explicit SI/frame contracts. Verified engineering JSON remains authoritative; the rendering dictionary and display LOD cannot replace engineering inputs.

## Frozen legacy web application

**`apps/web` and the `apps/api` HTTP server stack are frozen/legacy.** Do not add web UI features, new server features or duplicate desktop product work there. The desktop application must never depend on a running web/API server: shared service functions currently located in `apps/api/app/services` are part of the local worker implementation (see the authoritative execution path above) and move only through an explicitly planned, compatibility-tested extraction. Security fixes and minimal compatibility corrections explicitly needed to preserve the existing CI/legacy interface remain allowed for both. Keep their required npm audit, unit tests, packaged application and HTTPS checks intact. Accessibility/UI/load WIP is archived, not silently promoted as a new web feature programme.

`apps/api` remains a maintained legacy HTTP adapter; there is one shared simulation behavior, not a separately tuned web physics engine. Changes to shared services must preserve existing saved inputs and reports, with explicit provenance/schema compatibility.

## Preserved pre-rename work

The full checkpoint `a1d7313146b687e78468df9a5b66a3920120092c` is retained without merging at [archive/aeroforge-wip-2026-11](https://github.com/god88844-hub/aerodynamics-lab/tree/archive/aeroforge-wip-2026-11). This branch is preservation evidence, not an accepted release. Its old CI may differ from current main.

The original checkpoint has 21 changed paths. Before provenance reconciliation, two exact utility/test files were already present on main and 19 paths had unpromoted changes. Integrating the two missing provenance-hook/test edits reduces the remaining unpromoted path count to 17; it does not change or merge the full archive. All unrelated changes remain quarantined.

The exact path dispositions and Git blob identities are recorded in [LEGACY_WIP_MANIFEST](LEGACY_WIP_MANIFEST.md).

## Planning lock and execution boundary

Leave PR #126 open for owner review. Merge/tag and Slice 0A begin only after approval (P0A-004); the first software task is P0A-005. CAD, detailed analysis, weather and autonomy follow their master-plan prerequisites. Phases 1–4 remain interfaces/registries only until their entry gates. Scientific acceptance still requires independent matching measurements and qualified review; green CI and a plan tag do not grant it.
