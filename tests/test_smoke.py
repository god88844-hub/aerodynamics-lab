"""Smoke tests for Milestone 0: packages importable, API app constructible."""

import physics


def test_physics_package_importable():
    assert physics.__version__


def test_api_app_importable():
    # The API app registers at least the health route.
    from app.main import app as fastapi_app

    paths = {route.path for route in fastapi_app.routes}
    assert "/api/health" in paths


def test_shared_schemas_package_importable():
    import aeroforge_schemas

    assert aeroforge_schemas.__doc__
