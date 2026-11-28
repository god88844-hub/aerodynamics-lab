"""Phase 1 Contracts, Dataset Ingestion, and Incompressible Bio-Inspired Envelope Tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aeroforge_schemas.bioinspired import (
    BioInspiredVehicleContract,
    CompliantFlexureSpec,
    FlappingWingKinematics,
    MorphingWingState,
    UnsteadyAeroEnvelope,
)
from physics.aerodynamics.bioinspired_flapping import (
    compute_theodorsen_lag_magnitude,
    evaluate_compliant_flex_beam,
    evaluate_flapping_cycle_quasi_steady,
    evaluate_morphing_wing_reflex,
    verify_bioinspired_contract,
)
from physics.validation.phase1_dataset_eval import evaluate_all_phase1_datasets


def test_phase1_contracts_and_fail_closed_validation() -> None:
    kin = FlappingWingKinematics(
        wing_span_r_m=0.07,
        mean_chord_c_m=0.02,
        flap_frequency_hz=40.0,
        stroke_amplitude_rad=1.5,
        stroke_plane_angle_rad=0.0,
        feathering_amplitude_rad=0.75,
        deviation_amplitude_rad=0.0,
        r11_moment=0.5,
        r22_moment=0.3333,
        r33_moment=0.25,
    )
    flex = CompliantFlexureSpec(
        material_id="cf_nylon_unibody",
        density_kg_m3=1380.0,
        density_source="tu_delft_delfly_flex_2026",
        flexural_rigidity_ei_nm2=0.045,
        torsional_rigidity_gj_nm2=0.025,
        endurance_fatigue_limit_pa=45e6,
        fatigue_safety_factor_min=1.25,
        max_cycle_count_budget=100_000,
    )
    env = UnsteadyAeroEnvelope(
        max_tip_mach=0.15,
        reynolds_min=1_000.0,
        reynolds_max=200_000.0,
        strouhal_min=0.15,
        strouhal_max=0.60,
        max_reduced_freq_k=1.2,
    )
    contract = BioInspiredVehicleContract(
        id="flapsim_baseline",
        bio_mode="flapping_wing",
        total_mass_kg=0.030,
        flapping=kin,
        flexure=flex,
        envelope=env,
        biological_scaling_prohibited=True,
    )
    out = verify_bioinspired_contract(contract)
    assert out["physical_validation_status"] == "UNVALIDATED_BIOINSPIRED"
    assert out["flapping_eval"]["hover_tw"] if "hover_tw" in out["flapping_eval"] else out["flapping_eval"]["hover_thrust_to_weight"] > 0.5

    # Refuses supersonic / high-Mach flapping outside bio-inspired incompressible envelope
    with pytest.raises(ValidationError):
        UnsteadyAeroEnvelope(
            max_tip_mach=0.75,
            reynolds_min=1000.0,
            reynolds_max=50000.0,
            strouhal_min=0.1,
            strouhal_max=0.5,
            max_reduced_freq_k=1.0,
        )

    # Missing mode block fails closed
    with pytest.raises(ValidationError):
        BioInspiredVehicleContract(
            id="missing_morph",
            bio_mode="morphing_wing",
            total_mass_kg=1.2,
            flexure=flex,
            envelope=env,
        )


def test_phase1_physics_theodorsen_morphing_and_fatigue() -> None:
    assert compute_theodorsen_lag_magnitude(0.0) == pytest.approx(1.0)
    assert 0.5 < compute_theodorsen_lag_magnitude(0.5) < 1.0

    morph = MorphingWingState(
        baseline_span_m=1.2,
        baseline_area_m2=0.22,
        wing_tuck_fraction=0.5,
        wing_asymmetry_diff=0.2,
        tail_spread_fraction=0.8,
        tail_tilt_rad=0.15,
        tail_elevator_rad=0.05,
    )
    mr = evaluate_morphing_wing_reflex(morph, airspeed_m_s=14.0)
    assert mr["effective_span_m"] < 1.2
    assert mr["roll_moment_nm"] > 0.0

    flex = CompliantFlexureSpec(
        material_id="pa12_compliant",
        density_kg_m3=1010.0,
        density_source="eos_pa2200_datasheet",
        flexural_rigidity_ei_nm2=0.12,
        torsional_rigidity_gj_nm2=0.05,
        endurance_fatigue_limit_pa=25e6,
        fatigue_safety_factor_min=1.25,
        max_cycle_count_budget=5000,
    )
    ok_beam = evaluate_compliant_flex_beam(flex, span_m=0.18, section_mass_kg=0.012, peak_distributed_load_n_m=1.2, applied_cycles=1000)
    assert ok_beam["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    fail_beam = evaluate_compliant_flex_beam(flex, span_m=0.18, section_mass_kg=0.012, peak_distributed_load_n_m=1.2, applied_cycles=10000)
    assert fail_beam["verdict"] == "FAIL"


def test_phase1_collected_public_datasets_verified() -> None:
    rep = evaluate_all_phase1_datasets()
    assert rep["phase"] == 1
    assert rep["policy_role"] == "DEVELOPMENT"
    assert rep["physical_acceptance_granted"] is False

    df = rep["delfly_flex_2026"]
    assert df["flex_rows"] == 15 and df["nimble_rows"] == 15
    assert df["flex_mean_hover_fy_n"] > 0.19
    assert df["nimble_mean_hover_fy_n"] > 0.24
    assert df["pitch_moment_reversal_verified"] is True

    fs = rep["flapsim_single_thrust_flapper"]
    assert fs["peak_tip_mach"] < 0.20
    assert fs["hover_tw"] >= 0.9

    pb = rep["pigeonbot_and_avian_ct"]
    assert pb["pigeonbot_morph_combos"] == 81
    assert pb["pigeonbot_turbulence_levels"] == 7
    assert pb["ct_bo1_monotonic"] is True
    assert pb["ct_pf4_monotonic"] is True
