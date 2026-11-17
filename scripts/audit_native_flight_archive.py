#!/usr/bin/env python3
"""Offline review of existing *native* original flight files.

Examples, using legally obtained originals only:
  python scripts/audit_native_flight_archive.py --root /evidence/originals --hash-file flight01/pressure.tdms
  python scripts/audit_native_flight_archive.py --root /evidence/originals --manifest source_manifest.json

A green byte-integrity audit is NOT physical evidence authentication, and
does not open, decode or export arbitrary proprietary file formats.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from physics.validation.native_flight_archive import (  # noqa: E402
    audit_native_flight_archive, hash_original_archive_file,
)


def cli(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True,
                    help="Folder containing unmodified original instrument files")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--manifest", type=Path,
                      help="Frozen source inventory JSON; all files must exist and match")
    mode.add_argument("--hash-file", type=str,
                      help="Safe relative path to one unmodified file; computes a new SHA-256")
    ap.add_argument("--output", type=Path, help="Optional separate audit report path")
    args = ap.parse_args(argv)
    try:
        if args.hash_file is not None:
            result = hash_original_archive_file(args.root, args.hash_file)
        else:
            if (args.manifest.is_symlink() or not args.manifest.is_file()
                    or args.manifest.stat().st_size > 2_000_000):
                raise ValueError("manifest must be an existing non-symlinked file <= 2MB")
            obj = json.loads(args.manifest.read_text(encoding="utf-8"))
            result = audit_native_flight_archive(args.root, obj)
        out = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is not None:
            if args.output.resolve() == args.manifest.resolve() if args.manifest is not None else False:
                raise ValueError("audit output may not overwrite the source manifest")
            if args.output.resolve().is_relative_to(args.root.resolve()):
                raise ValueError("audit output must remain outside original evidence root")
            args.output.write_text(out, encoding="utf-8")
        print(out, end="")
        return 0
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"ORIGINAL_FLIGHT_ARCHIVE_AUDIT_FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
