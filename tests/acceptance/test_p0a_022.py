"""P0A-022 acceptance tests: deterministic mission phase/command/disturbance authoring,
controller/sensor clock serialization, seed reproducibility, and render-cadence independence.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from aeroforge_schemas.project import EngineeringProject
from physics.scenarios.mission_authoring import author_mission, run_authored_mission

ROOT = Path(__file__).resolve().parents[2]
LAB_PROJECT = ROOT / "scripts" / "lab_project.py"
REFERENCE_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def test_authored_mission_replay_is_identical_and_render_independent(tmp_path):
    imported = tmp_path / "base.json"
    subprocess.run(
        [sys.executable, str(LAB_PROJECT), "import-legacy", str(REFERENCE_DESIGN), str(imported)],
        cwd=ROOT, check=True,
    )
    base_doc = json.loads(imported.read_text(encoding="utf-8"))

    mission_spec = {
        "controller_dt_s": 0.01,
        "sensor_sample_hz": 100.0,
        "sensor_latency_s": 0.02,
        "sensor_noise_sigma_m": 0.015,
        "seed": 20261126,
        "phases": [
            {"phase": "takeoff", "duration_s": 1.0, "target_altitude_m": 3.0},
            {"phase": "climb", "duration_s": 1.0, "target_altitude_m": 6.0},
            {"phase": "hover", "duration_s": 1.5, "target_altitude_m": 6.0},
            {"phase": "manual_command", "duration_s": 0.5, "target_altitude_m": 6.0, "manual_throttle_norm": 0.52},
            {"phase": "descent", "duration_s": 1.0, "target_altitude_m": 1.0},
            {"phase": "landing", "duration_s": 1.0, "target_altitude_m": 0.0},
        ],
        "disturbances": [
            {"start_s": 2.2, "duration_s": 0.5, "force_world_n": [0.0, 0.0, -2.5]}
        ],
    }

    req = tmp_path / "author_mission_req.json"
    authored = tmp_path / "authored_mission.json"
    req.write_text(json.dumps({"project": base_doc, "mission": mission_spec}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(LAB_PROJECT), "author-mission", str(req), str(authored)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr

    # Run mission twice via worker CLI at different render_fps_hint -> identical telemetry & digest
    run_60_in = tmp_path / "run60.json"
    run_144_in = tmp_path / "run144.json"
    authored_doc = json.loads(authored.read_text(encoding="utf-8"))
    run_60_in.write_text(json.dumps({"project": authored_doc, "mass_kg": 1.6, "render_fps_hint": 60.0}), encoding="utf-8")
    run_144_in.write_text(json.dumps({"project": authored_doc, "mass_kg": 1.6, "render_fps_hint": 144.0}), encoding="utf-8")

    out_60 = tmp_path / "out60.json"
    out_144 = tmp_path / "out144.json"
    assert subprocess.run([sys.executable, str(LAB_PROJECT), "run-mission", str(run_60_in), str(out_60)], cwd=ROOT).returncode == 0
    assert subprocess.run([sys.executable, str(LAB_PROJECT), "run-mission", str(run_144_in), str(out_144)], cwd=ROOT).returncode == 0

    res60 = json.loads(out_60.read_text(encoding="utf-8"))
    res144 = json.loads(out_144.read_text(encoding="utf-8"))
    assert res60["mission_sha256"] == res144["mission_sha256"]
    assert res60["telemetry"] == res144["telemetry"]
    assert res60["render_cadence_independent"] is True
    assert set(res60["telemetry"]["phase"]) == {"takeoff", "climb", "hover", "manual_command", "descent", "landing"}

    # Changing seed changes noisy sensor telemetry deterministically
    proj = EngineeringProject.model_validate(authored_doc)
    alt_proj = author_mission(proj, {**mission_spec, "seed": 99999})
    res_alt = run_authored_mission(alt_proj, mass_kg=1.6)
    assert res_alt["mission_sha256"] != res60["mission_sha256"]


def test_desktop_wires_mission_and_seed_authoring():
    main_gd = (ROOT / "apps" / "desktop" / "main.gd").read_text(encoding="utf-8")
    for sym in ("_open_mission_dialog", "_run_authored_mission", "author-mission"):
        assert sym in main_gd
