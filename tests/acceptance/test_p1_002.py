"""P1-002 Acceptance Tests: Morphing/Flapping Geometry Contracts & Checksummed Public Datasets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aeroforge_schemas.bioinspired import (
    BioInspiredVehicleContract,
    CompliantFlexureSpec,
    FlappingWingKinematics,
    MorphingWingState,
    UnsteadyAeroEnvelope,
)
from physics.validation.phase1_dataset_eval import evaluate_all_phase1_datasets

ROOT = Path(__file__).resolve().parents[2]


def test_p1_002_contracts_roundtrip_and_provenance() -> None:
    kin = FlappingWingKinematics(
        wing_span_r_m=0.08,
        mean_chord_c_m=0.028,
        flap_frequency_hz=40.0,
        stroke_amplitude_rad=1.36,
        stroke_plane_angle_rad=0.0,
        feathering_amplitude_rad=0.78,
        deviation_amplitude_rad=0.05,
        r11_moment=0.52,
        r22_moment=0.35,
        r33_moment=0.25,
    )
    morph = MorphingWingState(
        baseline_span_m=1.15,
        baseline_area_m2=0.21,
        wing_tuck_fraction=0.30,
        wing_asymmetry_diff=0.12,
        tail_spread_fraction=0.75,
        tail_tilt_rad=0.14,
        tail_elevator_rad=0.04,
    )
    flex = CompliantFlexureSpec(
        material_id="cf_nylon_unibody",
        density_kg_m3=1380.0,
        density_source="tu_delft_delfly_flex_2026",
        flexural_rigidity_ei_nm2=0.045,
        torsional_rigidity_gj_nm2=0.025,
        endurance_fatigue_limit_pa=45e6,
        fatigue_safety_factor_min=1.25,
        max_cycle_count_budget=250_000,
    )
    env = UnsteadyAeroEnvelope(
        max_tip_mach=0.25,
        reynolds_min=800.0,
        reynolds_max=250_000.0,
        strouhal_min=0.12,
        strouhal_max=1.2,
        max_reduced_freq_k=1.5,
    )
    contract = BioInspiredVehicleContract(
        id="p1_002_contract_check",
        bio_mode="flapping_wing",
        total_mass_kg=0.032,
        flapping=kin,
        morphing=morph,
        flexure=flex,
        envelope=env,
        biological_scaling_prohibited=True,
    )
    restored = BioInspiredVehicleContract.model_validate_json(contract.model_dump_json())
    assert restored.biological_scaling_prohibited is True
    assert restored.physical_validation_status == "UNVALIDATED_BIOINSPIRED"
    assert restored.flapping.frames.body == "right_handed_x_forward_y_left_z_up"

    # Unordered radial moments must fail closed
    with pytest.raises(ValidationError):
        FlappingWingKinematics(
            wing_span_r_m=0.08,
            mean_chord_c_m=0.028,
            flap_frequency_hz=40.0,
            stroke_amplitude_rad=1.2,
            stroke_plane_angle_rad=0.0,
            feathering_amplitude_rad=0.6,
            deviation_amplitude_rad=0.0,
            r11_moment=0.30,
            r22_moment=0.50,
            r33_moment=0.25,
        )

    # Missing density_source provenance must fail closed
    with pytest.raises(ValidationError):
        CompliantFlexureSpec(
            material_id="bad_mat",
            density_kg_m3=1200.0,
            density_source="x",
            flexural_rigidity_ei_nm2=0.04,
            torsional_rigidity_gj_nm2=0.02,
            endurance_fatigue_limit_pa=40e6,
            fatigue_safety_factor_min=1.25,
            max_cycle_count_budget=10_000,
        )


def test_p1_002_public_datasets_are_strictly_development() -> None:
    report = evaluate_all_phase1_datasets()
    assert report["policy_role"] == "DEVELOPMENT"
    assert report["physical_acceptance_granted"] is False
    assert report["delfly_flex_2026"]["pitch_moment_reversal_verified"] is True
    assert report["pigeonbot_and_avian_ct"]["pigeonbot_morph_combos"] == 81
    reg = json.loads((ROOT / "data" / "registry.json").read_text(encoding="utf-8"))
    assert all(c["policy_role"] == "DEVELOPMENT" for c in reg["campaigns"])
