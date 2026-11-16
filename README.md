# AeroForge

Physics-based drone simulation lab — a modular digital-twin laboratory for
multi-rotor UAVs with verification & validation (V&V) built into every result.

## Mission

1. **Primary:** simulation evidence must be as reliable as physical testing
   *within its validated envelope*. Every result ships with a best estimate,
   quantified uncertainty, a credibility rating, and explicit caveats
   (philosophy of NASA-STD-7009 and ASME V&V 10). We never claim a design
   "flies" unless the model has demonstrated accuracy in that regime.
2. **Secondary:** multi-rotor drones only in v1 (quadcopters first). The system
   is structured so fixed-wing, VTOL, etc. can be added later as plugins, but
   they are **not** implemented now.

## Hard principles (enforced in code, not aspirational)

- **Physical grounding** — every component corresponds to real hardware or
  physics; SI units everywhere; every datum carries a `source` and
  `uncertainty`; unknown data blocks conclusions instead of being invented.
- **Traceability** — all inputs and assumptions are recorded in outputs;
  designs are reproducible from saved snapshots.
- **Component failure = project failure** — if any part exceeds its operating
  limits (over-current, undervoltage, yield stress, thermal limit), the design
  fails. A design "passes" only if *all* components stay in spec.
- **No fake data** — no hard-coded flight paths or magic numbers; every force
  is computed from models or measured data, labeled with its fidelity.
- **Validation before trust** — calibration data and validation data are kept
  separate; benchmarks with known targets gate every subsystem.
- **Uncertainty quantification** — key outputs report prediction intervals;
  if uncertainty exceeds safety margins the verdict is
  `Needs Further Validation` / `Inconclusive`, never "safe".

## Quickstart

### Backend (Python 3.11+, FastAPI)

```bash
cd apps/api
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
# http://127.0.0.1:8000/api/health
```

### Frontend (Node.js 22.12+, React + TypeScript + Vite)

```bash
cd apps/web
npm ci
npm audit --audit-level=moderate
npm run dev
# http://localhost:5173  (proxies /api to 127.0.0.1:8000)
```

### Tests

```bash
pytest                 # from repo root (pythonpath is set in pyproject.toml)
cd apps/web && npm test
```

### Simulation CLI

```bash
python scripts/run_simulation.py            # reports physics version
python scripts/run_simulation.py design.json  # scenario runner (Milestones 1-4)
```

## Repository layout

```
aeroforge/
  apps/
    web/                 # React front-end (editor, viewport, charts)
    api/                 # FastAPI backend
  packages/
    physics/             # core simulation logic
      dynamics/          # 6-DOF rigid body, quaternions, mass properties
      aerodynamics/      # drag, induced velocity, ground effect
      propulsion/        # motors, ESCs, propellers, batteries
      structures/        # stress/limit checks
      integration/       # RK4 + scipy ODE solvers
      validation/        # benchmarks, uncertainty, credibility scoring
    geometry/            # parametric primitives + inertia
    shared-schemas/      # Pydantic models shared by API and physics
    optimization/        # batch runs and design search (M6)
  data/
    components/          # sourced component databases (motors, props, ...)
    benchmarks/          # reference flight test data
    airfoils/
  scripts/               # CLI entry points
  tests/                 # pytest: physics / integration / regression / e2e
  docs/                  # architecture, validation strategy, manuals
```

## Milestone status

All milestones complete — see [docs/milestone_reports.md](docs/milestone_reports.md)
for the full per-milestone changelog, [docs/audit/M9_AUDIT.md](docs/audit/M9_AUDIT.md)
for the independent scientific validation audit (which capabilities are
independently validated, with what measured error, and which evidence gaps
remain), and [outputs/](outputs) for the generated capstone, V&V and Pareto
reports.

## Deviations from the original build specification

Per the spec's instruction, deviations are documented as they arise:

1. **`packages/shared-schemas/`** — the package directory is named
   `aeroforge_schemas/` (Python module names cannot contain `-`).
2. **Import strategy** — packages are made importable via `pythonpath`
   configuration (pytest / uvicorn / Docker `PYTHONPATH`) rather than an
   editable pip install; revisit if packaging for distribution is needed.
3. **uvicorn module path** — run as `app.main:app` from `apps/api/`
   (the spec's `api.app.main:app` would require an extra top-level shim).
4. **Persistence stack** — SQLAlchemy/Alembic are pinned in
   `apps/api/requirements.txt`; the migration environment is initialized with
   design persistence (M5) when there are real tables to migrate.

## License

[Apache License 2.0](LICENSE) — Copyright 2026 AeroForge contributors.
