"""P0A-036: Standalone Windows package layout, licenses/notices, and clean rollback/recovery."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from desktop_worker.windows_packaging import (
    recover_user_project_after_corruption,
    safe_stage_update_or_rollback,
    stage_standalone_package,
)

ROOT = Path(__file__).resolve().parents[2]


def test_packaged_layout_executes_without_dev_checkout_or_http_server(tmp_path):
    pkg_dir = tmp_path / "AerodynamicsLabStandalone"
    summary = stage_standalone_package(pkg_dir, repo_root=ROOT)
    assert Path(summary["manifest_path"]).is_file()
    manifest = json.loads(Path(summary["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["http_server_required"] is False
    assert (pkg_dir / "LICENSE").is_file()
    assert (pkg_dir / "NOTICE_STANDALONE.txt").is_file()
    assert not (pkg_dir / "apps/web").exists()

    # Execute workflows from the isolated packaged layout (not dev checkout)
    work_dir = tmp_path / "user_projects"
    work_dir.mkdir()
    create_req = work_dir / "create_req.json"
    proj_path = work_dir / "project.json"
    create_req.write_text(
        json.dumps(
            {
                "name": "Clean User Standalone Drone",
                "aircraft_family": "multirotor",
                "template": "legacy_reference",
                "reference_design_path": str(pkg_dir / "data/designs/quad_mn3508_6s.json"),
            }
        ),
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    packaged_cli = pkg_dir / "scripts/lab_project.py"
    subprocess.run(
        [sys.executable, str(packaged_cli), "create", str(create_req), str(proj_path)],
        check=True,
        cwd=work_dir,
        env=env,
    )
    sim_out = work_dir / "sim.json"
    subprocess.run(
        [sys.executable, str(packaged_cli), "simulate", str(proj_path), str(sim_out)],
        check=True,
        cwd=work_dir,
        env=env,
    )
    sim_res = json.loads(sim_out.read_text(encoding="utf-8"))
    assert sim_res["result"]["status"] == "completed"

    # Corrupt project.json on disk and recover from the packaged recovery snapshot
    original_bytes = proj_path.read_bytes()
    proj_path.write_text("{CORRUPT_USER_EDIT", encoding="utf-8")
    recovered = recover_user_project_after_corruption(proj_path)
    assert recovered["project"]["name"] == "Clean User Standalone Drone"
    assert json.loads(proj_path.read_text(encoding="utf-8"))["name"] == "Clean User Standalone Drone"
    assert len(original_bytes) > 0


def test_failed_install_update_rolls_back_preserving_prior_install(tmp_path):
    install_dir = tmp_path / "install_app"
    stage_standalone_package(install_dir, repo_root=ROOT)
    marker = install_dir / "USER_MARKER.txt"
    marker.write_text("keep-me", encoding="utf-8")

    outcome = safe_stage_update_or_rollback(ROOT, install_dir, simulate_failure=True)
    assert outcome["status"] == "failed_rolled_back"
    assert outcome["rolled_back"] is True
    assert marker.read_text(encoding="utf-8") == "keep-me"
    assert (install_dir / "package_manifest.json").is_file()
