"""Audit timestamped telemetry bundles with pinned hashes and disjoint split groups.

Does not fetch sources, alter input, fit aircraft models or certify evidence.
Usage:
  python scripts/audit_telemetry_ingestion.py --root data/benchmarks/telemetry
  python scripts/audit_telemetry_ingestion.py --root path/to/bundles --output audit.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages"))
sys.path.insert(0, str(REPO / "packages" / "shared-schemas"))

from physics.validation.telemetry_ingestion import (  # noqa: E402
    DEFAULT_EVIDENCE_ROOT, audit_telemetry_directory,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DEFAULT_EVIDENCE_ROOT)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        report = audit_telemetry_directory(args.root)
        text = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    except (ValueError, OSError) as exc:
        print(f"Telemetry evidence audit FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
