"""Inspect pinned third-party physical telemetry without treating it as simulation validation.

Usage:
    python scripts/audit_public_flight_evidence.py
    python scripts/audit_public_flight_evidence.py --output outputs/audit/public_physical_batt.json

The default command prints an evidence-quality report, not a flight-performance claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages"))
sys.path.insert(0, str(REPO / "packages" / "shared-schemas"))

from physics.validation.public_evidence import (  # noqa: E402
    audit_quadplane_battery, get_public_source_inventory,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="optional JSON output (will be overwritten)")
    args = parser.parse_args()
    report = {
        "schema_version": "1.0",
        "primary_goal": "independent model prediction accuracy vs physical measurements",
        "recorded_battery_observations": audit_quadplane_battery(),
        "external_dataset_inventory": get_public_source_inventory(),
        "aeroforge_aircraft_physical_equivalence_established": False,
    }
    serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
