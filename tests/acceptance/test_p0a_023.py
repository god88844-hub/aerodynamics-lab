"""P0A-023: Authoritative desktop simulation, edit->response causality, single RK4 integrator, playback state machine."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from aeroforge_schemas.project import import_legacy_project
from desktop_worker.environment_authoring import author_test_ground
from physics.dynamics.assembly_layout import build_multirotor_layout_and_bom
from physics.propulsion.loader import ComponentLibrary
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation
from physics.scenarios.mission_authoring import author_mission

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "data" / "components"
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def _base_project():
    raw = json.loads(LEGACY_DESIGN.read_text(encoding="utf-8"))
    proj = import_legacy_project(raw)
    return author_mission(
        proj,
        {
            "controller_dt_s": 0.004,
            "seed": 42,
            "phases": [
                {"phase": "takeoff", "duration_s": 0.4, "target_altitude_m": 2.0},
                {"phase": "hover", "duration_s": 0.4, "target_altitude_m": 2.0},
            ],
        },
    )


def test_geometry_environment_and_mission_edits_causally_change_response():
    base = _base_project()
    res_base = run_authoritative_desktop_simulation(base)
    assert res_base["result"]["status"] == "completed"
    assert res_base["execution_fidelity"]["integrator"] == "rk4_float64"

    # 1. Geometry/layout mass edit changes thrust and altitude response
    bom = build_multirotor_layout_and_bom(
        {
            "rotors": [
                {"position_m": [0.3, 0.0, 0.0], "spin_direction": 1},
                {"position_m": [0.15, 0.26, 0.0], "spin_direction": -1},
                {"position_m": [-0.15, 0.26, 0.0], "spin_direction": 1},
                {"position_m": [-0.3, 0.0, 0.0], "spin_direction": -1},
                {"position_m": [-0.15, -0.26, 0.0], "spin_direction": 1},
                {"position_m": [0.15, -0.26, 0.0], "spin_direction": -1},
            ],
            "motor_id": "tmotor_mn3508_kv380",
            "propeller_id": "tmotor_p15x5_cf",
            "esc_id": "generic_esc_20a",
            "battery_id": "generic_6s_lipo_16000mah",
            "frame_parts": [
                {"name": "center_hub", "material_id": "alu_6061_t6", "shape": "box", "dimensions_m": [0.22, 0.22, 0.015], "position_m": [0.0, 0.0, 0.0]}
            ],
        },
        ComponentLibrary(COMPONENTS),
    )
    edited_geom = base.model_copy(deep=True)
    edited_geom.experiment.parameters["layout_bom"] = bom
    res_geom = run_authoritative_desktop_simulation(edited_geom)
    assert res_geom["result"]["status"] in ("completed", "inconclusive")
    assert res_geom["result"]["aborted"] is False
    assert res_geom["result"]["telemetry"]["z"] != res_base["result"]["telemetry"]["z"]
    assert res_geom["result"]["telemetry"]["motor_thrusts_n"] != res_base["result"]["telemetry"]["motor_thrusts_n"]

    # 2. Environment edit (strong wind + thinner air) changes lateral velocity/position and rotor thrust headroom
    edited_env = author_test_ground(
        base,
        {
            "wind_world_m_s": [6.0, 0.0, 0.0],
            "temperature_k": 310.0,
            "pressure_pa": 80000.0,
            "relative_humidity": 0.2,
        },
    )
    res_env = run_authoritative_desktop_simulation(edited_env)
    assert res_env["result"]["telemetry"]["x"] != res_base["result"]["telemetry"]["x"]

    # 3. Mission edit changes target altitude response
    edited_mission = author_mission(
        base,
        {
            "controller_dt_s": 0.004,
            "seed": 42,
            "phases": [
                {"phase": "takeoff", "duration_s": 0.4, "target_altitude_m": 5.0},
                {"phase": "hover", "duration_s": 0.4, "target_altitude_m": 5.0},
            ],
        },
    )
    res_mission = run_authoritative_desktop_simulation(edited_mission)
    assert max(res_mission["result"]["telemetry"]["z"]) > max(res_base["result"]["telemetry"]["z"])


def test_propulsion_limit_breach_aborts_and_marks_component_fail():
    base = _base_project()
    # Aggressive climb target exceeding modeled static rotor thrust headroom
    over = author_mission(
        base,
        {
            "controller_dt_s": 0.004,
            "seed": 42,
            "phases": [{"phase": "takeoff", "duration_s": 0.4, "target_altitude_m": 40.0}],
        },
    )
    res = run_authoritative_desktop_simulation(over)
    assert res["result"]["status"] == "failed"
    assert res["result"]["aborted"] is True
    assert res["component_verdicts"]["propulsion"] == "FAIL"
    assert res["dual_digital_twin"]["design_verdict"] == "FAIL"
    assert res["dual_digital_twin"]["design_pass_fail_probability_pct"] == 0.0


def test_cli_simulate_and_desktop_playback_state_machine(tmp_path):
    base = _base_project()
    in_path = tmp_path / "sim_in.json"
    out_path = tmp_path / "sim_out.json"
    in_path.write_text(json.dumps({"project": base.model_dump(mode="json")}), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "simulate", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    cli_res = json.loads(out_path.read_text(encoding="utf-8"))
    assert cli_res["result"]["status"] == "completed"

    gd = (ROOT / "apps/desktop/main.gd").read_text(encoding="utf-8")
    for token in (
        '"Run authoritative"',
        '"Step +dt"',
        "_toggle_play_pause",
        "_step_replay",
        "_run_authoritative_sim",
        "playback_state",
    ):
        assert token in gd, f"missing {token} in main.gd"
