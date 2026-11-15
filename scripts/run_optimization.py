"""CLI: batch design-space evaluation over a declared grid, with a Pareto
frontier of (total mass) vs (hover endurance to the 3.5 V/cell warning).

Every candidate passes the same validation gates as manual designs; out-of-
envelope or structurally-failing candidates are flagged infeasible with the
reason recorded (never silently dropped).

Usage:
    python scripts/run_optimization.py                       # default grid (~480 candidates)
    python scripts/run_optimization.py --out outputs/pareto  # writes JSON + CSV
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from aeroforge_schemas.design import DroneDesign  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.structures.materials import load_materials  # noqa: E402
from optimization.batch import pareto_front, run_grid  # noqa: E402

DEFAULT_GRID = {
    "battery_capacity_ah": [6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0, 24.0],
    "rotor_count": [4, 6],
    "arm_length_m": [0.18, 0.21, 0.25, 0.30, 0.35],
    "payload_kg": [0.0, 1.0, 2.0, 3.0, 5.0, 8.0],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="AeroForge batch design evaluation.")
    parser.add_argument("--design", default=str(REPO_ROOT / "data" / "designs" / "quad_mn3508_6s.json"))
    parser.add_argument("--out", default=None, help="output basename (writes .json and .csv)")
    parser.add_argument("--max-endurance-h", type=float, default=24.0,
                        help="endurance cap [h] for the search")
    args = parser.parse_args()

    design = DroneDesign.model_validate_json(Path(args.design).read_text(encoding="utf-8"))
    if design.powertrain is None:
        print("error: the base design needs a powertrain block", file=sys.stderr)
        return 2
    library = ComponentLibrary(REPO_ROOT / "data" / "components")

    material = None
    if design.frame is not None:
        materials = load_materials(library.data_dir / "materials.json")
        material = materials[design.frame.material_id]

    t0 = time.perf_counter()
    results = run_grid(design, library, DEFAULT_GRID, material=material,
                       max_endurance_s=args.max_endurance_h * 3600.0)
    elapsed = time.perf_counter() - t0

    feasible = [r for r in results if r.feasible]
    front = pareto_front(results)

    print("=" * 70)
    print(f"AeroForge batch evaluation — {len(results)} candidates in {elapsed:.1f} s")
    print(f"  feasible           : {len(feasible)}")
    print(f"  flagged infeasible : {len(results) - len(feasible)}")
    print(f"  Pareto frontier    : {len(front)} candidates (mass vs hover endurance)")
    print("=" * 70)
    print(f"{'cap[Ah]':>8} {'rot':>4} {'arm[m]':>7} {'payload':>8} {'mass[kg]':>9} "
          f"{'endur[min]':>10} {'margin':>7}  flags")
    for r in front:
        p = r.params
        endur_min = (r.endurance_to_warning_s / 60.0) if r.endurance_to_warning_s else None
        print(f"{p['battery_capacity_ah']:>8} {p['rotor_count']:>4} {p['arm_length_m']:>7} "
              f"{p['payload_kg']:>8} {r.mass_kg:>9.3f} "
              f"{endur_min:>10.1f} {r.structural_margin:>7.2f}  {','.join(r.flags) or '-'}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        rows = [r.as_row() for r in results]
        payload = {
            "base_design": design.name,
            "n_candidates": len(results),
            "n_feasible": len(feasible),
            "elapsed_s": round(elapsed, 2),
            "grid": DEFAULT_GRID,
            "pareto_front": [r.as_row() for r in front],
            "candidates": rows,
            "notes": [
                "battery mass/R scaled with capacity: ESTIMATED relations",
                "hover endurance = static hover to the 3.5 V/cell warning "
                "(perfect altitude hold, no wind)",
                "out-of-envelope and structurally-failing candidates are flagged "
                "infeasible with the reason recorded",
            ],
        }
        out.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        fieldnames = list(rows[0].keys())
        with out.with_suffix(".csv").open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nwrote {out.with_suffix('.json')} and {out.with_suffix('.csv')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
