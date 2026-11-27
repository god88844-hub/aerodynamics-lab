"""Phase 0D non-hardware software verification: coupled weather, SITL+EKF+LiDAR, AprilTag, reproducible ZIP + SBOM."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from aeroforge_schemas.project import EngineeringProject, import_legacy_project
from physics.autonomy.sitl_and_swarms import localize_fiducial_apriltag_proxy, run_sitl_closed_loop_mission
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def _load_ref_project() -> EngineeringProject:
    return import_legacy_project(json.loads(LEGACY_DESIGN.read_text(encoding="utf-8")))


def test_p0d_adverse_weather_coupled_into_authoritative_runner():
    base = _load_ref_project()
    dry = run_authoritative_desktop_simulation(base)

    wet_proj = EngineeringProject.model_validate(
        {
            **base.model_dump(mode="json"),
            "experiment": {
                **base.experiment.model_dump(mode="json"),
                "parameters": {
                    **dict(base.experiment.parameters or {}),
                    "adverse_weather": {
                        "turbulence_intensity": 0.18,
                        "rain_mm_h": 25.0,
                        "oat_c": -3.0,
                        "lwc_g_m3": 0.4,
                        "icing_exposure_s": 8.0,
                    },
                },
            },
        }
    )
    wet = run_authoritative_desktop_simulation(wet_proj)
    assert wet["adverse_weather_summary"] is not None
    assert wet["adverse_weather_summary"]["caveat_status"] == "SUPPORTED_WITH_CAVEATS"
    assert wet["physical_validation_status"] == "unvalidated"
    assert wet["adverse_weather_summary"]["icing"]["icing_active"] is True
    assert wet["adverse_weather_summary"]["icing"]["accreted_mass_kg"] > 0.0
    assert wet["result"]["telemetry"]["z"] != dry["result"]["telemetry"]["z"]


def test_p0d_sitl_ekf_lidar_closed_loop_and_fiducial_vision():
    for fw in ("ardupilot", "px4"):
        mission = run_sitl_closed_loop_mission(firmware_kind=fw)
        assert mission["firmware_kind"] == fw
        assert mission["verdict"] == "NO_MODELED_LIMIT_BREACHED"
        assert mission["channel_provenance"] == "SYNTHETIC"
        assert mission["physical_validation_status"] == "UNVALIDATED"
        assert mission["mean_ekf_position_error_m"] < 0.8

    tag_hit = localize_fiducial_apriltag_proxy(tag_world_m=(0.5, 0.2, 0.0), camera_pos_m=(0.0, 0.0, 4.0))
    assert tag_hit["detected"] is True
    assert tag_hit["channel_provenance"] == "SYNTHETIC"

    tag_miss = localize_fiducial_apriltag_proxy(tag_world_m=(12.0, 0.0, 4.0), camera_pos_m=(0.0, 0.0, 4.0))
    assert tag_miss["detected"] is False


def test_p0d_reproducible_installer_zip_and_sbom(tmp_path):
    stage_dir = tmp_path / "staged_app"
    zip_a = tmp_path / "AeroForge_a.zip"
    zip_b = tmp_path / "AeroForge_b.zip"

    res_a = subprocess.run(
        [sys.executable, str(ROOT / "scripts/package_windows_app.py"), str(stage_dir), "--zip", str(zip_a)],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    out_a = json.loads(res_a.stdout)
    assert Path(out_a["sbom_path"]).is_file()
    assert len(out_a["sbom_sha256"]) == 64

    res_b = subprocess.run(
        [sys.executable, str(ROOT / "scripts/package_windows_app.py"), str(stage_dir), "--zip", str(zip_b)],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    out_b = json.loads(res_b.stdout)
    assert out_a["installer_archive"]["archive_sha256"] == out_b["installer_archive"]["archive_sha256"]
