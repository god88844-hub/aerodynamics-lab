"""The frozen workload exercises real project/asset entry points without flight claims."""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import pytest

from aeroforge_schemas.project import EngineeringProject
from app.services.project_assets import copy_assets, verify_assets
from app.services.project_service import run_project

ROOT = Path(__file__).resolve().parents[2] / "data/benchmarks/assembly-200"


def test_published_workload_is_portable_complete_and_physically_unvalidated(tmp_path):
    project = EngineeringProject.model_validate_json((ROOT / "project.json").read_bytes())
    manifest = json.loads((ROOT / "fixture.json").read_bytes())
    assert len(project.vehicle.nodes) == manifest["part_count"] == 200
    assert dict(Counter(node.name.split()[0] for node in project.vehicle.nodes)) == manifest["categories"]
    assert project.fingerprint() == manifest["project_sha256"]
    assert manifest["physical_validation_status"] == "unvalidated"
    assert len(project.assets) == 21
    verify_assets(project, ROOT)
    by_id = {asset.id: asset for asset in project.assets}
    for asset in project.assets:
        if asset.role == "display_mesh":
            mesh = json.loads((ROOT / asset.path).read_bytes())
            assert mesh["source_sha256"] == by_id[mesh["source_asset_id"]].sha256
            assert mesh["triangles"] and mesh["vertices_m"]
        if asset.role == "parametric_source":
            metadata = json.loads((ROOT / asset.path).read_bytes())
            assert by_id[metadata["exact_geometry_asset_id"]].role == "exact_geometry"
            assert metadata["physical_validation_status"] == "unvalidated"
    copy_assets(project, ROOT, tmp_path / "saved.json")
    verify_assets(project, tmp_path)
    with pytest.raises(ValueError, match="no implemented simulation backend"):
        run_project(project)


def test_asset_corruption_is_refused_even_for_shared_instances(tmp_path):
    project = EngineeringProject.model_validate_json((ROOT / "project.json").read_bytes())
    copy_assets(project, ROOT, tmp_path / "saved.json")
    target = tmp_path / project.assets[0].path
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_assets(project, tmp_path)
