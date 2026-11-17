"""M27.3 integration: source hashes prove bytes only, never physical origin."""
from hashlib import sha256

from fastapi.testclient import TestClient
from app.main import app


def payload():
    runs = []
    for k in range(2):
        obs = "sample_id,t_s,observed,measurement_hard_bound\n" + "".join(
            f"s{i},{i*0.1:.1f},{10+k*.1+.1:.3f},0.05\n" for i in range(6)
        )
        pred = "sample_id,t_s,prediction,lower,upper\n" + "".join(
            f"s{i},{i*0.1:.1f},{10+k*.1:.3f},{10+k*.1-.3:.3f},{10+k*.1+.3:.3f}\n"
            for i in range(6)
        )
        runs.append({
            "run_id": f"synthetic_{k}", "group_id": f"distinct_fixture_{k}",
            "dataset_kind": "reported_physical_measurements",  # spoofed label, never proof
            "hardware_match": True, "unused_for_calibration": True,
            "observed_csv": obs, "observed_sha256": sha256(obs.encode()).hexdigest(),
            "prediction_csv": pred, "prediction_sha256": sha256(pred.encode()).hexdigest(),
        })
    return {
        "frozen_model_git_sha": "a"*40, "frozen_protocol_sha256": "b"*64,
        "channel": "terminal_voltage_v", "maximum_absolute_error": .2,
        "minimum_robust_coverage_fraction": 1., "calibration_group_ids": ["calibrator_1"],
        "runs": runs,
    }


def test_api_reports_consistency_not_real_world_equivalence():
    with TestClient(app) as client:
        res = client.post("/api/components/source-pinned-holdout-audit", json=payload())
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["status"] == "REPORTED_HOLDOUT_CONSISTENT_EXTERNAL_AUTHENTICATION_REQUIRED"
    assert out["source_bytes_integrity_verified_against_operator_supplied_digests"] is True
    assert out["source_identity_or_preregistration_externally_authenticated"] is False
    assert out["actual_independent_physical_validation_established"] is False
    assert out["decision_equivalent_to_physical_testing"] is False
    assert len(out["runs"]) == 2


def test_tampering_and_cross_run_source_reuse_are_rejected():
    with TestClient(app) as client:
        original = payload()
        original["runs"][0]["observed_csv"] += " "
        res = client.post("/api/components/source-pinned-holdout-audit", json=original)
        assert res.status_code == 422
        assert "digest mismatch" in res.text
        copied = payload()
        copied["runs"][1]["observed_csv"] = copied["runs"][0]["observed_csv"]
        copied["runs"][1]["observed_sha256"] = copied["runs"][0]["observed_sha256"]
        res = client.post("/api/components/source-pinned-holdout-audit", json=copied)
        assert res.status_code == 422
        assert "reused" in res.text


def test_api_synthetic_and_unknown_fields_cannot_produce_flight_proof():
    with TestClient(app) as client:
        req = payload()
        req["runs"][0]["dataset_kind"] = "synthetic_fixture"
        out = client.post("/api/components/source-pinned-holdout-audit", json=req)
        assert out.status_code == 200
        assert out.json()["status"] == "REPORTED_HOLDOUT_REJECTED"
        req = payload()
        req["physical_flight_authorized"] = True
        assert client.post("/api/components/source-pinned-holdout-audit", json=req).status_code == 422
        req = payload()
        req["runs"][1]["unused_for_calibration"] = False
        out = client.post("/api/components/source-pinned-holdout-audit", json=req)
        assert out.status_code == 200
        assert out.json()["status"] == "REPORTED_HOLDOUT_REJECTED"
