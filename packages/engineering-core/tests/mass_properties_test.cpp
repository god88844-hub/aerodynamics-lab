#include "lab/mass_properties.hpp"
#include "lab/flight_rk4.hpp"
#include "lab/bioinspired.hpp"
#include "lab/whole_aircraft.hpp"
#include "lab/multiphysics_and_rockets.hpp"

#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

int main() {
    const std::array<lab::MassPoint, 2> parts = {{{2.0, {1e9, 0.0, -1.0}},
                                               {1.0, {1e9 + 3.0, 0.0, 2.0}}}};
    const auto result = lab::combine_mass_points(parts);
    if (result.mass_kg != 3.0 || std::abs(result.center_of_mass_m[0] - (1e9 + 1.0)) > 1e-7
        || std::abs(result.center_of_mass_m[2]) > 1e-14) {
        std::cerr << "Mass combination disagrees with the analytical result\n";
        return 1;
    }
    for (const double mass : {0.0, -1.0, std::numeric_limits<double>::infinity()}) {
        const std::array<lab::MassPoint, 1> invalid = {{{mass, {0.0, 0.0, 0.0}}}};
        try {
            lab::combine_mass_points(invalid);
            return 2;
        } catch (const std::invalid_argument &) {
        }
    }
    try {
        lab::combine_mass_points({});
        return 3;
    } catch (const std::invalid_argument &) {
    }

    // P0A-020: datum transform and rotor clearance checks
    const double s = std::sqrt(0.5);
    const lab::Vector3 rotated = lab::transform_point_wxyz({1.0, 2.0, 3.0}, {s, 0.0, 0.0, s}, {0.5, 0.0, 0.0});
    if (std::abs(rotated[0] - 1.0) > 1e-12 || std::abs(rotated[1] - 2.5) > 1e-12 || std::abs(rotated[2] - 3.0) > 1e-12) {
        std::cerr << "Datum transform disagrees with 90 deg yaw analytic point\n";
        return 4;
    }
    const std::array<lab::RotorDisk, 2> clear_rotors = {{{{0.0, 0.0, 0.0}, 0.15}, {{0.35, 0.0, 0.0}, 0.15}}};
    const auto clear_res = lab::evaluate_rotor_pair_clearance(clear_rotors, 0.02);
    if (!clear_res.clear || std::abs(clear_res.minimum_tip_clearance_m - 0.05) > 1e-12) {
        std::cerr << "Clearance check disagrees with expected 0.05 m tip gap\n";
        return 5;
    }
    const std::array<lab::RotorDisk, 2> overlap_rotors = {{{{0.0, 0.0, 0.0}, 0.20}, {{0.30, 0.0, 0.0}, 0.20}}};
    const auto overlap_res = lab::evaluate_rotor_pair_clearance(overlap_rotors, 0.02);
    if (overlap_res.clear || std::abs(overlap_res.minimum_tip_clearance_m + 0.10) > 1e-12) {
        std::cerr << "Overlap clearance check disagrees with expected -0.10 m overlap\n";
        return 6;
    }

    std::cout << "Engineering mass-property and clearance checks passed\n";

    // Tier-0 / Mobile C++20 6-DoF RK4 verification: stationary hover, wind drag shift, propulsion abort
    lab::MultirotorSimConfig hover_cfg;
    hover_cfg.mass_kg = 2.0;
    hover_cfg.max_total_thrust_n = 72.0;
    hover_cfg.initial_altitude_m = 2.0;
    hover_cfg.target_altitude_m = 2.0;
    hover_cfg.duration_s = 0.2;
    const auto hover_res = lab::run_multirotor_rk4(hover_cfg);
    if (!hover_res.ok || hover_res.aborted || std::abs(hover_res.final_position_m[2] - 2.0) > 1e-9) {
        std::cerr << "C++20 RK4 stationary hover drifted beyond 1e-9 m\n";
        return 7;
    }
    lab::MultirotorSimConfig wind_cfg = hover_cfg;
    wind_cfg.wind_world_m_s = {5.0, 0.0, 0.0};
    const auto wind_res = lab::run_multirotor_rk4(wind_cfg);
    if (wind_res.final_position_m[0] <= 0.0) {
        std::cerr << "C++20 RK4 wind drag did not shift X position\n";
        return 8;
    }
    lab::MultirotorSimConfig over_cfg = hover_cfg;
    over_cfg.target_altitude_m = 50.0;
    const auto over_res = lab::run_multirotor_rk4(over_cfg);
    if (!over_res.aborted) {
        std::cerr << "C++20 RK4 over-thrust demand failed to abort cleanly\n";
        return 9;
    }
    std::cout << "C++20 6-DoF RK4 multirotor kernel checks passed\n";

    // Phase 1 C++20 bio-inspired strip BEMT convergence, morphing, flex aeroelastic, Savitsky, and 1S RK4 checks
    lab::FlappingParams fp16;
    fp16.n_strips = 16;
    const auto fres16 = lab::evaluate_flapping_strip_bemt(fp16);
    lab::FlappingParams fp64 = fp16;
    fp64.n_strips = 64;
    const auto fres64 = lab::evaluate_flapping_strip_bemt(fp64);
    if (!fres16.valid || !fres64.valid || fres16.hover_tw < 1.05 ||
        std::abs(fres16.mean_lift_n - fres64.mean_lift_n) / std::max(1e-6, fres64.mean_lift_n) > 0.02) {
        std::cerr << "Flapping strip BEMT hover or strip convergence check failed\n";
        return 10;
    }
    const auto mp = lab::evaluate_morphing_stability({});
    if (!mp.valid || mp.effective_span_m >= 1.15 || mp.yaw_damping_coeff <= 0.04) {
        std::cerr << "Morphing stability evaluation failed\n";
        return 11;
    }
    lab::FlexBeamParams flex_ok;
    const auto f_ok = lab::evaluate_compliant_flex_aeroelastic(flex_ok);
    lab::FlexBeamParams flex_fail = flex_ok;
    flex_fail.applied_cycles = 500000;
    const auto f_fail = lab::evaluate_compliant_flex_aeroelastic(flex_fail);
    if (!f_ok.structural_ok || f_fail.structural_ok) {
        std::cerr << "Compliant flex beam fatigue gate failed\n";
        return 12;
    }
    const auto sea = lab::evaluate_savitsky_seaplane({});
    if (!sea.valid || !sea.planing_or_buoyant_ok || sea.hydro_lift_n <= 0.0) {
        std::cerr << "Savitsky seaplane check failed\n";
        return 13;
    }
    lab::MultirotorSimConfig mav_1s;
    mav_1s.mass_kg = 0.032;
    mav_1s.n_rotors = 2;
    mav_1s.max_total_thrust_n = 0.50;
    mav_1s.nominal_bus_voltage_v = 3.85;
    mav_1s.min_bus_voltage_v = 3.20;
    mav_1s.pack_r0_ohm = 0.065;
    mav_1s.current_per_n_a = 8.0;
    mav_1s.duration_s = 0.4;
    const auto mav_res = lab::run_multirotor_rk4(mav_1s);
    if (!mav_res.ok || mav_res.aborted) {
        std::cerr << "1S micro-flapper 6-DoF RK4 trajectory aborted unexpectedly\n";
        return 14;
    }
    std::cout << "Phase 1 C++20 flapping, morphing, flex aeroelastic, Savitsky, and 1S RK4 checks passed\n";

    // Phase 3 & Creator Whole-Aircraft C++20 checks: coupled jet cycle, cargo slung load, tailsitter, flying wing, fasteners/AWG
    lab::CoupledJetParams jet_p;
    jet_p.mach = 1.25;
    const auto jet_r = lab::evaluate_coupled_jet_cycle(jet_p);
    if (!jet_r.valid || jet_r.inlet_recovery_eta >= 1.0 || jet_r.mach_cone_half_angle_deg >= 60.0) {
        std::cerr << "Coupled supersonic jet cycle failed MIL-E-5008B or Mach cone check\n";
        return 15;
    }
    const auto cargo_ok = lab::evaluate_cargo_slung_load({});
    lab::CargoSlungLoadParams cargo_heavy;
    cargo_heavy.cargo_mass_kg = 8.0;
    const auto cargo_fail = lab::evaluate_cargo_slung_load(cargo_heavy);
    if (!cargo_ok.valid || !cargo_ok.stable_ok || cargo_fail.stable_ok) {
        std::cerr << "Cargo slung-load pendulum check failed\n";
        return 16;
    }
    const auto ts_ok = lab::evaluate_creator_archetypes({});
    lab::CreatorArchetypeParams fw_unstable;
    fw_unstable.mode = 1;
    fw_unstable.sweep_deg = 2.0;
    const auto fw_fail = lab::evaluate_creator_archetypes(fw_unstable);
    if (!ts_ok.authority_ok || fw_fail.authority_ok) {
        std::cerr << "Creator tailsitter/flying-wing check failed\n";
        return 17;
    }
    const auto fh_ok = lab::evaluate_fastener_and_harness_safety({});
    lab::FastenerHarnessParams fh_thin_wire;
    fh_thin_wire.wire_awg = 22;
    fh_thin_wire.continuous_current_a = 40.0;
    const auto fh_bad = lab::evaluate_fastener_and_harness_safety(fh_thin_wire);
    if (!fh_ok.bolt_ok || !fh_ok.wire_ok || fh_bad.wire_ok) {
        std::cerr << "ISO fastener or AWG harness safety check failed\n";
        return 18;
    }
    std::cout << "Phase 3 & Creator whole-aircraft C++20 kernel checks passed\n";

    // Multiphysics gaps + Phase 4 Rockets & Hypersonics C++20 kernel checks
    lab::AeroacousticsParams ac_jet;
    ac_jet.is_jet = true;
    ac_jet.jet_mach = 1.38;
    const auto ac_r = lab::evaluate_aeroacoustics(ac_jet);
    if (!ac_r.valid || ac_r.sonic_boom_pa <= 0.0 || ac_r.total_spl_dba < 70.0) {
        std::cerr << "Aeroacoustics / sonic boom check failed\n";
        return 19;
    }

    lab::HelicopterHighSpeedParams h_vrs;
    h_vrs.horizontal_speed_m_s = 1.2;
    h_vrs.vertical_speed_m_s = -2.1; // v_z / v_h ~ -0.77 inside VRS band [-1.25, -0.35]
    const auto h_vrs_r = lab::evaluate_helicopter_highspeed(h_vrs);
    if (!h_vrs_r.valid || !h_vrs_r.vrs_entered || h_vrs_r.gyro_precession_torque_nm <= 0.0) {
        std::cerr << "Helicopter VRS / gyroscopic precession check failed\n";
        return 20;
    }

    lab::HydroCavitationParams cav_fast;
    cav_fast.prop_rpm = 16000.0;
    const auto cav_r = lab::evaluate_hydro_cavitation(cav_fast);
    if (!cav_r.valid || !cav_r.cavitating) {
        std::cerr << "Hydro cavitation check failed\n";
        return 21;
    }

    lab::RfStealthParams rf_plain, rf_stealth;
    rf_stealth.stealth_shaping = true;
    rf_stealth.sweep_deg = 42.0;
    const auto rf_p = lab::evaluate_rf_and_rcs(rf_plain);
    const auto rf_s = lab::evaluate_rf_and_rcs(rf_stealth);
    if (!rf_p.valid || !rf_p.link_ok || rf_s.rcs_dbsm >= rf_p.rcs_dbsm) {
        std::cerr << "RF telemetry & RCS stealth check failed\n";
        return 22;
    }

    const auto rocket_ok = lab::evaluate_rocket_and_hypersonics({});
    if (!rocket_ok.valid || !rocket_ok.orbit_capable || !rocket_ok.flight_ok ||
        rocket_ok.reentry_heat_flux_w_m2 <= 1e5 || rocket_ok.knudsen_number <= 0.0) {
        std::cerr << "Phase 4 rocket / Sutton-Graves hypersonics check failed\n";
        return 23;
    }
    std::cout << "Multiphysics (Aeroacoustics/VRS/Cavitation/RF-RCS) & Phase 4 Rocket C++20 checks passed\n";
    return 0;
}
