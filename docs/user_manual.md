# AeroForge User Manual

AeroForge lets you assemble a multi-rotor drone from real components, run
engineering-grade physics, and get a verdict with uncertainty and
credibility attached. It is an engineering study tool, not a game: if any
component would exceed its real limits, the design fails.

## Web editor (M5)

```bash
cd apps/api  && python -m uvicorn app.main:app --port 8000
cd apps/web  && npm run dev
# open http://localhost:5173
```

- The editor loads the reference design (quad_mn3508_6s) automatically;
  saved designs are listed in the left panel.
- **Edit**: name, arm length (rotor placement regenerates), battery
  position/mass, powertrain picks from the evidence database (estimated
  components flagged), frame material/tube, drag CdA.
- The **preview** line comes from the physics core: mass, CoG, principal
  moments, hover-trim thrusts (or the reason trim is impossible).
- **Simulate**: saves the design snapshot, then runs the chosen scenario.
  The results panel shows metrics, events, success criteria and the
  trustworthiness section; charts show altitude/vz, motor currents and
  battery SOC/bus voltage; the 3D viewport draws the flight path.

## Simulation CLI (M1-M4)

```bash
python scripts/run_simulation.py data/designs/quad_mn3508_6s.json --scenario flight
python scripts/run_simulation.py data/designs/quad_mn3508_6s.json --scenario hover-static
python scripts/run_simulation.py data/designs/quad_example_2kg.json --scenario hover-ideal
```

Scenarios: `flight` (takeoff → 5 m → land, powertrain in the loop),
`hover-static` (endurance analysis), `hover-hold` (closed-loop disturbance
rejection), `hover-ideal` (dynamics verification, ideal actuators).

## Design-space exploration (M6)

```bash
python scripts/run_optimization.py --out outputs/pareto
# grid: battery capacity x rotor count x arm length x payload
# outputs: feasible candidates, flags, Pareto frontier (mass vs endurance)
```

Every candidate passes the same validation gates as manual designs;
infeasible ones are flagged with the reason.

## V&V report (M7)

```bash
python scripts/run_vv_report.py data/designs/quad_mn3508_6s.json --out outputs/vv_report
```

Emits benchmarks (gated, pre-registered tolerances), convergence studies
(time step, solver tolerance, closed-loop substeps), Monte Carlo endurance
uncertainty with a sensitivity ranking, and validated-vs-assumed lists.
Exit code 1 = a gate failed → the design needs further analysis.

## Capstone (M8)

```bash
python scripts/run_capstone.py --out outputs/capstone_report
```

Full mission suite for the 60 kg hexacopter (hover, climb, land, maneuver,
wind gust, motor failure) plus uncertainty and the credibility report with
nine design goals.

## Rules to expect

- A design passes only if **every** component stays within its operating
  limits during the whole scenario ("component failure = project failure").
- Operating points outside the measured envelope are flagged or refused —
  never silently extrapolated.
- If uncertainty crosses a requirement threshold, the verdict is
  INCONCLUSIVE / NEEDS FURTHER VALIDATION, and the report tells you which
  measurement would reduce uncertainty the most.
- Every result carries a verdict line of the form "NOT a flight-worthiness
  claim" until real hardware validation is performed.
