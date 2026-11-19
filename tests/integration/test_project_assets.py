from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest

from aeroforge_schemas.project import AssemblyVehicle, EngineeringProject, GeometryAsset
from app.services.project_assets import copy_assets, verify_assets


def test_asset_copy_verifies_source_and_preserves_conflicting_destination(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    (source / "assets").mkdir(parents=True)
    target.mkdir()
    original = b"original exact geometry"
    (source / "assets/part.step").write_bytes(original)
    project = EngineeringProject(
        id=uuid4(), name="CAD", aircraft_family="fixed_wing", vehicle=AssemblyVehicle(),
        assets=[GeometryAsset(id="part", path="assets/part.step",
                              sha256=sha256(original).hexdigest(), role="exact_geometry")],
    )
    destination = target / "project.json"
    copy_assets(project, source, destination)
    assert (target / "assets/part.step").read_bytes() == original
    verify_assets(project, target)
    copy_assets(project, source, destination)
    (target / "assets/part.step").write_bytes(b"another design")
    with pytest.raises(ValueError, match="SHA-256"):
        copy_assets(project, source, destination)
    assert (target / "assets/part.step").read_bytes() == b"another design"
    (source / "assets/part.step").write_bytes(b"changed source")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_assets(project, source)


def test_asset_document_collision_is_refused(tmp_path):
    original = b"original"
    (tmp_path / "project.json").write_bytes(original)
    project = EngineeringProject(
        id=uuid4(), name="CAD", aircraft_family="fixed_wing", vehicle=AssemblyVehicle(),
        assets=[GeometryAsset(id="part", path="project.json",
                              sha256=sha256(original).hexdigest(), role="parametric_source")],
    )
    with pytest.raises(ValueError, match="conflicts with an asset"):
        copy_assets(project, tmp_path, tmp_path / "project.json")
    assert (tmp_path / "project.json").read_bytes() == original
