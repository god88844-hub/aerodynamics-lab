"""P0A-025: Numerical fidelity recording, interactive-vs-offline agreement, and resource/budget refusal."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from aeroforge_schemas.project import import_legacy_project
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation
from physics.scenarios.mission_authoring import author_mission

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def _sample_project():
    raw = json.loads(LEGACY_DESIGN.read_text(encoding="utf-8"))
    proj = import_legacy_project(raw)
    return author_mission(
        proj,
        {
            "controller_dt_s": 0.005,
            "seed": 99,
            "phases": [
                {"phase": "takeoff", "duration_s": 0.3, "target_altitude_m": 2.5},
                {"phase": "hover", "duration_s": 0.2, "target_altitude_m": 2.5},
            ],
        },
    )


def test_interactive_cli_and_offline_integration_agree_within_tolerance(tmp_path):
    proj = _sample_project()
    offline = run_authoritative_desktop_simulation(proj)
    fid = offline["execution_fidelity"]
    assert fid["requested_dt_s"] == pytest.approx(0.005)
    assert fid["effective_dt_s"] == pytest.approx(0.005)
    assert fid["step_count"] == 100
    assert fid["solver_rate_hz"] == pytest.approx(200.0)
    assert fid["numerical_error_estimate"] >= 0.0
    assert fid["quaternion_max_norm_drift"] < 1e-6
    assert fid["budget_within_limit"] is True

    in_path = tmp_path / "req.json"
    out_path = tmp_path / "res.json"
    in_path.write_text(json.dumps({"project": proj.model_dump(mode="json")}), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "simulate", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    interactive = json.loads(out_path.read_text(encoding="utf-8"))
    assert interactive["result"]["telemetry"]["z"] == pytest.approx(offline["result"]["telemetry"]["z"], abs=1e-12)
    assert interactive["result"]["telemetry"]["v_bus_v"] == pytest.approx(offline["result"]["telemetry"]["v_bus_v"], abs=1e-12)
    assert interactive["project_sha256"] == offline["project_sha256"]


def test_budget_refusal_preserves_project_without_corruption():
    proj = _sample_project()
    before_sha = proj.fingerprint()
    with pytest.raises(ValueError, match="step_budget_exceeded"):
        run_authoritative_desktop_simulation(proj, dt_s=0.0001, step_budget=100)
    assert proj.fingerprint() == before_sha


def test_desktop_fidelity_panel_wiring():
    gd = (ROOT / "apps/desktop/main.gd").read_text(encoding="utf-8")
    for token in ('"Fidelity / Budgets"', "_open_fidelity_dialog", "execution_fidelity"):
        assert token in gd, token
