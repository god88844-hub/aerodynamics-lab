#!/usr/bin/env python3
"""M26.25-29 explicit original source acquisition for the KIOS M300 Zenodo data.

The published KIOS DJI Matrice 300 record is not AeroForge's 60kg hexacopter.
Metadata inspection and checksum matching do not establish flight validation.
No automatic network access: `discover --fetch` or `download` are opt-in.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
from urllib.request import Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from physics.validation.zenodo_flight_candidate import (  # noqa: E402
    METADATA_API_URL, inspect_zenodo_m300_record,
)
from physics.validation.zenodo_original_download import (  # noqa: E402
    _NoRedirect, plan_original_zenodo_download, download_zenodo_original,
)
from physics.validation.zenodo_original_csv_schema import inspect_downloaded_m300_csv  # noqa: E402
from physics.validation.zenodo_m300_suitability import classify_m300_evidence_suitability  # noqa: E402


def _no_dup(pairs):
    values = {}
    for k, v in pairs:
        if k in values:
            raise ValueError("duplicate original metadata JSON key")
        values[k] = v
    return values


def _no_constant(v):
    raise ValueError("nonfinite metadata JSON forbidden")


def read_json(path: Path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 2_000_000:
        raise ValueError("small nonsymlink source metadata JSON required")
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_no_dup, parse_constant=_no_constant)


def cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    discover = sub.add_parser("discover", help="inspect official API-shaped metadata")
    discover.add_argument("--metadata-json", type=Path, help="provider response previously saved")
    discover.add_argument("--fetch", action="store_true", help="explicit official TLS API request")
    discover.add_argument("--save-metadata", type=Path, help="new file for returned metadata")
    plan = sub.add_parser("plan", help="plan a single published original file")
    plan.add_argument("--metadata-json", type=Path, required=True)
    plan.add_argument("--rights-review-ref", required=True)
    download = sub.add_parser("download", help="opt-in original transfer, hash-check, no overwrite")
    download.add_argument("--metadata-json", type=Path, required=True)
    download.add_argument("--rights-review-ref", required=True)
    download.add_argument("--output", type=Path, required=True)
    inspect = sub.add_parser("inspect", help="audit obtained original CSV")
    inspect.add_argument("--source-file", type=Path, required=True)
    inspect.add_argument("--acquisition-receipt", type=Path, required=True)
    classify = sub.add_parser("classify", help="assess against AeroForge reference hardware")
    classify.add_argument("--metadata-json", type=Path, required=True)
    classify.add_argument("--acquisition-receipt", type=Path)
    classify.add_argument("--csv-inspection-report", type=Path)
    classify.add_argument("--reference-aircraft", default="60 kg hexacopter")
    args = p.parse_args(argv)
    try:
        if args.action == "discover":
            if bool(args.fetch) == bool(args.metadata_json):
                raise ValueError("use exactly one of --fetch or --metadata-json")
            if args.fetch:
                req = Request(METADATA_API_URL, headers={
                    "Accept": "application/json", "User-Agent": "AeroForge-Evidence/1.0",
                })
                with build_opener(_NoRedirect()).open(req, timeout=30) as response:
                    if response.status != 200:
                        raise ValueError("official provider metadata request failed")
                    raw = response.read(2_000_001)
                    if len(raw) > 2_000_000:
                        raise ValueError("provider JSON larger than 2MB cap")
                obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_dup,
                                 parse_constant=_no_constant)
                result = inspect_zenodo_m300_record(obj)
                if args.save_metadata is not None:
                    with args.save_metadata.open("xb") as fp:
                        fp.write(raw)
            else:
                if args.save_metadata is not None:
                    raise ValueError("--save-metadata only valid with --fetch")
                result = inspect_zenodo_m300_record(read_json(args.metadata_json))
        elif args.action in ("plan", "download"):
            meta = inspect_zenodo_m300_record(read_json(args.metadata_json))
            pld = plan_original_zenodo_download(
                meta, source_use_review_reference=args.rights_review_ref,
            )
            result = (
                download_zenodo_original(pld, output_file=args.output)
                if args.action == "download" else pld
            )
        elif args.action == "inspect":
            result = inspect_downloaded_m300_csv(
                args.source_file, read_json(args.acquisition_receipt),
            )
        else:
            if args.csv_inspection_report and not args.acquisition_receipt:
                raise ValueError("CSV report needs matching acquisition receipt")
            result = classify_m300_evidence_suitability(
                inspect_zenodo_m300_record(read_json(args.metadata_json)),
                acquisition_receipt=(read_json(args.acquisition_receipt)
                                     if args.acquisition_receipt else None),
                source_csv_report=(read_json(args.csv_inspection_report)
                                   if args.csv_inspection_report else None),
                reference_aircraft_type=args.reference_aircraft,
            )
        print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            json.JSONDecodeError) as exc:
        print(f"OFFICIAL_ZENODO_SOURCE_ACQUISITION_INCONCLUSIVE: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
