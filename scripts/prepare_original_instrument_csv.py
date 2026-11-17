#!/usr/bin/env python3
"""Inspect, explicitly normalize, or replay an as-obtained vendor CSV source.

No action authenticates original physical measurements or grants flight release.
Original files/metadata must be acquired lawfully, provided locally and hashed.
Every successful execution is a TECHNICAL audit only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from physics.validation.frozen_campaign_inputs import _read_pinned_json  # noqa: E402
from physics.validation.flight_vendor_csv_inspector import inspect_original_vendor_csv  # noqa: E402
from physics.validation.flight_explicit_csv_conversion import write_derived_vendor_csv  # noqa: E402
from physics.validation.flight_derived_csv_replay import replay_derived_flight_csv  # noqa: E402


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--source-manifest-json", type=Path, required=True)
    parser.add_argument("--source-manifest-sha256", required=True)
    modes = parser.add_subparsers(dest="action", required=True)
    inspect = modes.add_parser("inspect")
    inspect.add_argument("--relative-path", required=True)
    convert = modes.add_parser("convert")
    convert.add_argument("--mapping-json", type=Path, required=True)
    convert.add_argument("--mapping-sha256", required=True)
    convert.add_argument("--derived-csv", type=Path, required=True)
    convert.add_argument("--provenance-json", type=Path, required=True)
    verify = modes.add_parser("verify")
    verify.add_argument("--derived-csv", type=Path, required=True)
    verify.add_argument("--provenance-json", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, _ = _read_pinned_json(
            args.source_manifest_json, args.source_manifest_sha256, "source manifest"
        )
        if args.action == "inspect":
            result = inspect_original_vendor_csv(
                args.original_root, manifest, relative_path=args.relative_path
            )
        elif args.action == "convert":
            mapping, _ = _read_pinned_json(
                args.mapping_json, args.mapping_sha256, "mapping"
            )
            result = write_derived_vendor_csv(
                args.original_root, manifest, mapping=mapping,
                derived_csv_path=args.derived_csv,
                provenance_json_path=args.provenance_json,
            )
        else:
            result = replay_derived_flight_csv(
                args.original_root, manifest,
                derived_csv_path=args.derived_csv,
                provenance_json_path=args.provenance_json,
            )
        print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
        return 0  # Local integrity/normalization workflow, NEVER physical acceptance.
    except (OSError, ValueError, TypeError, UnicodeError, KeyError) as exc:
        print(f"EXTERNAL_INSTRUMENT_CSV_PREPARATION_FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
