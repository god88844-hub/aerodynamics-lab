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


def test_recorded_frame_and_memory_decisions_reproduce_from_raw_receipts():
    root = Path(__file__).resolve().parents[2] / "docs/prototypes/measurements/assembly-200"
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, digest in manifest["files_sha256"].items():
        assert sha256((root / name).read_bytes()).hexdigest() == digest
    frames = json.loads((root / "final-viewport.json").read_bytes())
    memory = json.loads((root / "final-memory.json").read_bytes())
    samples = sorted(frames["frame_intervals_ms"])
    assert len(samples) == 600 and frames["part_count"] == 200
    assert samples[569] == frames["p95_ms"] <= 1000 / 30
    assert frames["mean_fps"] == pytest.approx(600000 / sum(samples))
    assert frames["viewport_target_met"] and frames["worker_stopped"]
    assert memory["desktop_pid"] == frames["desktop_pid"]
    assert memory["root_launcher_pid"] != memory["desktop_pid"] or memory["launcher_os_peak_resident_bytes"] == 0
    observed_peak = max(sum(p["resident_bytes"] for p in sample["processes"]
                            if p["pid"] not in (memory["desktop_pid"], memory["root_launcher_pid"]))
                        for sample in memory["samples"])
    assert observed_peak == memory["sampled_peak_worker_resident_sum_bytes"]
    assert memory["failure"] is None and memory["godot_exit_code"] == 0
    for key in ("cleanup_verified", "canonical_roundtrip_verified", "memory_attribution_valid", "source_assets_unchanged_verified"):
        assert memory[key] is True
    assert manifest["attempts"][-1]["source_commit"] == memory["commit_sha"]
    assert manifest["physical_validation_status"] == frames["physical_validation_status"] == "unvalidated"
