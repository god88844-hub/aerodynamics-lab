#!/usr/bin/env python3
"""Offline M300 original source profile or explicit official-download retry.

Only the exact pinned provider file can be downloaded; exploratory reports
are not physical aircraft validation or authorization to fly.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
from physics.validation.zenodo_official_fallback import alternate_zenodo_original_download
from physics.validation.zenodo_m300_exploratory_report import build_original_m300_exploratory_report
from physics.validation.frozen_campaign_inputs import _read_pinned_json

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest="action", required=True)
    retry = subs.add_parser("retry-official-download")
    retry.add_argument("--plan-json", type=Path, required=True)
    retry.add_argument("--plan-sha256", required=True)
    retry.add_argument("--original-out", type=Path, required=True)
    profile = subs.add_parser("profile-local")
    profile.add_argument("--original-file", type=Path, required=True)
    profile.add_argument("--receipt-json", type=Path, required=True)
    profile.add_argument("--receipt-sha256", required=True)
    profile.add_argument("--mapping-json", type=Path, required=True)
    profile.add_argument("--mapping-sha256", required=True)
    args = p.parse_args(argv)
    try:
        if args.action == "retry-official-download":
            plan, _ = _read_pinned_json(args.plan_json, args.plan_sha256, "official plan")
            report = alternate_zenodo_original_download(plan, output_file=args.original_out)
        else:
            receipt, _ = _read_pinned_json(args.receipt_json, args.receipt_sha256, "original receipt")
            mapping, _ = _read_pinned_json(args.mapping_json, args.mapping_sha256, "source column mapping")
            if set(mapping) != {"original_time_column","original_time_unit",
                                "declared_max_sample_gap_s","channel_mappings","reference_aircraft"}:
                raise ValueError("exact time, channels, envelope and aircraft mapping required")
            report = build_original_m300_exploratory_report(
                args.original_file, receipt, **mapping,
            )
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
        return 0  # Local technical audit ONLY, not physical scientific validation.
    except (ValueError, TypeError, OSError, UnicodeError, KeyError) as exc:
        print(f"ORIGINAL_M300_EVIDENCE_UNAVAILABLE_OR_UNQUALIFIED: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
