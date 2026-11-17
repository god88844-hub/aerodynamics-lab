#!/usr/bin/env python3
"""Read-only public propulsion Dataverse metadata discovery.

Examples:
  python scripts/inspect_dataverse_propulsion.py --fetch-metadata
  python scripts/inspect_dataverse_propulsion.py --metadata-json exported-api.json
  python scripts/inspect_dataverse_propulsion.py --metadata-json exported-api.json --original-file downloaded-original.csv --file-id 123

--fetch-metadata retrieves metadata ONLY, not experimental file contents.
The operator must obtain original files under appropriate source permissions.
Zero exit means the audit ran, not that physical validation was established.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

# Permit direct execution from the repository root without a developer shell
# setting PYTHONPATH, matching the monorepo's packages/ source layout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from physics.validation.dataverse_candidate import (
    METADATA_URL, inspect_dataverse_candidate, inspect_original_local_file,
)

MAX_METADATA_BYTES = 2_000_000


def _remote_json() -> dict:
    req = Request(
        METADATA_URL,
        headers={"Accept": "application/json", "User-Agent": "AeroForge-ResearchMetadata/1.0"},
    )
    with urlopen(req, timeout=15) as resp:
        raw = resp.read(MAX_METADATA_BYTES + 1)
    if len(raw) > MAX_METADATA_BYTES:
        raise ValueError("Provider metadata exceeds maximum permitted size")
    return json.loads(raw.decode("utf-8"))


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="M22 external propulsion Dataverse candidate discovery; never authorizes physical validation"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--metadata-json", type=Path, help="Saved untouched official Dataverse API response")
    source.add_argument("--fetch-metadata", action="store_true", help="Fetch only official dataset JSON metadata")
    parser.add_argument("--original-file", type=Path, help="Already acquired original file to size/checksum audit, read only")
    parser.add_argument("--file-id", type=int, help="Official numerical file ID corresponding to --original-file")
    parser.add_argument("--output", type=Path, help="Optional JSON report file (not the original source)")
    args = parser.parse_args(argv)
    if (args.original_file is None) != (args.file_id is None):
        parser.error("--original-file and --file-id must be supplied together")
    try:
        if args.fetch_metadata:
            response = _remote_json()
        else:
            if not args.metadata_json.is_file() or args.metadata_json.stat().st_size > MAX_METADATA_BYTES:
                raise ValueError("Local metadata JSON must exist and be at most 2 MB")
            response = json.loads(args.metadata_json.read_text(encoding="utf-8"))
        report = inspect_dataverse_candidate(response)
        if args.original_file is not None:
            report["locally_staged_original_file"] = inspect_original_local_file(
                report, file_id=args.file_id, local_path=args.original_file
            )
        encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is not None:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 0  # Technical audit only. Physical validation always remains false.
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(2, f"UNVALIDATED_SOURCE_OR_METADATA_ERROR: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(cli())
