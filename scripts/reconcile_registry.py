"""Build/check the canonical source index without changing legacy runtime catalogs.

--audit-local records workstation custody only; normal CI never requires external data.
Repository text hashes explicitly use LF-normalized bytes; originals use exact bytes.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = "data/registry.json"
CUSTODY = "data/research/custody-20261120.json"
CATALOGS = ("data/research/registry.json", "data/benchmarks/public_sources.json",
            "data/research/campaign_index.json", CUSTODY)


def read(root, path):
    return json.loads((root / path).read_text(encoding="utf-8-sig"))


def artifact(root, path):
    raw = (root / path).read_bytes()
    original = path.endswith("BATT.csv")
    hashed = raw if original else raw.replace(b"\r\n", b"\n")
    return {"path": path, "bytes_hashed": len(hashed), "sha256": sha256(hashed).hexdigest(),
            "hash_semantics": "EXACT_ORIGINAL_BYTES" if original else "LF_NORMALIZED_REPOSITORY_TEXT"}


def hash_references(value, path=""):
    """Preserve pins and JSON pointers without pretending every digest is a raw source."""
    if isinstance(value, dict):
        for key, child in sorted(value.items()):
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from hash_references(child, path + "/" + escaped)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from hash_references(child, path + "/" + str(i))
    elif isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value):
        yield {"json_pointer": path, "sha256": value.lower(),
               "semantics": "RECORDED_REFERENCE_CHECK_CONTEXT_NOT_AUTOMATICALLY_ORIGINAL"}


def generated(root=ROOT):
    research, public, index, custody = [read(root, p) for p in CATALOGS]
    sources = []
    for i, card in enumerate(research["entries"]):
        sources.append({**card, "catalog_reference": f"{CATALOGS[0]}#/entries/{i}",
                        "integration": "SEE_CAMPAIGNS_AND_CUSTODY_NOT_A_VALIDATION_CLAIM"})
    aliases = {"uiuc_propeller_database": "uiuc_propellers", "cmu_matrice100_209_flights": "cmu_m100",
               "quadplane_px4_2022": "quadplane_2022"}
    for i, card in enumerate(public["datasets"]):
        if card["id"] in aliases:
            next(s for s in sources if s["id"] == aliases[card["id"]]).setdefault("legacy_aliases", []).append(card["id"])
            continue
        sources.append({"id": card["id"], "title": card["name"], "kind": card["type"],
                        "urls": [card["url"]], "license": {"identifier": card["license_status"],
                        "scope": "Legacy metadata claim; inspect dataset-specific original terms before acquisition/reuse",
                        "terms_url": card["url"], "redistribution": "Not granted by this registry"},
                        "uncertainty_and_gaps": [card["cannot_validate"]],
                        "catalog_reference": f"{CATALOGS[1]}#/datasets/{i}"})
    sources.extend(index["additional_sources"])
    next(s for s in sources if s["id"] == "mdpi_g30_2025")["repository_paths"] = ["data/benchmarks/public/g30_2025/bench_table_5.json"]
    next(s for s in sources if s["id"] == "mdpi_g30_2025")["uncertainty_and_gaps"].append(
        "Nine transcribed published points, not raw sensor files; MN1010 motor and installation differ from P80 III. Published 3234 W row conflicts with 46.2 V * 0.7 A = 32.34 W; preserve original anomaly.")
    campaigns = []
    artifacts = set(CATALOGS)
    for descriptor in index["campaigns"]:
        prefix = descriptor["id"]
        paths = sorted(p.relative_to(root).as_posix() for p in (root / "docs/campaigns").glob(prefix + "*.json"))
        if not paths:
            raise ValueError(f"No artifacts for {prefix}")
        paths.append(descriptor["report"])
        artifacts.update(paths)
        pins, historical = [], []
        for path in paths:
            if not path.endswith(".json"):
                continue
            data = read(root, path)
            pins.extend({"artifact": path, **h} for h in hash_references(data))
            for key, value in data.items():
                if re.search("calibrat|holdout|split|source_files|source_sha|cohort|band", key):
                    historical.append({"artifact": path, "json_pointer": "/" + key, "original_value": value})
        campaigns.append({**descriptor, "policy_role": "DEVELOPMENT", "physical_acceptance": "UNVALIDATED",
                          "artifacts": paths, "recorded_hash_references": pins,
                          "historical_partitions": historical,
                          "limits": "Historical inspected comparison; not confirmatory under policy 1.0.0. See report for inputs, hardware, uncertainty and exclusions."})
    artifacts.update(a["path"] for a in research["local_custody"]["repository_artifacts"])
    artifacts.update(p.relative_to(root).as_posix() for p in (root / "data/benchmarks").rglob("*.json"))
    artifacts.update(["data/benchmarks/public/quadplane_2022/BATT.csv",
                      "data/benchmarks/uiuc/apce_10x5_static_pg0819.txt"])
    components = []
    for path in sorted((root / "data/components").rglob("*.json")):
        relative = path.relative_to(root).as_posix()
        artifacts.add(relative)
        data = read(root, relative)
        components.append({"artifact": relative, "id": data.get("id", "materials"),
                           "source_metadata": data.get("source", data.get("materials")),
                           "policy_role": "CALIBRATION_OR_SCREENING_NOT_INDEPENDENT_VALIDATION",
                           "physical_acceptance": "UNVALIDATED",
                           "license": "DATA_SPECIFIC_RIGHTS_UNRESOLVED_NOT_INHERITED_FROM_PROJECT",
                           "parameter_rule": "Unsourced/typical/generic parameters and assumed uncertainty bands are UNVERIFIED_ESTIMATE, even where a legacy source estimated flag is false; inspect parameter-level notes."})
    for source in sources:
        linked = [c["id"] for c in campaigns if source["id"] in c["source_ids"]]
        source["campaigns"] = linked
        is_tool = source.get("kind") in {"standard", "software", "software_comparison", "software_simulation", "restricted_software_reference", "software_calculated_thermochemistry"}
        acquired = linked or source.get("repository_paths") or any(r.get("source_id") == source["id"] for r in research["local_custody"]["external_files"])
        source["policy_role"] = "NOT_APPLICABLE_REFERENCE_OR_TOOL" if is_tool else ("DEVELOPMENT" if acquired else "UNASSIGNED_BEFORE_ACQUISITION_AND_PROTOCOL_REVIEW")
        source["physical_acceptance"] = "UNVALIDATED"
        # No future/unacquired source receives an invented hash.
        source["unacquired_original_sha256"] = None
        source["original_hash_location"] = "Linked campaign pins and dated custody; null means unacquired/unidentified, not a missing hash to invent"
    matches = []
    for record in custody["files"]:
        references = [{"campaign": c["id"], "source_ids": c["source_ids"], **h}
                      for c in campaigns for h in c["recorded_hash_references"] if h["sha256"] == record["sha256"]]
        legacy = [r for r in research["local_custody"]["external_files"] if r["sha256"] == record["sha256"]]
        if references or legacy:
            matches.append({**record, "campaign_pin_matches": references,
                            "legacy_source_ids": sorted({r["source_id"] for r in legacy if r.get("source_id")}),
                            "classification": "EXACT_PIN_MATCH_REVIEW_ORIGINAL_VS_DERIVED_CONTEXT_NOT_AUTHENTICATION"})
    return {"schema_version": "2.0", "checked_at": "2026-11-20", "canonical": True,
            "repository": research["repository"], "project_license": research["project_license"],
            "policy": {"version": "1.0.0", "path": "docs/VALIDATION_TOLERANCES.md",
                       "all_inspected_campaigns": "DEVELOPMENT", "physical_acceptance_granted": False,
                       "future_phases": "INTERFACES_AND_DATASET_REGISTRIES_ONLY"},
            "semantics": {"catalogs": "Dated legacy source metadata retained; no automatic refresh or rights grant",
                          "originals": "Exact bytes in dated external custody, not included by cloning; unmatched local files are not accepted source evidence",
                          "hashes": "Repository text explicitly LF-normalized; original source pins and external SHA-256 are exact bytes. Derived/model hashes remain labeled references.",
                          "licenses": "Article/code/data licenses differ; unresolved rights remain unresolved. No redistribution authorized here.",
                          "partitions": "Historical calibration/holdout roles preserved below, all now DEVELOPMENT under prospective policy"},
            "source_catalogs": [artifact(root, p) for p in CATALOGS], "sources": sources,
            "campaigns": campaigns, "component_calibration_inputs": components,
            "repository_artifacts": [artifact(root, p) for p in sorted(artifacts)],
            "external_custody": {"path": CUSTODY, "files": len(custody["files"]),
                                 "bytes": sum(f["bytes"] for f in custody["files"]),
                                 "status": "WORKSTATION_SNAPSHOT_NOT_SHIPPED_OR_AUTHENTICATED",
                                 "exact_pin_matches": matches}}


def validate(value):
    ids = [s["id"] for s in value["sources"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source identity")
    for source in value["sources"]:
        if not source.get("license") or not source.get("urls"):
            raise ValueError("Source needs explicit license scope and primary URL")
        if source["physical_acceptance"] != "UNVALIDATED":
            raise ValueError("Registry cannot promote physical acceptance")
    for campaign in value["campaigns"]:
        if campaign["policy_role"] != "DEVELOPMENT" or campaign["physical_acceptance"] != "UNVALIDATED":
            raise ValueError("Inspected campaign cannot be promoted to confirmatory/accepted")
        if not set(campaign["source_ids"]) <= set(ids):
            raise ValueError("Unknown campaign source identity")
    if len(value["campaigns"]) != 20:
        raise ValueError("Reconcile the complete 20-campaign baseline before changing its count")


def audit_local(root=ROOT):
    folder = root.parent / "source-physical"
    if not folder.is_dir():
        raise ValueError("External source directory unavailable; do not fabricate custody")
    files = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        digest = sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(block)
        files.append({"path": "../source-physical/" + path.relative_to(folder).as_posix(),
                      "bytes": path.stat().st_size, "sha256": digest.hexdigest(),
                      "classification": "LOCAL_FILE_NOT_AUTOMATICALLY_PUBLISHER_ORIGINAL",
                      "identity_rule": "Only a match to a documented original pin plus provenance identifies source bytes; derived fits/outputs remain derived"})
    (root / CUSTODY).write_text(json.dumps({"checked_at": "2026-11-20", "scope": "All files present in workstation source directory; includes derived files, not all are original evidence", "files": files}, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--audit-local", action="store_true")
    args = parser.parse_args()
    if args.audit_local:
        audit_local()
    result = generated()
    validate(result)
    if args.check:
        if read(ROOT, OUTPUT) != result:
            raise SystemExit("Registry drift: reconcile and review source/hash/role changes")
    else:
        (ROOT / OUTPUT).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Registry verified: {len(result['sources'])} sources, {len(result['campaigns'])} DEVELOPMENT campaigns; no physical acceptance")


if __name__ == "__main__":
    main()
