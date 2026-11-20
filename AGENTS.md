# Builder entry point

Read [PRODUCT_SPEC](docs/PRODUCT_SPEC.md), [ROADMAP](docs/ROADMAP.md), and the canonical [ACCEPTANCE_LEDGER](docs/ACCEPTANCE_LEDGER.md) before selecting work. They define scope, dependency order, and actual evidence respectively.

Current authorization is foundation documentation, evidence reconciliation and prototype verification. **WP7–WP9, CAD expansion, physics code edits and Slice 0A execution remain held until explicit owner approval.** The local prototype PASS does not remove this hold. Leave the spec-lock PR open for review; do not create `v0.0-spec-lock` before approval. Phases 1–4 permit interface contracts and dataset registries only.

Follow [ARCHITECTURE](docs/ARCHITECTURE.md): Godot is the desktop, shared services live under `apps/api`; a local HTTP server is not required. `apps/web` is frozen legacy: security fixes and minimal CI/compatibility corrections only.

Use [WP1–WP3 contracts](docs/contracts/README.md) and [fundamentals](docs/fundamentals/coordinates_and_units.md). Store SI, explicit frames, active Hamilton `wxyz` engineering quaternions and declared time bases. Convert source frames and Godot `xyzw` at boundaries. Exact CAD is authoritative; display LOD cannot change physics or evidence. Unsupported BEMT/VLM/CFD execution must remain refused.

Software verification, synthetic experiments, measured comparison and physical acceptance are distinct. Known applicable physical-limit excursions produce FAIL; missing inputs or unsupported behavior produce INCONCLUSIVE/unvalidated predictions. No invented post-failure behavior or synthetic-as-physical claims.

Use [data/registry.json](data/registry.json), [SOURCES](docs/SOURCES.md), [tolerances](docs/VALIDATION_TOLERANCES.md), and the relevant campaign. Preserve source bytes/hashes, license scope, hardware/conditions and calibration/partition history. All 20 inspected campaigns are DEVELOPMENT under the prospective policy, including historical holdouts. Mark unsourced/estimated parameters `UNVERIFIED_ESTIMATE`. Never invent a license, measurement, citation or successful acceptance result.

Before committing, run the checks appropriate to the changed boundary:

```text
python scripts/export_contracts.py --check
python scripts/reconcile_registry.py --check
pytest
pytest tests/cad tests/integration/test_project_assets.py
pytest tests/cad/test_reusable_worker.py tests/cad/test_worker_resources.py tests/integration/test_worker_admission.py tests/integration/test_worker_record_locking.py tests/integration/test_worker_retirement.py -o addopts='' -ra -s
```

Use the locked backend environment for the general suite and the separate locked CAD environment for CAD/Windows worker tests; see [.github/workflows/ci.yml](.github/workflows/ci.yml). Desktop checks are native CTest and Godot `smoke_test.gd`. For local qualification use [the receipt harness](scripts/qualify_bundled_smoke.ps1) and [protocol/report](docs/prototypes/QUALIFICATION_GATE_LOCAL.md); do not replace local measurements with CI-host claims.

Required CI: `python-tests`, `desktop-foundation`, `windows-worker`, `web-build`, `packaged-app`. Preserve locked installation, backend/CAD audits and `npm audit --audit-level=moderate` including development dependencies. No audit bypasses. Bind results to the final PR head; identify synthetic merge checkouts and tree equivalence explicitly. Setup: [dev guide](docs/dev_guide.md).

Commit after each completed milestone. Preserve the [21-file remote archive](docs/ACCEPTANCE_LEDGER.md#preserved-baseline) and historical reports. Record exact commits, run URLs, measured limitations and pending review. Never promote a whole package from a narrow prototype result.
