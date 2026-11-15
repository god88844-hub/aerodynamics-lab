"""CLI entry point for running an AeroForge simulation scenario.

Milestone 0: verifies that the physics packages are importable and reports
versions. The full scenario runner (design snapshot in -> telemetry +
credibility report out) lands with Milestones 1-4.

Usage:
    python scripts/run_simulation.py
    python scripts/run_simulation.py path/to/design_snapshot.json
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (REPO_ROOT / "packages", REPO_ROOT / "packages" / "shared-schemas"):
    _s = str(_p)
    if _p.is_dir() and _s not in sys.path:
        sys.path.insert(0, _s)

import physics  # noqa: E402  (import after sys.path setup)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an AeroForge simulation scenario.")
    parser.add_argument("config", nargs="?", help="Path to a design snapshot JSON (M1+).")
    parser.add_argument("--output", help="Directory for telemetry + report outputs.")
    args = parser.parse_args()

    print(f"AeroForge physics {physics.__version__}")

    if args.config:
        print(
            "The scenario runner is implemented in Milestones 1-4. "
            f"Config {args.config!r} accepted but not yet simulated."
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
