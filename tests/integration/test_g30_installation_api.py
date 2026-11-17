"""M17 HTTP contract: published measurements are evidence, not an aircraft pass."""
from fastapi.testclient import TestClient


def test_public_g30_bench_preserves_inconsistent_power_and_mismatch_flags():
    from app.main import app
    with TestClient(app) as client:
        response = client.get("/api/components/public-g30-benchmark")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["data_quality"]["published_measurement_count"] == 9
    assert result["data_quality"]["reported_power_inconsistency_count"] == 1
    assert result["comparison"]["in_envelope_count"] == 3
    assert result["reference"]["same_motor"] is False
    assert result["supports_aeroforge_electrical_power_comparison"] is False
    assert result["independent_physical_validation_of_aeroforge_reference"] is False
