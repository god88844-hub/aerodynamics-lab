#include "cad_mesh_builder.hpp"

#include <cassert>
#include <cmath>
#include <filesystem>
#include <iostream>

int main() {
    // 1. NACA 4-digit closed airfoil generator
    const auto airfoil = aerolab::sample_naca4_airfoil("2412", 16);
    assert(airfoil.size() == 31);
    assert(std::abs(airfoil.front().x - 1.0f) < 1e-4f);

    // 2. Build all 5 VehicleFamily CAD scenes and verify non-empty triangles + CAD edges
    for (auto fam : {aerolab::VehicleFamily::Multirotor, aerolab::VehicleFamily::FixedWing,
                     aerolab::VehicleFamily::Helicopter, aerolab::VehicleFamily::VTOL,
                     aerolab::VehicleFamily::CustomPart}) {
        aerolab::AircraftDesignParams p;
        p.family = fam;
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
        }
    }

    // 3. Rotor tip overlap must fail closed
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

    // 4. Out-of-envelope stall alpha must fail closed
    aerolab::AircraftDesignParams stall;
    stall.family = aerolab::VehicleFamily::FixedWing;
    stall.alpha_deg = 16.0f;
    const auto stall_scene = aerolab::build_cad_scene(stall);
    aerolab::LiveEvidenceSummary stall_ev;
    aerolab::evaluate_live_physics_and_curves(stall, stall_scene, stall_ev);
    assert(stall_ev.validation_status == "FAIL");

    // 5. Overweight payload & weak battery overload sag must fail closed
    aerolab::AircraftDesignParams overweight;
    overweight.family = aerolab::VehicleFamily::Multirotor;
    overweight.payload_mass_kg = 12.0f;
    overweight.battery_r0_ohm = 0.25f;
    const auto ov_scene = aerolab::build_cad_scene(overweight);
    aerolab::LiveEvidenceSummary ov_ev;
    aerolab::evaluate_live_physics_and_curves(overweight, ov_scene, ov_ev);
    assert(ov_ev.validation_status == "FAIL");
    assert(ov_ev.predicted_readiness_pct == 0.0);

    // 6. Rotor overspeed pushing tip Mach > 0.70 must fail closed
    aerolab::AircraftDesignParams overspeed;
    overspeed.family = aerolab::VehicleFamily::Helicopter;
    overspeed.rotor_rpm = 3800.0f;
    const auto os_scene = aerolab::build_cad_scene(overspeed);
    aerolab::LiveEvidenceSummary os_ev;
    aerolab::evaluate_live_physics_and_curves(overspeed, os_scene, os_ev);
    assert(os_ev.rotor_tip_mach > 0.70);
    assert(os_ev.validation_status == "FAIL");

    // 5. PNG uncompressed stored-deflate encoder smoke check
    const auto tmp_png = std::filesystem::temp_directory_path() / "aerolab_native_test.png";
    std::vector<std::uint8_t> rgba(4 * 4 * 4, 200);
    assert(aerolab::write_png_rgba(tmp_png.string(), 4, 4, rgba));
    assert(std::filesystem::file_size(tmp_png) > 50);
    std::filesystem::remove(tmp_png);

    std::cout << "native_cad_tests: ALL PASSED\n";
    return 0;
}
