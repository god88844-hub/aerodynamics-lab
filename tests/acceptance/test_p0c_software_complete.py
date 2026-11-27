"""Phase 0C software verification: autorotation flare, coupled aero-thermo-structural VTOL, Pitt-Peters convergence, & lessons."""

from __future__ import annotations

from physics.aerodynamics.rotorcraft_vtol import (
    build_detailed_solver_contract,
    run_coupled_aero_thermo_structural,
    run_helicopter_autorotation_mission,
    verify_rotorcraft_convergence_and_inflow,
)
from desktop_worker.learning_experiments import create_rotorcraft_vtol_lesson_bundle


def test_p0c_helicopter_autorotation_flare_pass_and_rpm_fail():
    safe_auto = run_helicopter_autorotation_mission(flare_altitude_m=8.0, min_safe_rpm=950.0)
    assert safe_auto["aircraft_family"] == "helicopter"
    assert safe_auto["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert safe_auto["physical_validation_status"] == "UNVALIDATED"
    assert len(safe_auto["telemetry"]["t"]) == len(safe_auto["telemetry"]["q_wxyz"])

    high_rpm_fail = run_helicopter_autorotation_mission(initial_rpm=1100.0, min_safe_rpm=1080.0, flare_altitude_m=2.0)
    assert high_rpm_fail["verdict"] == "FAIL"
    assert high_rpm_fail["abort_reason"] is not None


def test_p0c_coupled_aero_thermo_structural_vtol_architectures():
    tilt = run_coupled_aero_thermo_structural(vtol_architecture="tilt_rotor", max_tip_deflection_mm=25.0)
    assert tilt["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert tilt["mode_1_hz"] > 10.0

    lpc = run_coupled_aero_thermo_structural(vtol_architecture="lift_plus_cruise", max_tip_deflection_mm=25.0)
    assert lpc["vtol_architecture"] == "lift_plus_cruise"

    excessive_flex = run_coupled_aero_thermo_structural(vtol_architecture="tilt_rotor", max_tip_deflection_mm=0.2)
    assert excessive_flex["verdict"] == "FAIL"
    assert "deflection" in str(excessive_flex["abort_reason"]).lower()


def test_p0c_bemt_convergence_pitt_peters_contract_and_lesson():
    conv = verify_rotorcraft_convergence_and_inflow()
    assert conv["refinement_monotone"] is True
    assert conv["pitt_peters_final_lambda0"] > 0.0

    refused_local = build_detailed_solver_contract(
        solver_kind="openfoam_rans",
        mesh_cell_count=8_000_000,
        estimated_ram_mb=24_000,
        available_ram_mb=16_000,
        execution_target="local",
    )
    assert refused_local["admission_status"] == "refused_offer_remote_or_smaller_mesh"

    lesson = create_rotorcraft_vtol_lesson_bundle(
        hypothesis="In-ground-effect cushion increases rotor thrust and timely flare arrests autorotation sink."
    )
    assert lesson["ige_thrust_gain_pct"] > 0.0
    assert lesson["autorotation_verdict"] == "NO_MODELED_LIMIT_BREACHED"
