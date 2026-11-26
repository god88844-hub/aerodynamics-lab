"""CLI entry point to stage a standalone offline Aerodynamics Lab package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages"), str(ROOT / "packages/shared-schemas"), str(ROOT / "apps/api")]

from desktop_worker.windows_packaging import stage_standalone_package  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target_dir", type=Path)
    args = parser.parse_args()
    summary = stage_standalone_package(args.target_dir, repo_root=ROOT)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
