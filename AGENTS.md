# Builder entry point

Read [ROADMAP](docs/ROADMAP.md), then the relevant numbered section of [MASTER_PLAN](docs/MASTER_PLAN.md). [PRODUCT_SPEC](docs/PRODUCT_SPEC.md) defines scope; [ACCEPTANCE_LEDGER](docs/ACCEPTANCE_LEDGER.md) records actual evidence.

All local project work belongs under **`C:\Users\Simulation apps\flights simulation`**. Use [WORKSPACE](docs/WORKSPACE.md) for data, caches, scratch/application state and relocated history. Do not recreate the previous Codex workspace or develop in archived worktrees. CI uses its own checked-out workspace.

Qualification passed and is complete. Current work is full software planning lock. Leave PR #126 open; **do not merge, tag `v0.0-plan-locked`, or begin Slice 0A before owner approval** (P0A-004). After that approval, the first implementation task is **P0A-005**, M21 cutoff regression. Execute Phase 0 in dependency order; WP7–WP9 start at their listed tasks, not through another qualification stage. Phases 1–4 remain contracts/registries only until their explicit entry gates.

Choose the first unchecked builder task whose dependencies are checked. Custodian/reviewer/owner tasks require real external receipts. Update `docs/planning/tasks.json`, regenerate `MASTER_PLAN.md`, sync the corresponding issue checklists and update scientific status separately. Each future acceptance-test path is a planned deliverable, not an existing capability. Do not mark a task done without its specified proof. Software slice exits and physical exits are different gates.

Follow [ARCHITECTURE](docs/ARCHITECTURE.md): Godot is the desktop, shared services live under `apps/api`; a local HTTP server is not required. `apps/web` is frozen legacy: security fixes and minimal CI/compatibility corrections only.

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
