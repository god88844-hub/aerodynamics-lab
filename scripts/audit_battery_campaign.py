"""Offline M21 discharge-campaign consistency check; does NOT validate actual aircraft.

Usage:
  python scripts/audit_battery_campaign.py --request campaign.json --output audit.json

The frozen protocol and source files must preexist; this command neither
retrieves real measurements nor authenticates their physical origin.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT / "packages" / "shared-schemas"))

from pydantic import ValidationError  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.validation.battery_campaign import (  # noqa: E402
    BatteryCampaignRequest, audit_battery_campaign,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        body = BatteryCampaignRequest.model_validate_json(
            args.request.read_text(encoding="utf-8")
        )
        spec = ComponentLibrary(ROOT / "data" / "components").battery(
            body.battery_model_id
        )
        report = audit_battery_campaign(spec, body)
        output = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        print(output, end="")
        # Report-only: no M21 result currently establishes actual physical
        # pack equivalence; never exit successfully as though certified.
        return 2 if report["decision_equivalent_to_physical_testing"] is False else 0
    except (ValueError, OSError, ValidationError, RuntimeError) as exc:
        print(f"Battery campaign audit FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
