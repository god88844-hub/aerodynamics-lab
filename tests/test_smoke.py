"""Smoke tests for Milestone 0: packages importable, API app constructible."""

import physics


def test_physics_package_importable():
    assert physics.__version__


def test_api_health_endpoint():
    """Verify the API through its public HTTP contract rather than internal
    route objects (newer FastAPI versions wrap included routers in objects
    without `.path` — GitHub CI found this, M9 rev 2)."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "aeroforge-api"


def test_shared_schemas_package_importable():
    import aeroforge_schemas

    assert aeroforge_schemas.__doc__
