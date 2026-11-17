"""Read-only audit of an externally preregistered physical test protocol.

Examples:
  python scripts/audit_validation_protocol.py --protocol protocol.json
  python scripts/audit_validation_protocol.py --protocol protocol.json --expected-sha256 <frozen-digest>
  python scripts/audit_validation_protocol.py --protocol protocol.json --manifests recorded-m19-manifests.json --output audit.json

A passing software audit is NOT approval to fly or demonstrated physical
simulation equivalence. Source identity and approval are user assertions.
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
from physics.validation.validation_protocol import (  # noqa: E402
    ProtocolAuditRequest, audit_protocol,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--manifests", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        manifests = (json.loads(args.manifests.read_text(encoding="utf-8"))
                     if args.manifests else [])
        body = ProtocolAuditRequest.model_validate({
            "protocol": protocol, "expected_frozen_sha256": args.expected_sha256,
            "imported_manifests": manifests,
        })
        result = audit_protocol(body)
        rendered = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if not result["blockers"] else 2
    except (ValueError, OSError, ValidationError) as exc:
        print(f"Validation protocol audit FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
