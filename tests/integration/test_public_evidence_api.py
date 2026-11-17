"""Public evidence HTTP contract: real third-party data does not validate the model."""
from fastapi.testclient import TestClient


def test_public_physical_evidence_route_cites_verbatim_source_and_limits():
    from app.main import app
    with TestClient(app) as client:
        resp = client.get("/api/components/public-evidence")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    audit = body["quadplane_battery_audit"]
    assert audit["source"]["git_blob_sha1"] == "1e434d8edcc26d5dfc016a557e24d5c44cffff3c"
    assert audit["quality"]["rows_verified"] == 1442
    assert audit["quality"]["per_row_timestamps_present"] is False
    assert audit["near_real_world_equivalence_established"] is False
    assert body["model_physically_validated_by_these_public_sources"] is False
    assert len(body["registry"]["datasets"]) >= 5
