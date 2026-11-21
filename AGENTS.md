# Builder entry point

Read [ROADMAP](docs/ROADMAP.md), then the relevant numbered section of [MASTER_PLAN](docs/MASTER_PLAN.md). [PRODUCT_SPEC](docs/PRODUCT_SPEC.md) defines scope; [ACCEPTANCE_LEDGER](docs/ACCEPTANCE_LEDGER.md) records actual evidence.

All local project work belongs under **`C:\Users\Simulation apps\flights simulation`**. Use [WORKSPACE](docs/WORKSPACE.md) for data, caches, scratch/application state and relocated history. Do not recreate the previous Codex workspace or develop in archived worktrees. CI uses its own checked-out workspace.

## Standalone offline architecture (locked)

Aerodynamics Lab is a **100 % standalone, local, offline desktop application** (`apps/desktop/` Godot frontend + local C++20/Python/Open CASCADE core + local workers). The installer bundles the desktop executable, native/CAD runtime, built-in components, materials, starter designs, lessons and compact reference benchmarks — the user needs **zero server or Docker setup**. Large multi-GB raw external research datasets are optional downloadable offline data packs, never base-installer content. `apps/web/` and the `apps/api/` HTTP server stack are **frozen legacy**: no new features there, and the desktop application must never depend on a running web/API server. See [ARCHITECTURE](docs/ARCHITECTURE.md) and [PRODUCT_SPEC](docs/PRODUCT_SPEC.md).

## Plan-lock and execution hold (status)

Qualification passed and is complete. Owner authorization for conditional merge/tag is recorded in [P0A-004](docs/acceptance/P0A-004.md). PR #126 is merged at `5644110b`, the annotated tag `v0.0-plan-locked` exists and `main` is synchronized and green. **Stage 0A execution is ACTIVE**: P0A-005 (M21 SIT cutoff regression reproduction), P0A-006 (causal battery sag/cutoff propagation in the authoritative plant, strict-support battery contract, exact event bracketing, component FAIL verdicts; the SIT knee-anchor probe was refuted and the repaired model's held-out numbers equal the frozen baseline) and P0A-007 (mode-separated battery verification: measured-current replay vs prospective demand scored per unchanged source row, exact conservation identities, monotone 3-level timestep convergence; workbook scoring opt-in via `AEROFORGE_SIT_WORKBOOK`) are complete per [docs/acceptance/P0A-005.md](docs/acceptance/P0A-005.md), [docs/acceptance/P0A-006.md](docs/acceptance/P0A-006.md) and [docs/acceptance/P0A-007.md](docs/acceptance/P0A-007.md); the next builder task is P0A-008 (awaits owner instruction). There is no new qualification stage; Phases 1–4 remain contracts/registries only until their explicit entry gates.

## Legacy plans are read-only

Files `docs/M10_*` through `docs/M29_*` (and `docs/ROADMAP_STATUS_2026_11_17.md`) are **archived historical references**: read-only inputs that shaped [MASTER_PLAN](docs/MASTER_PLAN.md). They are never active work plans, never execution authority and must not be edited or resurrected as tasks. The only active plan is [MASTER_PLAN](docs/MASTER_PLAN.md) rendered from `docs/planning/tasks.json`.

## Working rules

When implementation is explicitly resumed, choose the first unchecked builder task whose dependencies are checked. Custodian/reviewer/owner tasks require real external receipts. Update `docs/planning/tasks.json`, regenerate `MASTER_PLAN.md`, run `python scripts/sync_issue_checklists.py` to sync the corresponding issue checklists and update scientific status separately. Each future acceptance-test path is a planned deliverable, not an existing capability. Do not mark a task done without its specified proof. Software slice exits and physical exits are different gates.

Follow [ARCHITECTURE](docs/ARCHITECTURE.md): Godot is the desktop, shared services live under `apps/api`; a local HTTP server is not required. `apps/web` and the `apps/api` HTTP server stack are frozen legacy: security fixes and minimal CI/compatibility corrections only.

Use [WP1–WP3 contracts](docs/contracts/README.md) and [fundamentals](docs/fundamentals/coordinates_and_units.md). Store SI, explicit frames, active Hamilton `wxyz` engineering quaternions and declared time bases. Convert source frames and Godot `xyzw` at boundaries. Exact CAD is authoritative; display LOD cannot change physics or evidence. Unsupported BEMT/VLM/CFD execution must remain refused.

Software verification, synthetic experiments, measured comparison and physical acceptance are distinct. Known applicable physical-limit excursions produce FAIL; missing inputs or unsupported behavior produce INCONCLUSIVE/unvalidated predictions. No invented post-failure behavior or synthetic-as-physical claims.

Use [data/registry.json](data/registry.json), [SOURCES](docs/SOURCES.md), [tolerances](docs/VALIDATION_TOLERANCES.md), and the relevant campaign. Preserve source bytes/hashes, license scope, hardware/conditions and calibration/partition history. All 20 inspected campaigns are DEVELOPMENT under the prospective policy, including historical holdouts. Mark unsourced/estimated parameters `UNVERIFIED_ESTIMATE`. Never invent a license, measurement, citation or successful acceptance result.

Before committing, run the checks appropriate to the changed boundary:

```text
python scripts/export_contracts.py --check
python scripts/reconcile_registry.py --check
python scripts/check_master_plan.py --check
pytest
pytest tests/cad tests/integration/test_project_assets.py
pytest tests/cad/test_reusable_worker.py tests/cad/test_worker_resources.py tests/integration/test_worker_admission.py tests/integration/test_worker_record_locking.py tests/integration/test_worker_retirement.py -o addopts='' -ra -s
```

Use locked backend/CAD environments; see [.github/workflows/ci.yml](.github/workflows/ci.yml). Desktop verification uses native CTest and normal Godot `smoke_test.gd`; do not replace local measurements with CI-host claims. Preserve completed [qualification receipts](docs/prototypes/QUALIFICATION_GATE_FOLLOWUP.md) as history; do not reopen that stage as a prerequisite for product development.

Required CI: `python-tests`, `desktop-foundation`, `windows-worker`, `web-build`, `packaged-app`. Preserve locked installation, backend/CAD audits and `npm audit --audit-level=moderate` including development dependencies. No audit bypasses. Bind results to the final PR head; identify synthetic merge checkouts and tree equivalence explicitly. Setup: [dev guide](docs/dev_guide.md).

Commit after each completed milestone. Preserve the [21-file remote archive](docs/ACCEPTANCE_LEDGER.md#preserved-baseline) and historical reports. Record exact commits, run URLs, measured limitations and pending review. Never promote a whole package from a narrow verification result.

## Builder handoff checklist

A new sequential builder agent needs exactly one read of this file plus [MASTER_PLAN](docs/MASTER_PLAN.md):

1. **State**: read this file top to bottom; [MASTER_PLAN](docs/MASTER_PLAN.md) "Next action and execution rules"; confirm `git log -1` matches `origin/main` (`git fetch origin && git status -sb`) and the latest recorded evidence in [ACCEPTANCE_LEDGER](docs/ACCEPTANCE_LEDGER.md); `git status` must be clean.
2. **Authority**: confirm an explicit owner instruction exists for the next task (implementation is held by default; custodian/reviewer/owner tasks need real external receipts).
3. **Task**: take the first unchecked builder task in [MASTER_PLAN](docs/MASTER_PLAN.md) whose `dependencies` are all `done` (currently **P0A-008**). Read its `language`, `target_files`, numbered `todos`, `verify_commands` and `acceptance`.
4. **Implement**: work only in the declared `target_files`; keep SI/frames/quaternion/time-base contracts; refuse unsupported mechanisms.
5. **Verify**: run the task's `verify_commands` plus the boundary checks above; the task's `planned_tests`/acceptance proof must pass on the final head.
6. **Record**: fill `docs/acceptance/<TASK>.md`, add `completion_evidence` to the task in `docs/planning/tasks.json`, regenerate `MASTER_PLAN.md` (`python scripts/check_master_plan.py --render`), sync issue checklists (`python scripts/sync_issue_checklists.py`), commit on a feature branch and open a PR.
7. **Merge**: after all five required CI jobs are green on the PR head, merge, confirm green `main`, update the ledger — then stop and wait for the next owner instruction unless execution is explicitly resumed.
