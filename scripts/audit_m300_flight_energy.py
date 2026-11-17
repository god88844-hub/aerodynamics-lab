#!/usr/bin/env python3
"""M26.30–M26.34 reproducible original-M300 flight energy screen.

The actual original Zenodo file must first have been legitimately acquired and
must pass its published provider MD5 and pinned local SHA-256. Source-specific
battery units, clock and current-discharge sign require reviewed documentation.
All results are conditional and never validate the AeroForge 60kg hexacopter.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from hashlib import sha256

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
from physics.validation.m300_original_energy import analyse_m300_original_energy
from physics.validation.m300_energy_holdout import score_frozen_m300_energy


def _reject_dups(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key forbidden")
        result[key] = value
    return result


def _reject_nan(raw):
    raise ValueError("JSON nonfinite numeric value forbidden")


def _read_json(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("JSON evidence must be a bounded nonsymlink existing file")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_dups,
                      parse_constant=_reject_nan)


def cli(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-csv", type=Path, required=True)
    p.add_argument("--acquisition-receipt-json", type=Path, required=True)
    p.add_argument("--explicit-mapping-json", type=Path, required=True)
    sub = p.add_subparsers(dest="mode", required=True)
    sub.add_parser("account")
    holdout = sub.add_parser("holdout")
    holdout.add_argument("--protocol-json", type=Path, required=True)
    holdout.add_argument("--predictions-json", type=Path, required=True)
    holdout.add_argument("--predictions-sha256", required=True)
    args = p.parse_args(argv)
    try:
        receipt = _read_json(args.acquisition_receipt_json)
        mapping = _read_json(args.explicit_mapping_json)
        if args.mode == "account":
            result = analyse_m300_original_energy(args.original_csv, receipt, mapping=mapping)
        else:
            result = score_frozen_m300_energy(
                args.original_csv, receipt, mapping=mapping,
                protocol=_read_json(args.protocol_json),
                frozen_prediction_json_path=args.predictions_json,
                frozen_prediction_sha256=args.predictions_sha256,
            )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        # 0 signifies a syntactically successful software audit, NEVER certified
        # physical accuracy, compatibility, or flight authorization.
        return 0 if args.mode == "account" else (
            3 if result["status"].startswith("FAIL_") else 4
        )
    except (OSError, ValueError, TypeError, KeyError, OverflowError,
            UnicodeError, json.JSONDecodeError) as exc:
        print(f"M300_SOURCE_ENERGY_EVIDENCE_INCONCLUSIVE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
