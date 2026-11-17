# AeroForge Developer Guide

## Environment

- Python 3.11+ (backend + physics), Node 20+/22+ (frontend), git.
- Backend deps: `cd apps/api && python -m pip install -r requirements.txt`.
- Frontend deps: `cd apps/web && npm install`.

## Running

```bash
# API
cd apps/api
python -m uvicorn app.main:app --reload --port 8000

# Web (proxies /api to 127.0.0.1:8000)
cd apps/web
npm run dev

# Simulation CLI
python scripts/run_simulation.py [design_snapshot.json]
```

## Testing

```bash
pytest                    # all python tests (pythonpath set in pyproject.toml)
pytest tests/physics -q   # physics only
cd apps/web && npm test   # Rstest
```

CI (`.github/workflows/ci.yml`) runs pytest and the web build+tests on every
push; a failing test or lint breaks the build.

## Code layout

- `packages/physics/*` — simulation core. Pure Python + NumPy/SciPy. No API
  or UI imports allowed (keeps the core usable headless).
- `packages/shared-schemas/aeroforge_schemas` — Pydantic models shared by
  API and physics: the design snapshot format.
- `apps/api` — FastAPI routes/services/persistence only; heavy lifting lives
  in packages.
- `apps/web` — React editor/viewer; talks to the API exclusively.

## Adding a component

1. Add a JSON file under `data/components/<category>/` using the category
   schema (motor, propeller, battery, frame, sensor, controller).
2. Every numeric datum needs a `source` and `uncertainty`; a datum without a
   source must be marked `estimated: true` and carries a large uncertainty —
   or the design cannot use it.
3. Add/extend a benchmark under `data/benchmarks/` if the component has
   published test data; wire the benchmark test in `tests/physics/`.

## Adding a physics model

1. Implement in the right subpackage with explicit assumptions in the
   docstring (fidelity level, validity domain).
2. Unit-test against analytical solutions where they exist.
3. Register the model's validation status in the credibility report
   (measured / theory / approximation + evidence).
4. Run the regression suite; save a new baseline only when the change is
   intentional and documented.

## Coding standards

- SI units everywhere; unit-bearing names (`mass_kg`, `length_m`) in schemas
  and data files.
- No magic numbers: constants come from `data/` or named module constants
  with sources.
- Fail closed: unknown data or out-of-envelope operating points produce
  explicit errors/flags, never default behavior that looks like success.
- Docstrings state assumptions and limits, not just purpose.
