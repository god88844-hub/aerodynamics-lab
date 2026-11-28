#pragma once

#include <array>
#include <string>
#include <vector>

namespace lab {

struct MultirotorSimConfig {
    double mass_kg = 1.5;
    std::array<double, 3> inertia_diag_kg_m2 = {0.03, 0.03, 0.05};
    int n_rotors = 4;
    double max_total_thrust_n = 56.0;
    double cd_a_m2 = 0.05;
    double air_density_kg_m3 = 1.225;
    std::array<double, 3> wind_world_m_s = {0.0, 0.0, 0.0};
    double initial_altitude_m = 2.0;
    double target_altitude_m = 2.0;
    double dt_s = 0.004;
    double duration_s = 0.4;
    double min_bus_voltage_v = 19.2;
    double nominal_bus_voltage_v = 25.2;
    double pack_r0_ohm = 0.05;
    double current_per_n_a = 1.4;
};

struct MultirotorSimStepResult {
    bool ok = false;
    bool aborted = false;
    std::string error_or_reason;
    int step_count = 0;
    double final_time_s = 0.0;
    double max_altitude_m = 0.0;
    double min_bus_voltage_v = 25.2;
    std::array<double, 3> final_position_m = {0.0, 0.0, 0.0};
    std::array<double, 4> final_quaternion_wxyz = {1.0, 0.0, 0.0, 0.0};
    std::vector<double> times_s;
    std::vector<std::array<double, 3>> positions_m;
    std::vector<std::array<double, 4>> quaternions_wxyz;
};

MultirotorSimStepResult run_multirotor_rk4(const MultirotorSimConfig &cfg);

} // namespace lab
