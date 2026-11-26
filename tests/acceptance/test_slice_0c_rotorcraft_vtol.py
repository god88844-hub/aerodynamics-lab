"""Slice 0C software verification: Helicopter BEMT rotor, IGE ground effect, VTOL transition, and solver contracts."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from physics.aerodynamics.rotorcraft_vtol import (
    build_detailed_solver_contract,
    compute_beam_modal_frequencies_hz,
    compute_tail_rotor_balance,
    run_vtol_transition_corridor,
    solve_helicopter_bemt_rotor,
)

ROOT = Path(__file__).resolve().parents[2]


def test_bemt_ground_effect_tail_torque_and_singularity_refusal():
    oge = solve_helicopter_bemt_rotor(
        radius_m=0.65,
        root_cutout_m=0.10,
        chord_m=0.055,
        n_blades=2,
        omega_rad_s=150.0,
        collective_deg=8.0,
        altitude_agl_m=40.0,
    )
    ige = solve_helicopter_bemt_rotor(
        radius_m=0.65,
        root_cutout_m=0.10,
        chord_m=0.055,
        n_blades=2,
        omega_rad_s=150.0,
        collective_deg=8.0,
        altitude_agl_m=0.65,
    )
    assert ige["thrust_n"] > oge["thrust_n"]
    assert ige["ige_factor"] > 1.05

    tail = compute_tail_rotor_balance(main_torque_nm=oge["torque_nm"], tail_arm_m=0.75, max_tail_thrust_n=120.0)
    assert tail["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    with pytest.raises(ValueError, match="ground effect domain"):
        solve_helicopter_bemt_rotor(
            radius_m=0.65, root_cutout_m=0.10, chord_m=0.055, n_blades=2, omega_rad_s=150.0, collective_deg=8.0, altitude_agl_m=0.15
        )


def test_vtol_transition_thermal_fail_modal_and_detailed_solver_contracts(tmp_path):
    nom = run_vtol_transition_corridor(
        mass_kg=3.0, wing_area_m2=0.45, max_rotor_thrust_n=45.0, max_cruise_thrust_n=25.0, motor_max_temp_c=110.0
    )
    assert nom["status"] == "completed" and nom["verdict"] == "NO_MODELED_LIMIT_BREACHED"

    hot = run_vtol_transition_corridor(
        mass_kg=3.0, wing_area_m2=0.45, max_rotor_thrust_n=45.0, max_cruise_thrust_n=25.0, ambient_temp_c=94.0, motor_max_temp_c=95.0
    )
    assert hot["status"] == "failed" and hot["verdict"] == "FAIL"

    modes = compute_beam_modal_frequencies_hz(
        length_m=0.4, youngs_modulus_pa=69e9, area_moment_m4=2e-9, linear_density_kg_m=0.35
    )
    assert modes["mode_2_hz"] > modes["mode_1_hz"] > 0.0

    admitted = build_detailed_solver_contract(solver_kind="openfoam_rans", mesh_cell_count=250_000, estimated_ram_mb=1200, available_ram_mb=8000)
    refused = build_detailed_solver_contract(solver_kind="calculix_fea", mesh_cell_count=2_000_000, estimated_ram_mb=7000, available_ram_mb=8000)
    assert admitted["admission_status"] == "admitted"
    assert "refused" in refused["admission_status"]

    in_path = tmp_path / "vtol_in.json"
    out_path = tmp_path / "vtol_out.json"
    in_path.write_text(json.dumps({"mass_kg": 3.0, "wing_area_m2": 0.45, "max_rotor_thrust_n": 45.0}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "vtol-transition", str(in_path), str(out_path)], check=True, cwd=ROOT)
    cli_res = json.loads(out_path.read_text(encoding="utf-8"))
    assert cli_res["status"] == "completed"
