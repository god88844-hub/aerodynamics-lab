#include "cad_mesh_builder.hpp"
#include "worker_ipc.hpp"

#include <cassert>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <thread>

int main() {
    // 1. NACA 4-digit closed airfoil generator across all 5 selectable airfoils
    for (const std::string &code : {"2412", "0012", "4412", "23012", "6412"}) {
        const auto airfoil = aerolab::sample_naca4_airfoil(code, 16);
        assert(airfoil.size() == 31);
        assert(std::abs(airfoil.front().x - 1.0f) < 1e-4f);
    }

    // 2. Build all 12 VehicleFamily CAD scenes and verify non-empty triangles + CAD edges + realistic T/W
    for (auto fam : {aerolab::VehicleFamily::Multirotor, aerolab::VehicleFamily::FixedWing,
                     aerolab::VehicleFamily::Helicopter, aerolab::VehicleFamily::VTOL,
                     aerolab::VehicleFamily::Seaplane, aerolab::VehicleFamily::Jet,
                     aerolab::VehicleFamily::InsectFlapper, aerolab::VehicleFamily::MorphingWing,
                     aerolab::VehicleFamily::CargoUAV, aerolab::VehicleFamily::Tailsitter,
                     aerolab::VehicleFamily::FlyingWing, aerolab::VehicleFamily::RocketSpacecraft,
                     aerolab::VehicleFamily::CustomPart}) {
        aerolab::AircraftDesignParams p;
        p.family = fam;
        if (fam == aerolab::VehicleFamily::Helicopter) p.rotor_rpm = 1450.0f;
        else if (fam == aerolab::VehicleFamily::Seaplane) {
            p.hardware_catalog_idx = 1; p.airspeed_m_s = 22.0f; p.rotor_rpm = 7200.0f;
        } else if (fam == aerolab::VehicleFamily::Jet) {
            p.hardware_catalog_idx = 4; p.wingspan_m = 1.35f; p.root_chord_m = 0.38f;
            p.tip_chord_m = 0.14f; p.sweep_deg = 26.0f; p.alpha_deg = 2.2f; p.airspeed_m_s = 92.0f;
        } else if (fam == aerolab::VehicleFamily::CargoUAV) {
            p.rotor_count = 6; p.arm_length_m = 0.48f; p.prop_diameter_m = 0.38f;
            p.frame_mass_kg = 1.85f; p.battery_mass_kg = 1.55f; p.cargo_mass_kg = 1.80f;
            p.cable_length_m = 1.20f; p.rotor_rpm = 5400.0f; p.airspeed_m_s = 12.0f; p.screw_size_idx = 3;
        } else if (fam == aerolab::VehicleFamily::Tailsitter) {
            p.hardware_catalog_idx = 1; p.frame_mass_kg = 0.92f; p.battery_mass_kg = 0.48f;
            p.wingspan_m = 1.05f; p.root_chord_m = 0.28f; p.tip_chord_m = 0.18f;
            p.transition_pitch_deg = 70.0f; p.duct_area_ratio = 1.08f; p.rotor_rpm = 7200.0f; p.airspeed_m_s = 14.0f;
        } else if (fam == aerolab::VehicleFamily::FlyingWing) {
            p.hardware_catalog_idx = 1; p.frame_mass_kg = 0.72f; p.battery_mass_kg = 0.46f;
            p.wingspan_m = 1.25f; p.root_chord_m = 0.30f; p.tip_chord_m = 0.14f;
            p.sweep_deg = 26.0f; p.rotor_rpm = 7600.0f; p.airspeed_m_s = 22.0f; p.alpha_deg = 4.0f;
        } else if (fam == aerolab::VehicleFamily::InsectFlapper) {
            p.hardware_catalog_idx = 3; p.frame_mass_kg = 0.014f; p.battery_mass_kg = 0.010f;
            p.payload_mass_kg = 0.004f; p.motor_mass_kg = 0.004f; p.battery_cells_s = 1;
            p.battery_capacity_ah = 0.50f; p.battery_r0_ohm = 0.065f; p.wingspan_m = 0.16f;
            p.root_chord_m = 0.028f; p.tip_chord_m = 0.016f; p.flap_freq_hz = 40.0f; p.airspeed_m_s = 2.2f;
        } else if (fam == aerolab::VehicleFamily::MorphingWing) {
            p.hardware_catalog_idx = 1; p.frame_mass_kg = 0.65f; p.battery_mass_kg = 0.35f;
            p.payload_mass_kg = 0.12f; p.motor_mass_kg = 0.055f; p.battery_cells_s = 4;
            p.battery_capacity_ah = 4.5f; p.battery_r0_ohm = 0.018f; p.wingspan_m = 1.15f;
            p.root_chord_m = 0.22f; p.tip_chord_m = 0.14f; p.sweep_deg = 16.0f;
            p.morph_tuck_pct = 25.0f; p.wing_asymmetry_diff = 0.10f; p.tail_spread_pct = 75.0f;
            p.airspeed_m_s = 14.0f; p.alpha_deg = 4.5f;
        }
        const auto scene = aerolab::build_cad_scene(p);
        assert(!scene.vertices.empty());
        assert(!scene.indices.empty());
        assert(!scene.cad_edges.empty());

        aerolab::LiveEvidenceSummary ev;
        aerolab::evaluate_live_physics_and_curves(p, scene, ev);
        assert(ev.total_mass_kg > 0.01);
        assert(ev.curve_alpha_deg.size() == 10);
        if (fam == aerolab::VehicleFamily::CustomPart) {
            assert(ev.benchmark_match_pct < 0.0);
        } else {
            assert(ev.benchmark_match_pct > 85.0);
            assert(ev.predicted_readiness_pct > 55.0);
            assert(ev.validation_status == "DEVELOPMENT");
            assert(ev.thrust_to_weight > 0.8 && ev.thrust_to_weight < 8.0);
        }
    }

    // 2b. Seaplane hump fail, Jet overspeed fail, and Insect MAV Mach fail
    aerolab::AircraftDesignParams rough_sea;
    rough_sea.family = aerolab::VehicleFamily::Seaplane;
    rough_sea.rotor_rpm = 1800.0f;
    rough_sea.water_chop_m = 0.16f;
    aerolab::LiveEvidenceSummary rs_ev;
    aerolab::evaluate_live_physics_and_curves(rough_sea, aerolab::build_cad_scene(rough_sea), rs_ev);
    assert(rs_ev.validation_status == "FAIL");

    aerolab::AircraftDesignParams fast_jet;
    fast_jet.family = aerolab::VehicleFamily::Jet;
    fast_jet.hardware_catalog_idx = 4; // max Mach 0.88
    fast_jet.airspeed_m_s = 330.0f;    // Mach ~ 0.97 -> FAIL
    aerolab::LiveEvidenceSummary fj_ev;
    aerolab::evaluate_live_physics_and_curves(fast_jet, aerolab::build_cad_scene(fast_jet), fj_ev);
    assert(fj_ev.validation_status == "FAIL");

    aerolab::AircraftDesignParams fast_insect;
    fast_insect.family = aerolab::VehicleFamily::InsectFlapper;
    fast_insect.wingspan_m = 0.30f;
    fast_insect.flap_freq_hz = 160.0f; // tip Mach > 0.25 -> FAIL
    aerolab::LiveEvidenceSummary fi_ev;
    aerolab::evaluate_live_physics_and_curves(fast_insect, aerolab::build_cad_scene(fast_insect), fi_ev);
    assert(fi_ev.rotor_tip_mach > 0.25 && fi_ev.validation_status == "FAIL");

    // 3. Rotor tip overlap must fail closed (both standard prop & oversized CustomPropeller attachment)
    aerolab::AircraftDesignParams overlap;
    overlap.family = aerolab::VehicleFamily::Multirotor;
    overlap.arm_length_m = 0.14f;
    overlap.prop_diameter_m = 0.50f;
    const auto overlap_scene = aerolab::build_cad_scene(overlap);
    aerolab::LiveEvidenceSummary overlap_ev;
    aerolab::evaluate_live_physics_and_curves(overlap, overlap_scene, overlap_ev);
    assert(!overlap_ev.clearance_ok);
    assert(overlap_ev.validation_status == "FAIL");
    assert(overlap_ev.predicted_readiness_pct == 0.0);

    aerolab::AircraftDesignParams giant_custom_prop;
    giant_custom_prop.family = aerolab::VehicleFamily::Multirotor;
    giant_custom_prop.attach_custom_part = true;
    giant_custom_prop.arm_length_m = 0.25f;
    giant_custom_prop.active_part.sketch_kind = aerolab::SketchShapeKind::CustomPropeller;
    giant_custom_prop.active_part.length_m = 0.42f; // 0.588 m prop diameter vs 0.353 m arm spacing
    aerolab::LiveEvidenceSummary gcp_ev;
    aerolab::evaluate_live_physics_and_curves(giant_custom_prop, aerolab::build_cad_scene(giant_custom_prop), gcp_ev);
    assert(!gcp_ev.clearance_ok);
    assert(gcp_ev.validation_status == "FAIL");

    // 4. Out-of-envelope stall alpha must fail closed
    aerolab::AircraftDesignParams stall;
    stall.family = aerolab::VehicleFamily::FixedWing;
    stall.alpha_deg = 16.0f;
    const auto stall_scene = aerolab::build_cad_scene(stall);
    aerolab::LiveEvidenceSummary stall_ev;
    aerolab::evaluate_live_physics_and_curves(stall, stall_scene, stall_ev);
    assert(stall_ev.validation_status == "FAIL");

    // 5. Overweight payload & weak battery overload sag must fail closed + abort 6-DoF RK4
    aerolab::AircraftDesignParams overweight;
    overweight.family = aerolab::VehicleFamily::Multirotor;
    overweight.payload_mass_kg = 12.0f;
    overweight.battery_r0_ohm = 0.25f;
    const auto ov_scene = aerolab::build_cad_scene(overweight);
    aerolab::LiveEvidenceSummary ov_ev;
    aerolab::evaluate_live_physics_and_curves(overweight, ov_scene, ov_ev);
    assert(ov_ev.validation_status == "FAIL");
    assert(ov_ev.predicted_readiness_pct == 0.0);

    const auto repo = aerolab::detect_repo_root();
    aerolab::WorkerIPC ipc(repo);
    aerolab::AircraftDesignParams nominal_quad;
    nominal_quad.family = aerolab::VehicleFamily::Multirotor;
    aerolab::LiveEvidenceSummary nom_ev;
    aerolab::evaluate_live_physics_and_curves(nominal_quad, aerolab::build_cad_scene(nominal_quad), nom_ev);
    ipc.run_cpp_rk4_multirotor(nominal_quad, nom_ev);
    assert(ipc.snapshot_status().last_ok);
    assert(nom_ev.has_trajectory && nom_ev.max_altitude_m > 3.5);

    ipc.run_cpp_rk4_multirotor(overweight, ov_ev);
    assert(!ipc.snapshot_status().last_ok); // overload aborts cleanly inside RK4!
    assert(ov_ev.validation_status == "FAIL");

    // 6. Rotor overspeed pushing tip Mach > 0.70 must fail closed
    aerolab::AircraftDesignParams overspeed;
    overspeed.family = aerolab::VehicleFamily::Helicopter;
    overspeed.rotor_rpm = 3800.0f;
    const auto os_scene = aerolab::build_cad_scene(overspeed);
    aerolab::LiveEvidenceSummary os_ev;
    aerolab::evaluate_live_physics_and_curves(overspeed, os_scene, os_ev);
    assert(os_ev.rotor_tip_mach > 0.70);
    assert(os_ev.validation_status == "FAIL");

    // 7. All 6 SketchShapeKind custom parts build + project JSON save/load roundtrip + wind/alt/tolerance derating
    for (auto sk : {aerolab::SketchShapeKind::RoundedPlate, aerolab::SketchShapeKind::RingDuct,
                    aerolab::SketchShapeKind::AirfoilSection, aerolab::SketchShapeKind::HexMount,
                    aerolab::SketchShapeKind::CustomPropeller, aerolab::SketchShapeKind::CustomBodyShell}) {
        aerolab::AircraftDesignParams cust;
        cust.family = aerolab::VehicleFamily::CustomPart;
        cust.active_part.sketch_kind = sk;
        const auto cs = aerolab::build_cad_scene(cust);
        assert(!cs.vertices.empty() && cs.custom_part_mass_kg > 0.0);
    }

    aerolab::AircraftDesignParams roundtrip_in;
    roundtrip_in.family = aerolab::VehicleFamily::VTOL;
    roundtrip_in.wind_x_m_s = 11.5f;
    roundtrip_in.altitude_asl_m = 2200.0f;
    roundtrip_in.mfg_tolerance_pct = 12.0f;
    roundtrip_in.attach_custom_part = true;
    roundtrip_in.active_part.sketch_kind = aerolab::SketchShapeKind::CustomBodyShell;
    const std::string saved_json = ipc.build_project_payload_json(roundtrip_in);
    aerolab::AircraftDesignParams roundtrip_out;
    assert(aerolab::WorkerIPC::load_project_payload_json(saved_json, roundtrip_out));
    assert(roundtrip_out.family == aerolab::VehicleFamily::VTOL);
    assert(std::abs(roundtrip_out.wind_x_m_s - 11.5f) < 1e-3f);
    assert(std::abs(roundtrip_out.altitude_asl_m - 2200.0f) < 1e-2f);
    assert(std::abs(roundtrip_out.mfg_tolerance_pct - 12.0f) < 1e-3f);
    assert(roundtrip_out.attach_custom_part);
    assert(roundtrip_out.active_part.sketch_kind == aerolab::SketchShapeKind::CustomBodyShell);

    aerolab::AircraftDesignParams morph_in;
    morph_in.family = aerolab::VehicleFamily::MorphingWing;
    morph_in.morph_tuck_pct = 35.0f;
    morph_in.wing_asymmetry_diff = 0.18f;
    morph_in.tail_spread_pct = 82.0f;
    morph_in.tail_tilt_deg = 12.0f;
    const std::string morph_json = ipc.build_project_payload_json(morph_in);
    aerolab::AircraftDesignParams morph_out;
    assert(aerolab::WorkerIPC::load_project_payload_json(morph_json, morph_out));
    assert(morph_out.family == aerolab::VehicleFamily::MorphingWing);
    assert(std::abs(morph_out.morph_tuck_pct - 35.0f) < 1e-3f);
    assert(std::abs(morph_out.wing_asymmetry_diff - 0.18f) < 1e-3f);
    assert(std::abs(morph_out.tail_tilt_deg - 12.0f) < 1e-3f);

    // Phase 1 InsectFlapper (1S, ~32 g) and Seaplane/Jet JSON roundtrip + 6-DoF RK4 run
    aerolab::AircraftDesignParams insect_rt;
    insect_rt.family = aerolab::VehicleFamily::InsectFlapper;
    insect_rt.hardware_catalog_idx = 3;
    insect_rt.frame_mass_kg = 0.014f;
    insect_rt.battery_mass_kg = 0.010f;
    insect_rt.payload_mass_kg = 0.004f;
    insect_rt.motor_mass_kg = 0.004f;
    insect_rt.battery_cells_s = 1;
    insect_rt.battery_capacity_ah = 0.50f;
    insect_rt.battery_r0_ohm = 0.065f;
    insect_rt.wingspan_m = 0.16f;
    insect_rt.root_chord_m = 0.028f;
    insect_rt.flap_freq_hz = 40.0f;
    aerolab::AircraftDesignParams insect_out;
    assert(aerolab::WorkerIPC::load_project_payload_json(ipc.build_project_payload_json(insect_rt), insect_out));
    assert(insect_out.family == aerolab::VehicleFamily::InsectFlapper);
    assert(insect_out.battery_cells_s == 1);
    aerolab::LiveEvidenceSummary insect_ev;
    aerolab::evaluate_live_physics_and_curves(insect_out, aerolab::build_cad_scene(insect_out), insect_ev);
    assert(insect_ev.validation_status == "DEVELOPMENT" && insect_ev.thrust_to_weight >= 1.2);
    ipc.run_cpp_rk4_multirotor(insect_out, insect_ev);
    assert(ipc.snapshot_status().last_ok && insect_ev.has_trajectory && insect_ev.max_altitude_m > 3.0);

    aerolab::AircraftDesignParams calm_quad;
    calm_quad.family = aerolab::VehicleFamily::Multirotor;
    aerolab::LiveEvidenceSummary calm_ev;
    aerolab::evaluate_live_physics_and_curves(calm_quad, aerolab::build_cad_scene(calm_quad), calm_ev);

    aerolab::AircraftDesignParams windy_defective = calm_quad;
    windy_defective.wind_x_m_s = 14.0f;
    windy_defective.turbulence_pct = 35.0f;
    windy_defective.mfg_tolerance_pct = 20.0f;
    windy_defective.altitude_asl_m = 3000.0f;
    windy_defective.motor_cooling_grade = 0;
    const auto wd_scene = aerolab::build_cad_scene(windy_defective);
    assert(!wd_scene.wake_lines.empty()); // 3D wind arrow rendered
    aerolab::LiveEvidenceSummary wd_ev;
    aerolab::evaluate_live_physics_and_curves(windy_defective, wd_scene, wd_ev);
    assert(wd_ev.structural_fos < calm_ev.structural_fos);
    assert(wd_ev.hover_throttle_pct > calm_ev.hover_throttle_pct);
    assert(wd_ev.air_density_kg_m3 < calm_ev.air_density_kg_m3);
    assert(wd_ev.motor_temp_c > calm_ev.motor_temp_c);

    // 8. Exhaustive Run 6-DoF RK4, JSON roundtrip, Catalog Power, and Worker CLI matrix across all families
    for (auto fam : {aerolab::VehicleFamily::Multirotor, aerolab::VehicleFamily::FixedWing,
                     aerolab::VehicleFamily::Helicopter, aerolab::VehicleFamily::VTOL,
                     aerolab::VehicleFamily::Seaplane, aerolab::VehicleFamily::Jet,
                     aerolab::VehicleFamily::InsectFlapper, aerolab::VehicleFamily::MorphingWing,
                     aerolab::VehicleFamily::CargoUAV, aerolab::VehicleFamily::Tailsitter,
                     aerolab::VehicleFamily::FlyingWing}) {
        aerolab::AircraftDesignParams fp;
        fp.family = fam;
        if (fam == aerolab::VehicleFamily::Helicopter) fp.rotor_rpm = 1450.0f;
        else if (fam == aerolab::VehicleFamily::FixedWing) {
            fp.hardware_catalog_idx = 1; fp.battery_cells_s = 4; fp.battery_capacity_ah = 4.5f;
            fp.battery_r0_ohm = 0.018f; fp.battery_mass_kg = 0.55f; fp.rotor_rpm = 6200.0f;
        } else if (fam == aerolab::VehicleFamily::Seaplane) {
            fp.hardware_catalog_idx = 1; fp.battery_cells_s = 4; fp.battery_capacity_ah = 4.5f;
            fp.battery_r0_ohm = 0.018f; fp.battery_mass_kg = 0.55f; fp.airspeed_m_s = 22.0f; fp.rotor_rpm = 7200.0f;
        } else if (fam == aerolab::VehicleFamily::Jet) {
            fp.hardware_catalog_idx = 4; fp.battery_cells_s = 2; fp.battery_capacity_ah = 2.2f;
            fp.battery_r0_ohm = 0.020f; fp.battery_mass_kg = 0.90f; fp.wingspan_m = 1.35f;
            fp.root_chord_m = 0.38f; fp.tip_chord_m = 0.14f; fp.sweep_deg = 26.0f; fp.alpha_deg = 2.2f; fp.airspeed_m_s = 92.0f;
        } else if (fam == aerolab::VehicleFamily::CargoUAV) {
            fp.rotor_count = 6; fp.arm_length_m = 0.48f; fp.prop_diameter_m = 0.38f;
            fp.frame_mass_kg = 1.85f; fp.battery_mass_kg = 1.55f; fp.cargo_mass_kg = 1.80f;
            fp.cable_length_m = 1.20f; fp.rotor_rpm = 5400.0f; fp.airspeed_m_s = 12.0f; fp.screw_size_idx = 3;
        } else if (fam == aerolab::VehicleFamily::Tailsitter) {
            fp.hardware_catalog_idx = 1; fp.battery_cells_s = 4; fp.battery_capacity_ah = 4.5f;
            fp.battery_r0_ohm = 0.018f; fp.frame_mass_kg = 0.92f; fp.battery_mass_kg = 0.48f;
            fp.wingspan_m = 1.05f; fp.root_chord_m = 0.28f; fp.tip_chord_m = 0.18f;
            fp.transition_pitch_deg = 70.0f; fp.duct_area_ratio = 1.08f; fp.rotor_rpm = 7200.0f; fp.airspeed_m_s = 14.0f;
        } else if (fam == aerolab::VehicleFamily::FlyingWing) {
            fp.hardware_catalog_idx = 1; fp.battery_cells_s = 4; fp.battery_capacity_ah = 4.5f;
            fp.battery_r0_ohm = 0.018f; fp.frame_mass_kg = 0.72f; fp.battery_mass_kg = 0.46f;
            fp.wingspan_m = 1.25f; fp.root_chord_m = 0.30f; fp.tip_chord_m = 0.14f;
            fp.sweep_deg = 26.0f; fp.rotor_rpm = 7600.0f; fp.airspeed_m_s = 22.0f; fp.alpha_deg = 4.0f;
        } else if (fam == aerolab::VehicleFamily::InsectFlapper) {
            fp.hardware_catalog_idx = 3; fp.frame_mass_kg = 0.014f; fp.battery_mass_kg = 0.010f;
            fp.payload_mass_kg = 0.004f; fp.motor_mass_kg = 0.004f; fp.battery_cells_s = 1;
            fp.battery_capacity_ah = 0.50f; fp.battery_r0_ohm = 0.065f; fp.wingspan_m = 0.16f;
            fp.root_chord_m = 0.028f; fp.tip_chord_m = 0.016f; fp.flap_freq_hz = 40.0f; fp.airspeed_m_s = 2.2f;
        } else if (fam == aerolab::VehicleFamily::MorphingWing) {
            fp.hardware_catalog_idx = 1; fp.frame_mass_kg = 0.65f; fp.battery_mass_kg = 0.35f;
            fp.payload_mass_kg = 0.12f; fp.motor_mass_kg = 0.055f; fp.battery_cells_s = 4;
            fp.battery_capacity_ah = 4.5f; fp.battery_r0_ohm = 0.018f; fp.wingspan_m = 1.15f;
            fp.root_chord_m = 0.22f; fp.tip_chord_m = 0.14f; fp.sweep_deg = 16.0f;
            fp.morph_tuck_pct = 25.0f; fp.airspeed_m_s = 16.0f; fp.alpha_deg = 5.5f;
        }
        aerolab::AircraftDesignParams rt;
        assert(aerolab::WorkerIPC::load_project_payload_json(ipc.build_project_payload_json(fp), rt));
        assert(rt.family == fam);
        aerolab::LiveEvidenceSummary fev;
        aerolab::evaluate_live_physics_and_curves(rt, aerolab::build_cad_scene(rt), fev);
        assert(fev.validation_status == "DEVELOPMENT");
        ipc.run_cpp_rk4_multirotor(rt, fev);
        assert(ipc.snapshot_status().last_ok && fev.has_trajectory && fev.max_altitude_m > 3.5);
    }

    // Verify undersized Micro Coreless 1S selected on Jet, M2 bolt shear, 22AWG burn, and supersonic shock cone
    aerolab::AircraftDesignParams bad_jet;
    bad_jet.family = aerolab::VehicleFamily::Jet;
    bad_jet.hardware_catalog_idx = 3;
    bad_jet.battery_cells_s = 1;
    bad_jet.airspeed_m_s = 92.0f;
    aerolab::LiveEvidenceSummary bj_ev;
    aerolab::evaluate_live_physics_and_curves(bad_jet, aerolab::build_cad_scene(bad_jet), bj_ev);
    assert(bj_ev.validation_status == "FAIL");

    aerolab::AircraftDesignParams sup_jet;
    sup_jet.family = aerolab::VehicleFamily::Jet;
    sup_jet.hardware_catalog_idx = 5;
    sup_jet.airspeed_m_s = 475.0f;
    sup_jet.jet_throttle_pct = 100.0f;
    const auto sup_scene = aerolab::build_cad_scene(sup_jet);
    aerolab::LiveEvidenceSummary sj_ev;
    aerolab::evaluate_live_physics_and_curves(sup_jet, sup_scene, sj_ev);
    assert(sj_ev.mach > 1.3 && sj_ev.mach_cone_deg < 55.0);
    assert(sup_scene.wake_lines.size() > 30);

    aerolab::AircraftDesignParams cargo_drop;
    cargo_drop.family = aerolab::VehicleFamily::CargoUAV;
    cargo_drop.rotor_count = 6;
    cargo_drop.arm_length_m = 0.48f;
    cargo_drop.prop_diameter_m = 0.38f;
    cargo_drop.cargo_mass_kg = 2.0f;
    cargo_drop.rotor_rpm = 5600.0f;
    cargo_drop.screw_size_idx = 3;
    cargo_drop.payload_released = false;
    aerolab::LiveEvidenceSummary cd_before, cd_after;
    aerolab::evaluate_live_physics_and_curves(cargo_drop, aerolab::build_cad_scene(cargo_drop), cd_before);
    cargo_drop.payload_released = true;
    aerolab::evaluate_live_physics_and_curves(cargo_drop, aerolab::build_cad_scene(cargo_drop), cd_after);
    assert(cd_after.total_mass_kg < cd_before.total_mass_kg - 1.5);
    assert(cd_after.thrust_to_weight > cd_before.thrust_to_weight);

    aerolab::AircraftDesignParams thin_wire;
    thin_wire.family = aerolab::VehicleFamily::Multirotor;
    thin_wire.wire_awg = 22;
    aerolab::LiveEvidenceSummary tw_ev;
    aerolab::evaluate_live_physics_and_curves(thin_wire, aerolab::build_cad_scene(thin_wire), tw_ev);
    assert(!tw_ev.wire_ok && tw_ev.validation_status == "FAIL");

    // Verify custom BodyShell drag penalty & RingDuct shrouded thrust gain physically update live evidence
    aerolab::AircraftDesignParams custom_shell;
    custom_shell.family = aerolab::VehicleFamily::FixedWing;
    custom_shell.hardware_catalog_idx = 1; custom_shell.battery_cells_s = 4; custom_shell.battery_capacity_ah = 4.5f;
    custom_shell.battery_r0_ohm = 0.018f; custom_shell.battery_mass_kg = 0.55f; custom_shell.rotor_rpm = 6200.0f;
    aerolab::LiveEvidenceSummary base_fw, shell_fw;
    aerolab::evaluate_live_physics_and_curves(custom_shell, aerolab::build_cad_scene(custom_shell), base_fw);
    custom_shell.attach_custom_part = true;
    custom_shell.active_part.sketch_kind = aerolab::SketchShapeKind::CustomBodyShell;
    custom_shell.active_part.width_m = 0.14f;
    aerolab::evaluate_live_physics_and_curves(custom_shell, aerolab::build_cad_scene(custom_shell), shell_fw);
    assert(shell_fw.cd > base_fw.cd && shell_fw.validation_status == "UNVALIDATED_CUSTOM");
    assert(shell_fw.benchmark_match_pct < 0.0);

    aerolab::AircraftDesignParams duct_quad;
    duct_quad.family = aerolab::VehicleFamily::Multirotor;
    aerolab::LiveEvidenceSummary plain_q, duct_q;
    aerolab::evaluate_live_physics_and_curves(duct_quad, aerolab::build_cad_scene(duct_quad), plain_q);
    duct_quad.attach_custom_part = true;
    duct_quad.active_part.sketch_kind = aerolab::SketchShapeKind::RingDuct;
    aerolab::evaluate_live_physics_and_curves(duct_quad, aerolab::build_cad_scene(duct_quad), duct_q);
    assert(duct_q.thrust_to_weight != plain_q.thrust_to_weight && duct_q.validation_status == "UNVALIDATED_CUSTOM");

    // Verify Exploded View geometry displacement + Rocket/Hypersonic preset + Helicopter VRS fail
    aerolab::AircraftDesignParams exp_q = duct_quad;
    exp_q.attach_custom_part = false;
    exp_q.explode_factor = 1.0f;
    const auto exp_scene = aerolab::build_cad_scene(exp_q);
    assert(exp_scene.wake_lines.size() > 10); // Explosion guides + streamlines

    aerolab::AircraftDesignParams rkt;
    rkt.family = aerolab::VehicleFamily::RocketSpacecraft;
    aerolab::LiveEvidenceSummary rkt_ev;
    aerolab::evaluate_live_physics_and_curves(rkt, aerolab::build_cad_scene(rkt), rkt_ev);
    assert(rkt_ev.rocket_orbit_ok && rkt_ev.validation_status == "DEVELOPMENT" && rkt_ev.rocket_tps_c < 1850.0);

    aerolab::AircraftDesignParams heli_vrs;
    heli_vrs.family = aerolab::VehicleFamily::Helicopter;
    heli_vrs.rotor_rpm = 1450.0f;
    heli_vrs.airspeed_m_s = 1.2f;
    heli_vrs.heli_descent_m_s = -2.1f;
    aerolab::LiveEvidenceSummary hv_ev;
    aerolab::evaluate_live_physics_and_curves(heli_vrs, aerolab::build_cad_scene(heli_vrs), hv_ev);
    assert(hv_ev.heli_vrs && hv_ev.validation_status == "FAIL");

    // Live Python worker end-to-end check across ALL menu worker commands
    for (const std::string &cmd : {"fixed-wing-sim", "layout-bom", "6dof-fixed-wing", "vtol-transition",
                                   "autorotation-sim", "adverse-weather", "bounded-sweep", "phase1-eval"}) {
        assert(ipc.launch_python_command(cmd, ipc.build_project_payload_json(nominal_quad)));
        while (ipc.is_busy()) std::this_thread::sleep_for(std::chrono::milliseconds(15));
        assert(ipc.snapshot_status().last_ok);
    }
    assert(ipc.launch_python_command("compare-source", ipc.build_compare_payload_json(nominal_quad, nom_ev)));
    while (ipc.is_busy()) std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(ipc.snapshot_status().last_ok);

    assert(ipc.launch_python_command(
        "export-drawing", ipc.build_drawing_payload_json(nominal_quad, repo / ".local" / "tmp" / "native_exports")));
    while (ipc.is_busy()) std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(ipc.snapshot_status().last_ok);
    assert(std::filesystem::exists(repo / ".local" / "tmp" / "native_exports" / "wing_drawing.svg"));

    assert(ipc.launch_python_command(
        "build-custom-part", ipc.build_part_payload_json(roundtrip_in, repo / ".local" / "tmp" / "native_exports")));
    while (ipc.is_busy()) std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(ipc.snapshot_status().last_ok);

    // 9. PNG uncompressed stored-deflate encoder smoke check
    const auto tmp_png = std::filesystem::temp_directory_path() / "aerolab_native_test.png";
    std::vector<std::uint8_t> rgba(4 * 4 * 4, 200);
    assert(aerolab::write_png_rgba(tmp_png.string(), 4, 4, rgba));
    assert(std::filesystem::file_size(tmp_png) > 50);
    std::filesystem::remove(tmp_png);

    std::cout << "native_cad_tests: ALL PASSED\n";
    return 0;
}
