#!/usr/bin/env python3
"""Offline M26 original-file intake, exact CSV reading and flight coverage.

All operations are read-only with respect to the source tree; any report
is saved outside the original source directory. Results cannot establish
real physical data custody or flightworthiness.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages"))

from physics.validation.flight_inventory_scaffold import draft_native_flight_manifest  # noqa: E402
from physics.validation.flight_channel_csv import audit_original_flight_channel_csv  # noqa: E402
from physics.validation.flight_channel_coverage import audit_original_flight_channel_coverage  # noqa: E402

MAX_INPUT_JSON_BYTES = 2_000_000


def _load(path: Path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUT_JSON_BYTES:
        raise ValueError("metadata must be an existing nonsymlink JSON file of at most 2MB")
    return json.loads(path.read_text(encoding="utf-8"))


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True,
                        help="Read-only directory of actual original source files")
    parser.add_argument("--output", type=Path,
                        help="Separate report path, never inside original source directory")
    modes = parser.add_subparsers(dest="mode", required=True)
    draft = modes.add_parser("draft", help="Generate exact-source manifest from file assignments")
    draft.add_argument("--assignments-json", type=Path, required=True,
                       help="JSON object supplying all draft_native_flight_manifest arguments except root")
    csv_mode = modes.add_parser("csv", help="Check one originally supplied CSV channel")
    csv_mode.add_argument("--manifest", type=Path, required=True)
    csv_mode.add_argument("--relative-path", type=str, required=True)
    csv_mode.add_argument("--channels-json", type=Path, required=True,
                          help="Map of exact observed channel to SI engineering unit")
    csv_mode.add_argument("--maximum-gap-s", type=float, required=True)
    coverage = modes.add_parser("coverage", help="Check whole-flight availability of required channels")
    coverage.add_argument("--manifest", type=Path, required=True)
    coverage.add_argument("--sources-json", type=Path, required=True,
                          help="List of original CSV sources including exact channel/unit and gap records")
    coverage.add_argument("--required-channels", type=str, required=True,
                          help="Comma-separated required supported channel names")
    coverage.add_argument("--minimum-flights", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        if args.mode == "draft":
            params = _load(args.assignments_json)
            if not isinstance(params, dict):
                raise ValueError("draft arguments must be an exact JSON object")
            out = draft_native_flight_manifest(args.root, **params)
        elif args.mode == "csv":
            out = audit_original_flight_channel_csv(
                args.root, _load(args.manifest),
                relative_path=args.relative_path,
                channels_with_units=_load(args.channels_json),
                maximum_declared_sample_gap_s=args.maximum_gap_s,
            )
        else:
            out = audit_original_flight_channel_coverage(
                args.root, _load(args.manifest),
                required_channels=args.required_channels.split(","),
                original_csv_sources=_load(args.sources_json),
                minimum_distinct_flights_per_channel=args.minimum_flights,
            )
        encoded = json.dumps(out, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is not None:
            target = args.output.resolve()
            if target.is_relative_to(args.root.resolve(strict=True)):
                raise ValueError("audit report cannot be saved inside original evidence directory")
            if any(
                target == supplied.resolve()
                for supplied in (
                    getattr(args, "assignments_json", None),
                    getattr(args, "manifest", None),
                    getattr(args, "channels_json", None),
                    getattr(args, "sources_json", None),
                ) if supplied is not None
            ):
                raise ValueError("audit report cannot overwrite a source metadata JSON")
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(f"ORIGINAL_FLIGHT_EVIDENCE_INTAKE_FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
