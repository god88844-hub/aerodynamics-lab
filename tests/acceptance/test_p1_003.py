"""P1-003 Acceptance Tests: Unsteady Theodorsen/Wagner/LEV Strip-BEMT, Flexure Fatigue, and 1S Battery Coupling."""

from __future__ import annotations

import pytest

from aeroforge_schemas.bioinspired import (
    CompliantFlexureSpec,
    FlappingWingKinematics,
    MorphingWingState,
)
from aeroforge_schemas.component import BatterySpec, OcvPoint, SourceInfo
from physics.aerodynamics.bioinspired_flapping import (
    compute_theodorsen_lag_magnitude,
    compute_wagner_step_response,
    evaluate_compliant_flex_beam,
    evaluate_flapping_battery_coupled,
    evaluate_flapping_blade_element_strips,
    evaluate_morphing_wing_reflex,
)


def _sample_1s_battery(r_ohm: float = 0.065) -> BatterySpec:
    return BatterySpec(
        id="test_1s_500mah",
        name="1S 500mAh LiPo",
        chemistry="LiPo",
        cells_series=1,
        capacity_ah=0.5,
        internal_resistance_ohm=r_ohm,
        mass_kg=0.012,
        cutoff_cell_voltage_v=3.20,
        warning_cell_voltage_v=3.45,
        source=SourceInfo(source="FlapSim 1S 500mAh LiPo cell card"),
        ocv_curve=[
            OcvPoint(soc_pct=0.0, cell_voltage_v=3.20),
            OcvPoint(soc_pct=50.0, cell_voltage_v=3.80),
            OcvPoint(soc_pct=100.0, cell_voltage_v=4.20),
        ],
    )


def test_p1_003_wagner_theodorsen_and_strip_convergence() -> None:
    assert compute_theodorsen_lag_magnitude(0.0) == pytest.approx(1.0)
    assert compute_wagner_step_response(0.0) == pytest.approx(0.5)
    assert compute_wagner_step_response(100.0) > 0.99

    kin = FlappingWingKinematics(
        wing_span_r_m=0.08,
        mean_chord_c_m=0.028,
        flap_frequency_hz=40.0,
        stroke_amplitude_rad=1.36,
        stroke_plane_angle_rad=0.0,
        feathering_amplitude_rad=0.78,
        deviation_amplitude_rad=0.0,
        r11_moment=0.5,
        r22_moment=0.3333,
        r33_moment=0.25,
    )
    res16 = evaluate_flapping_blade_element_strips(kin, vehicle_mass_kg=0.032, n_strips=16)
    res32 = evaluate_flapping_blade_element_strips(kin, vehicle_mass_kg=0.032, n_strips=32)
    res64 = evaluate_flapping_blade_element_strips(kin, vehicle_mass_kg=0.032, n_strips=64)
    rel_16 = abs(res16["mean_lift_n"] - res64["mean_lift_n"]) / res64["mean_lift_n"]
    rel_32 = abs(res32["mean_lift_n"] - res64["mean_lift_n"]) / res64["mean_lift_n"]
    assert rel_32 < rel_16 < 0.02
    assert res64["hover_thrust_to_weight"] > 1.2

    # Refuse above M_tip = 0.25
    high_mach_kin = kin.model_copy(update={"flap_frequency_hz": 180.0, "wing_span_r_m": 0.14})
    with pytest.raises(ValueError, match="exceeds incompressible Phase 1 envelope"):
        evaluate_flapping_blade_element_strips(high_mach_kin, vehicle_mass_kg=0.032)


def test_p1_003_flex_divergence_and_1s_battery_coupling() -> None:
    kin = FlappingWingKinematics(
        wing_span_r_m=0.08,
        mean_chord_c_m=0.028,
        flap_frequency_hz=40.0,
        stroke_amplitude_rad=1.36,
        stroke_plane_angle_rad=0.0,
        feathering_amplitude_rad=0.78,
        deviation_amplitude_rad=0.0,
        r11_moment=0.5,
        r22_moment=0.3333,
        r33_moment=0.25,
    )
    coupled_ok = evaluate_flapping_battery_coupled(kin, vehicle_mass_kg=0.032, battery_spec=_sample_1s_battery(0.065))
    assert coupled_ok["battery_feasible"] is True
    assert coupled_ok["v_bus_v"] > 3.2

    # Degraded high-resistance pack must collapse causally
    coupled_bad = evaluate_flapping_battery_coupled(kin, vehicle_mass_kg=0.032, battery_spec=_sample_1s_battery(0.95))
    assert coupled_bad["battery_feasible"] is False
    assert coupled_bad["verdict"] == "FAIL"

    # Torsional divergence and S-N stress failure
    flex = CompliantFlexureSpec(
        material_id="cf_nylon",
        density_kg_m3=1380.0,
        density_source="tu_delft_delfly_flex_2026",
        flexural_rigidity_ei_nm2=0.045,
        torsional_rigidity_gj_nm2=0.008,
        endurance_fatigue_limit_pa=25e6,
        fatigue_safety_factor_min=1.25,
        max_cycle_count_budget=100_000,
    )
    div_fail = evaluate_compliant_flex_beam(
        flex, span_m=0.25, section_mass_kg=0.015, peak_distributed_load_n_m=2.0, applied_cycles=5000, airspeed_m_s=62.0
    )
    assert div_fail["divergence_margin"] < 1.5
    assert div_fail["verdict"] == "FAIL"

    morph = evaluate_morphing_wing_reflex(
        MorphingWingState(
            baseline_span_m=1.15,
            baseline_area_m2=0.21,
            wing_tuck_fraction=0.40,
            wing_asymmetry_diff=-0.15,
            tail_spread_fraction=0.90,
            tail_tilt_rad=0.10,
            tail_elevator_rad=0.02,
        )
    )
    assert morph["roll_moment_nm"] < 0.0
    assert morph["yaw_damping_coeff"] > 0.08
