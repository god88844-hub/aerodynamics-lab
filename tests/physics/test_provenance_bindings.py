"""M27.4 synthetic source-link fixtures, never physical validation."""
from copy import deepcopy
from hashlib import sha256

import pytest

from physics.validation.provenance_bindings import audit_provenance_bindings


def fixture():
    model, protocol, design = "a"*40, "b"*64, "c"*64
    payload = dict(
        frozen_model_git_sha=model,
        frozen_protocol_sha256=protocol,
        frozen_design_sha256=design,
        channel="voltage_v",
        maximum_absolute_error=0.3,
        minimum_robust_coverage_fraction=1.0,
        calibration_group_ids=["cal_group"],
        runs=[],
        evidence_sources=[],
    )
    def evidence(eid, exp, group, role, kind, digest):
        return {
            "evidence_id": eid, "experiment_id": exp,
            "group_id": group, "channel": "voltage_v",
            "role": role, "source_kind": kind,
            "source_sha256": digest,
            "source_reference": "synthetic source only; unverified origin",
            "frozen_model_git_sha": model,
            "frozen_protocol_sha256": protocol,
            "frozen_design_sha256": design,
        }
    payload["evidence_sources"].append(
        evidence("calibration", "exp_cal", "cal_group", "calibration",
                 "synthetic_fixture", "1"*64)
    )
    for i in range(2):
        obs = "sample_id,t_s,observed,measurement_hard_bound\n"
        pred = "sample_id,t_s,prediction,lower,upper\n"
        for n in range(6):
            t = n/10
            obs += f"s{n},{t:.1f},{10 + i/10 + .1:.2f},0.05\n"
            pred += f"s{n},{t:.1f},{10 + i/10:.2f},{9.5 + i/10:.2f},{10.5+i/10:.2f}\n"
        od, pd = sha256(obs.encode()).hexdigest(), sha256(pred.encode()).hexdigest()
        eid_obs, eid_pred = f"obs{i}", f"pred{i}"
        payload["runs"].append({
            "run_id": f"run{i}", "experiment_id": f"exp{i}",
            "group_id": f"group{i}",
            "dataset_kind": "reported_physical_measurements",  # spoofed in fixture
            "hardware_match": True, "unused_for_calibration": True,
            "observed_csv": obs, "prediction_csv": pred,
            "observed_sha256": od, "prediction_sha256": pd,
            "observation_evidence_id": eid_obs,
            "prediction_evidence_id": eid_pred,
        })
        payload["evidence_sources"].append(
            evidence(eid_obs, f"exp{i}", f"group{i}", "holdout",
                     "reported_physical_measurements", od)
        )
        payload["evidence_sources"].append(
            evidence(eid_pred, f"exp{i}", f"group{i}", "holdout",
                     "software_verification", pd)
        )
    return payload


def test_full_report_links_exact_bytes_but_never_certifies_physical_origin():
    payload = fixture()
    original = deepcopy(payload)
    result = audit_provenance_bindings(**payload)
    assert payload == original
    assert result["status"] == "ORIGINAL_BYTES_CROSS_LINKED_EXTERNAL_AUTHENTICATION_REQUIRED"
    assert result["source_binding_count"] == 4
    assert result["original_file_bytes_hashed_against_supplied_digests"]
    assert result["ledger_relationships_consistent"]
    assert not result["external_physical_source_authenticity_established"]
    assert not result["external_preregistration_or_independence_authenticated"]
    assert not result["simulation_equivalent_to_physical_validation"]
    assert not result["release_authorized"]


def test_one_swapped_manifest_digest_rejected():
    payload = fixture()
    payload["evidence_sources"][1]["source_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="original bytes/source inventory identity mismatch"):
        audit_provenance_bindings(**payload)


def test_cross_experiment_forgery_rejected():
    payload = fixture()
    payload["evidence_sources"][1]["experiment_id"] = "different_experiment"
    with pytest.raises(ValueError, match="identity mismatch"):
        audit_provenance_bindings(**payload)


def test_duplicate_references_rejected_before_positive_result():
    payload = fixture()
    payload["runs"][1]["observation_evidence_id"] = payload["runs"][0]["observation_evidence_id"]
    with pytest.raises(ValueError, match="duplicated evidence reference"):
        audit_provenance_bindings(**payload)


def test_raw_byte_change_cannot_be_hidden_by_unchanged_ledger():
    payload = fixture()
    payload["runs"][0]["observed_csv"] += " "
    with pytest.raises(ValueError, match="digest mismatch"):
        audit_provenance_bindings(**payload)


def test_synthetic_measurement_label_keeps_error_verdict_negative():
    payload = fixture()
    payload["runs"][1]["dataset_kind"] = "synthetic_fixture"
    result = audit_provenance_bindings(**payload)
    assert result["status"] == "OPERATOR_PROVENANCE_BINDINGS_REJECTED"
    assert not result["release_authorized"]


def test_ledger_calibration_and_holdout_group_sets_must_match_original_split():
    payload = fixture()
    payload["evidence_sources"][0]["group_id"] = "other_calibration_group"
    with pytest.raises(ValueError, match="calibration group inventory"):
        audit_provenance_bindings(**payload)
    payload = fixture()
    payload["evidence_sources"][1]["group_id"] = "irrelevant_holdout_group"
    with pytest.raises(ValueError, match="identity mismatch"):
        audit_provenance_bindings(**payload)
