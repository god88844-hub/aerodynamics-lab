"""M22 offline static bench campaign audit; a numerical pass is NOT flight approval.

Usage:
 python scripts/audit_propulsion_campaign.py --request campaign.json --output audit.json
All source/measurement provenance remains operator-declared and unauthenticated.
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
from physics.propulsion.dataset import PowertrainDataset  # noqa: E402
from physics.propulsion.loader import ComponentLibrary  # noqa: E402
from physics.validation.propulsion_campaign import (  # noqa: E402
    PropulsionCampaignRequest, audit_propulsion_campaign,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        data = PropulsionCampaignRequest.model_validate_json(
            args.request.read_text(encoding="utf-8")
        )
        library = ComponentLibrary(ROOT / "data" / "components")
        motor = library.motor(data.motor_id)
        propeller = library.propeller(data.propeller_id)
        dataset = PowertrainDataset(
            motor, propeller.motor_test_data_key or propeller.id
        )
        report = audit_propulsion_campaign(dataset, data)
        serialized = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized, encoding="utf-8")
        print(serialized, end="")
        # Nonzero exit is deliberate. No physical validity grant exists yet.
        return 2 if not report["independent_static_propulsion_validation_established"] else 0
    except (OSError, ValueError, ValidationError, RuntimeError) as exc:
        print(f"Propulsion campaign audit FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
