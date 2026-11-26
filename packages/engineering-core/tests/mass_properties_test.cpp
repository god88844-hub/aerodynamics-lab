#include "lab/mass_properties.hpp"
#include "lab/flight_rk4.hpp"

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
    return 0;
}
