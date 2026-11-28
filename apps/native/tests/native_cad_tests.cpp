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

    // 2. Build all 5 VehicleFamily CAD scenes and verify non-empty triangles + CAD edges + realistic T/W
    for (auto fam : {aerolab::VehicleFamily::Multirotor, aerolab::VehicleFamily::FixedWing,
                     aerolab::VehicleFamily::Helicopter, aerolab::VehicleFamily::VTOL,
                     aerolab::VehicleFamily::CustomPart}) {
        aerolab::AircraftDesignParams p;
        p.family = fam;
        if (fam == aerolab::VehicleFamily::Helicopter) p.rotor_rpm = 1450.0f;
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
            assert(ev.predicted_readiness_pct > 65.0);
            assert(ev.thrust_to_weight > 1.2 && ev.thrust_to_weight < 5.0);
        }
    }

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

    // 8. Live Python worker end-to-end check (compare-source, export-drawing, layout-bom, build-custom-part)
    assert(ipc.launch_python_command("compare-source", ipc.build_compare_payload_json(nominal_quad, nom_ev)));
    while (ipc.is_busy()) std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(ipc.snapshot_status().last_ok);

    assert(ipc.launch_python_command(
        "export-drawing", ipc.build_drawing_payload_json(nominal_quad, repo / ".local" / "tmp" / "native_exports")));
    while (ipc.is_busy()) std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(ipc.snapshot_status().last_ok);
    assert(std::filesystem::exists(repo / ".local" / "tmp" / "native_exports" / "wing_drawing.svg"));

    assert(ipc.launch_python_command("layout-bom", ipc.build_project_payload_json(nominal_quad)));
    while (ipc.is_busy()) std::this_thread::sleep_for(std::chrono::milliseconds(20));
    assert(ipc.snapshot_status().last_ok);

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
