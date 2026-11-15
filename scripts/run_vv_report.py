"""CLI: generate the full V&V report (benchmarks + convergence + Monte Carlo
uncertainty) for a design, as JSON + human-readable Markdown.

Usage:
    python scripts/run_vv_report.py data/designs/quad_mn3508_6s.json --out outputs/vv_report
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

from aeroforge_schemas.design import DroneDesign  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.validation.report import generate_vv_report, render_markdown, write_vv_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an AeroForge V&V report.")
    parser.add_argument("design", help="Path to a design snapshot JSON.")
    parser.add_argument("--out", default=str(REPO_ROOT / "outputs" / "vv_report"))
    parser.add_argument("--uq-samples", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    design = DroneDesign.model_validate_json(Path(args.design).read_text(encoding="utf-8"))
    library = ComponentLibrary(REPO_ROOT / "data" / "components")

    report = generate_vv_report(design, library, uq_samples=args.uq_samples, uq_seed=args.seed)
    out_base = Path(args.out)
    write_vv_report(report, out_base)

    print(render_markdown(report))
    print(f"written: {out_base.with_suffix('.json')}, {out_base.with_suffix('.md')}")
    return 0 if not report["needs_further_analysis"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
