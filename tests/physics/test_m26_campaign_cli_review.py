"""M26.14–M26.16 integration, using ONLY fabricated source/prediction bytes."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from importlib import util
from pathlib import Path
import json

import pytest

from physics.validation.frozen_campaign_inputs import audit_frozen_campaign_inputs
from physics.validation.flight_evidence_dossier import build_flight_evidence_dossier
from physics.validation.external_flight_evidence_gaps import audit_external_flight_evidence_gaps


def _existing_fixture(tmp_path):
    path = Path(__file__).resolve().parent / "test_m26_limits_sensitivity_dossier.py"
    spec = util.spec_from_file_location("synthetic_m261113_test_fixtures", path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.case(tmp_path)


def _cli():
    path = Path(__file__).resolve().parents[2] / "scripts" / "run_frozen_flight_campaign.py"
    spec = util.spec_from_file_location("frozen_flight_campaign_cli", path)
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.cli


def bundle(tmp_path):
    root, manifest, holdout, metric, hard, comparisons, stressed = _existing_fixture(tmp_path)
    config = {
        "holdout_case": holdout,
        "required_metrics": [metric],
        "comparison_cases": comparisons,
        "required_limits": [hard],
        "stress_cases": stressed,
        "review_documents": [],
    }
    manifest_path = tmp_path / "source_manifest.json"
    campaign_path = tmp_path / "frozen_campaign.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    campaign_path.write_text(json.dumps(config, sort_keys=True), encoding="utf-8")
    kwargs = {
        "source_manifest_json": manifest_path,
        "source_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
        "campaign_json": campaign_path,
        "campaign_sha256": sha256(campaign_path.read_bytes()).hexdigest(),
    }
    return root, config, kwargs


def test_m2614_exact_input_bytes_lock_and_false_physical_claims(tmp_path):
    root, config, pins = bundle(tmp_path)
    current = deepcopy(config)
    audit = audit_frozen_campaign_inputs(**pins)
    assert audit["campaign"] == current
    assert audit["source_manifest"]["files"]
    assert len(audit["input_pin_report"]["pair_fingerprint_sha256"]) == 64
    assert not audit["input_pin_report"]["source_publisher_authenticated"]
    assert not audit["input_pin_report"]["physical_test_data_validated"]


def test_m2614_mutated_protocol_json_rejected_even_if_valid_json(tmp_path):
    root, config, pins = bundle(tmp_path)
    p = pins["campaign_json"]
    p.write_bytes(p.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit_frozen_campaign_inputs(**pins)


def test_m2614_duplicate_keys_and_nan_are_never_accepted(tmp_path):
    root, config, pins = bundle(tmp_path)
    p = pins["campaign_json"]
    p.write_text('{"holdout_case": {}, "holdout_case": {}}')
    pins["campaign_sha256"] = sha256(p.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="duplicate JSON key"):
        audit_frozen_campaign_inputs(**pins)
    p.write_text('{"holdout_case": NaN}')
    pins["campaign_sha256"] = sha256(p.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="nonfinite JSON constant"):
        audit_frozen_campaign_inputs(**pins)


def test_m2616_missing_independent_provenance_is_explicit(tmp_path):
    root, config, pins = bundle(tmp_path)
    manifest = audit_frozen_campaign_inputs(**pins)["source_manifest"]
    report = build_flight_evidence_dossier(
        root, manifest, holdout_case=config["holdout_case"],
        required_metrics=config["required_metrics"],
        comparison_cases=config["comparison_cases"],
        required_limits=config["required_limits"],
        stress_cases=config["stress_cases"],
    )
    gaps = audit_external_flight_evidence_gaps(
        report, review_documents=[], original_root=root,
    )
    assert gaps["status"] == "INCONCLUSIVE_EXTERNAL_PHYSICAL_VALIDATION_NOT_ESTABLISHED"
    assert len(gaps["review_document_kinds_missing"]) == 8
    assert not gaps["physical_decision_equivalence_established"]
    assert not gaps["flight_or_manufacturing_release_authorized"]


def test_m2616_all_self_claimed_documents_cannot_self_certify(tmp_path):
    root, config, pins = bundle(tmp_path)
    manifest = audit_frozen_campaign_inputs(**pins)["source_manifest"]
    report = build_flight_evidence_dossier(
        root, manifest, holdout_case=config["holdout_case"],
        required_metrics=config["required_metrics"],
        comparison_cases=config["comparison_cases"],
        required_limits=config["required_limits"],
        stress_cases=config["stress_cases"],
    )
    missing = audit_external_flight_evidence_gaps(
        report, review_documents=[], original_root=root,
    )["required_external_evidence_kinds"]
    docs = []
    for i, kind in enumerate(missing):
        p = tmp_path / f"claimed_document_{i}.txt"
        p.write_text("SYNTHETIC pretend certificate; no evidence of physical experiment", encoding="utf-8")
        docs.append({
            "evidence_kind": kind, "document_path": str(p),
            "document_sha256": sha256(p.read_bytes()).hexdigest(),
            "claimed_issuer": "synthetic operator; not authenticated",
        })
    gaps = audit_external_flight_evidence_gaps(
        report, review_documents=docs, original_root=root,
    )
    assert gaps["all_required_document_kinds_declared"]
    assert gaps["review_document_kinds_missing"] == []
    assert not gaps["all_review_issuers_and_contents_authenticated"]
    assert not gaps["physical_decision_equivalence_established"]
    docs[0]["document_sha256"] = "f"*64
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        audit_external_flight_evidence_gaps(
            report, review_documents=docs, original_root=root,
        )


def test_m2615_cli_produces_deterministic_conditional_report_and_exit_four(tmp_path, capsys):
    root, config, pins = bundle(tmp_path)
    out = tmp_path / "external_dossier.json"
    argv = [
        "--original-root", str(root),
        "--source-manifest-json", str(pins["source_manifest_json"]),
        "--source-manifest-sha256", pins["source_manifest_sha256"],
        "--campaign-json", str(pins["campaign_json"]),
        "--campaign-sha256", pins["campaign_sha256"],
        "--output", str(out),
    ]
    assert _cli()(argv) == 4
    brief = json.loads(capsys.readouterr().out)
    assert brief["status"] == "INCONCLUSIVE_EXTERNAL_PHYSICAL_VALIDATION_NOT_ESTABLISHED"
    report = json.loads(out.read_text())
    assert report["recomputed_analytical_dossier"]["all_declared_analytical_gates_passed"]
    assert not report["physical_validation_accepted"]
    assert not report["flight_or_manufacturing_release_authorized"]
    assert report["frozen_campaign_input_verification"]["pair_fingerprint_sha256"]
    old = out.read_bytes()
    assert _cli()(argv) == 2
    assert out.read_bytes() == old


def test_m2615_cli_refuses_write_inside_original_file_tree(tmp_path, capsys):
    root, config, pins = bundle(tmp_path)
    original = root / "flight1" / "rotor.csv"
    before = original.read_bytes()
    argv = [
        "--original-root", str(root),
        "--source-manifest-json", str(pins["source_manifest_json"]),
        "--source-manifest-sha256", pins["source_manifest_sha256"],
        "--campaign-json", str(pins["campaign_json"]),
        "--campaign-sha256", pins["campaign_sha256"],
        "--output", str(root / "new_report.json"),
    ]
    assert _cli()(argv) == 2
    assert original.read_bytes() == before
    assert not (root / "new_report.json").exists()


def test_m2615_cli_critical_failure_exits_three_and_never_approves(tmp_path):
    root, config, pins = bundle(tmp_path)
    config["required_limits"][0]["hard_limit_max"] = 2510.
    config["required_limits"][0]["envelope_max"] = 2509.
    p = pins["campaign_json"]
    p.write_text(json.dumps(config, sort_keys=True))
    pins["campaign_sha256"] = sha256(p.read_bytes()).hexdigest()
    report_path = tmp_path / "failed_dossier.json"
    args = [
        "--original-root", str(root),
        "--source-manifest-json", str(pins["source_manifest_json"]),
        "--source-manifest-sha256", pins["source_manifest_sha256"],
        "--campaign-json", str(pins["campaign_json"]),
        "--campaign-sha256", pins["campaign_sha256"],
        "--output", str(report_path),
    ]
    assert _cli()(args) == 3
    report = json.loads(report_path.read_text())
    assert report["status"] == "FAIL_CRITICAL_ANALYTIC_OR_OPERATING_LIMIT_SCREEN"
    assert not report["physical_validation_accepted"]


def test_m2616_review_file_cannot_reside_among_original_measurements(tmp_path):
    root, config, pins = bundle(tmp_path)
    manifest = audit_frozen_campaign_inputs(**pins)["source_manifest"]
    report = build_flight_evidence_dossier(
        root, manifest, holdout_case=config["holdout_case"],
        required_metrics=config["required_metrics"],
        comparison_cases=config["comparison_cases"],
        required_limits=config["required_limits"],
        stress_cases=config["stress_cases"],
    )
    p = root / "flight0" / "rotor.csv"
    with pytest.raises(ValueError, match="outside|immutable original measurement root"):
        audit_external_flight_evidence_gaps(
            report, review_documents=[{
                "evidence_kind": "original_recorder_custody",
                "document_path": str(p),
                "document_sha256": sha256(p.read_bytes()).hexdigest(),
                "claimed_issuer": "operator",
            }], original_root=root,
        )
