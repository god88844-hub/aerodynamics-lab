"""P0A-035: Bounded parameter sweeps, candidate retention, deterministic reproduction, and Pareto caveats."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from aeroforge_schemas.design import DroneDesign
from optimization.bounded_sweep import run_bounded_sweep
from physics.propulsion.loader import ComponentLibrary
from physics.structures.materials import load_materials

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"
COMPONENTS = ROOT / "data" / "components"


def test_bounded_sweep_retains_infeasible_candidates_and_reproduces_exactly():
    design = DroneDesign.model_validate_json(LEGACY_DESIGN.read_bytes())
    lib = ComponentLibrary(COMPONENTS)
    mat = load_materials(COMPONENTS / "materials.json")["cfrp_quasi_iso"]
    grid = {
        "battery_capacity_ah": [10.0, 16.0],
        "rotor_count": [4],
        "arm_length_m": [0.25, 0.45],
        "payload_kg": [0.0, 5.0],
    }
    first = run_bounded_sweep(
        design,
        lib,
        grid,
        material=mat,
        constraints={"max_mass_kg": 4.2, "min_structural_margin": 1.2},
        seed=77,
    )
    second = run_bounded_sweep(
        design,
        lib,
        grid,
        material=mat,
        constraints={"max_mass_kg": 4.2, "min_structural_margin": 1.2},
        seed=77,
    )
    assert first["total_candidates"] == 8
    assert first["infeasible_count"] > 0
    assert first["feasible_count"] + first["infeasible_count"] == first["total_candidates"]
    assert first["candidates_sha256"] == second["candidates_sha256"]
    assert first["candidates"] == second["candidates"]
    assert first["pareto_frontier"] == second["pareto_frontier"]
    assert any("does NOT validate physical flightworthiness" in c for c in first["caveats"])


def test_cli_bounded_sweep_and_ui_wiring(tmp_path):
    in_path = tmp_path / "sweep_in.json"
    out_path = tmp_path / "sweep_out.json"
    in_path.write_text(
        json.dumps(
            {
                "constraints": {"max_mass_kg": 4.0},
                "seed": 12,
                "grid_spec": {"battery_capacity_ah": [10.0], "rotor_count": [4], "arm_length_m": [0.3], "payload_kg": [0.0, 4.0]},
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "bounded-sweep", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    res = json.loads(out_path.read_text(encoding="utf-8"))
    assert res["total_candidates"] == 2
    assert res["infeasible_count"] >= 1

    gd = (ROOT / "apps/desktop/main.gd").read_text(encoding="utf-8")
    for token in ('"Bounded Sweep"', "_open_sweep_dialog", "_run_bounded_sweep", "bounded-sweep"):
        assert token in gd, token
