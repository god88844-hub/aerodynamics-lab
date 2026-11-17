#!/usr/bin/env python3
"""M26.15: run complete flight evidence dossier from separately pinned JSON.

Usage:
 python scripts/run_frozen_flight_campaign.py --original-root /originals \
   --source-manifest-json /metadata/source.json --source-manifest-sha256 HASH \
   --campaign-json /metadata/campaign.json --campaign-sha256 HASH \
   --output /reports/dossier.json

Exit: 2 invalid input, 3 numerical/physical-limit FAIL, 4 external physical
evidence INCONCLUSIVE. Exit 0 is reserved and is never returned for a claimed
physical validation PASS. Reports and original evidence never get overwritten.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from physics.validation.frozen_campaign_inputs import audit_frozen_campaign_inputs  # noqa: E402
from physics.validation.flight_evidence_dossier import build_flight_evidence_dossier  # noqa: E402
from physics.validation.external_flight_evidence_gaps import audit_external_flight_evidence_gaps  # noqa: E402


def cli(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-root", type=Path, required=True)
    p.add_argument("--source-manifest-json", type=Path, required=True)
    p.add_argument("--source-manifest-sha256", required=True)
    p.add_argument("--campaign-json", type=Path, required=True)
    p.add_argument("--campaign-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        original_root = a.original_root.resolve(strict=True)
        if not original_root.is_dir():
            raise ValueError("original evidence root must be an existing directory")
        outpath = a.output.resolve(strict=False)
        if outpath.is_relative_to(original_root):
            raise ValueError("report must be outside immutable original measurement root")
        if outpath.is_symlink() or outpath.exists():
            raise ValueError("report output already exists; never overwrite prior evidence")
        frozen = audit_frozen_campaign_inputs(
            source_manifest_json=a.source_manifest_json,
            source_manifest_sha256=a.source_manifest_sha256,
            campaign_json=a.campaign_json,
            campaign_sha256=a.campaign_sha256,
        )
        for input_path in (a.source_manifest_json, a.campaign_json):
            if outpath == input_path.resolve(strict=True):
                raise ValueError("report cannot replace source metadata")
        params = frozen["campaign"]
        protected = [
            Path(x["frozen_prediction_csv_path"]) for x in params["comparison_cases"]
        ] + [
            Path(x["document_path"]) for x in params["review_documents"]
        ]
        if any(outpath == path.resolve(strict=False) for path in protected):
            raise ValueError("report cannot replace frozen predictions or review documents")
        dossier = build_flight_evidence_dossier(
            original_root, frozen["source_manifest"],
            holdout_case=params["holdout_case"],
            required_metrics=params["required_metrics"],
            comparison_cases=params["comparison_cases"],
            required_limits=params["required_limits"],
            stress_cases=params["stress_cases"],
        )
        review = audit_external_flight_evidence_gaps(
            dossier, review_documents=params["review_documents"],
            original_root=original_root,
        )
        report = {
            "schema_version": "1.0",
            "status": review["status"],
            "frozen_campaign_input_verification": frozen["input_pin_report"],
            "recomputed_analytical_dossier": dossier,
            "external_physical_evidence_readiness": review,
            "physical_validation_accepted": False,
            "flight_or_manufacturing_release_authorized": False,
        }
        canonical = json.dumps(
            report, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        report["pre_digest_report_sha256"] = sha256(canonical).hexdigest()
        encoded = json.dumps(
            report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False,
        ) + "\n"
        # Exclusive creation also guards a race between our preflight and write.
        with outpath.open("x", encoding="utf-8") as fp:
            fp.write(encoded)
        print(json.dumps({
            "status": report["status"],
            "dossier": str(outpath),
            "report_sha256": report["pre_digest_report_sha256"],
            "physical_validation_accepted": False,
        }, sort_keys=True))
        return 3 if dossier["status"].startswith("FAIL_") else 4
    except (OSError, ValueError, TypeError, UnicodeError, KeyError) as exc:
        print(f"FLIGHT_CAMPAIGN_INPUT_OR_AUDIT_FAILED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(cli())
