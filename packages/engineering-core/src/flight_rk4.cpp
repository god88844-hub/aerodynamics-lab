#include "lab/flight_rk4.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

namespace lab {
namespace {

constexpr double kGravity = 9.80665;
using State = std::array<double, 13>; // r_w(3), v_w(3), q_bw(4 wxyz), omega_b(3)

std::array<double, 3> rotate_vector(const std::array<double, 4> &q, const std::array<double, 3> &v) {
    const double w = q[0], x = q[1], y = q[2], z = q[3];
    const double tx = 2.0 * (y * v[2] - z * v[1]);
    const double ty = 2.0 * (z * v[0] - x * v[2]);
    const double tz = 2.0 * (x * v[1] - y * v[0]);
    return {
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    };
}

std::array<double, 4> normalize_quat(const std::array<double, 4> &q) {
    const double n = std::sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
    if (!std::isfinite(n) || n <= 1e-12) {
        return {1.0, 0.0, 0.0, 0.0};
    }
    return {q[0] / n, q[1] / n, q[2] / n, q[3] / n};
}

State compute_derivs(const State &s, const MultirotorSimConfig &cfg, double total_thrust_n) {
    const std::array<double, 3> vel = {s[3], s[4], s[5]};
    const std::array<double, 4> q = normalize_quat({s[6], s[7], s[8], s[9]});
    const std::array<double, 3> omega = {s[10], s[11], s[12]};

    const std::array<double, 3> thrust_world = rotate_vector(q, {0.0, 0.0, total_thrust_n});
    const double rx = vel[0] - cfg.wind_world_m_s[0];
    const double ry = vel[1] - cfg.wind_world_m_s[1];
    const double rz = vel[2] - cfg.wind_world_m_s[2];
    const double speed = std::sqrt(rx * rx + ry * ry + rz * rz);
    const double drag_factor = -0.5 * cfg.air_density_kg_m3 * cfg.cd_a_m2 * speed;

    const double ax = (thrust_world[0] + drag_factor * rx) / cfg.mass_kg;
    const double ay = (thrust_world[1] + drag_factor * ry) / cfg.mass_kg;
    const double az = (thrust_world[2] + drag_factor * rz) / cfg.mass_kg - kGravity;

    const double qw = q[0], qx = q[1], qy = q[2], qz = q[3];
    const double ox = omega[0], oy = omega[1], oz = omega[2];
    const double dqw = 0.5 * (-qx * ox - qy * oy - qz * oz);
    const double dqx = 0.5 * (qw * ox + qy * oz - qz * oy);
    const double dqy = 0.5 * (qw * oy - qx * oz + qz * ox);
    const double dqz = 0.5 * (qw * oz + qx * oy - qy * ox);

    // Rigid body Euler rotational dynamics (tau = 0 symmetric attitude hold)
    const double Ix = cfg.inertia_diag_kg_m2[0];
    const double Iy = cfg.inertia_diag_kg_m2[1];
    const double Iz = cfg.inertia_diag_kg_m2[2];
    const double dox = -(Iz - Iy) * oy * oz / Ix;
    const double doy = -(Ix - Iz) * oz * ox / Iy;
    const double doz = -(Iy - Ix) * ox * oy / Iz;

    return {vel[0], vel[1], vel[2], ax, ay, az, dqw, dqx, dqy, dqz, dox, doy, doz};
}

State rk4_step(const State &x, const MultirotorSimConfig &cfg, double total_thrust_n, double dt) {
    const State k1 = compute_derivs(x, cfg, total_thrust_n);
    State x2{};
    for (std::size_t i = 0; i < 13; ++i) x2[i] = x[i] + 0.5 * dt * k1[i];
    const State k2 = compute_derivs(x2, cfg, total_thrust_n);
    State x3{};
    for (std::size_t i = 0; i < 13; ++i) x3[i] = x[i] + 0.5 * dt * k2[i];
    const State k3 = compute_derivs(x3, cfg, total_thrust_n);
    State x4{};
    for (std::size_t i = 0; i < 13; ++i) x4[i] = x[i] + dt * k3[i];
    const State k4 = compute_derivs(x4, cfg, total_thrust_n);

    State out{};
    for (std::size_t i = 0; i < 13; ++i) {
        out[i] = x[i] + (dt / 6.0) * (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]);
    }
    const auto q = normalize_quat({out[6], out[7], out[8], out[9]});
    out[6] = q[0];
    out[7] = q[1];
    out[8] = q[2];
    out[9] = q[3];
    return out;
}

} // namespace

MultirotorSimStepResult run_multirotor_rk4(const MultirotorSimConfig &cfg) {
    if (!std::isfinite(cfg.mass_kg) || cfg.mass_kg <= 0.0 || cfg.n_rotors < 2
        || !std::isfinite(cfg.max_total_thrust_n) || cfg.max_total_thrust_n <= 0.0
        || !std::isfinite(cfg.dt_s) || cfg.dt_s <= 0.0 || !std::isfinite(cfg.duration_s) || cfg.duration_s <= 0.0
        || !std::isfinite(cfg.air_density_kg_m3) || cfg.air_density_kg_m3 <= 0.0) {
        throw std::invalid_argument("Invalid physical parameters for C++20 RK4 multirotor simulation");
    }
    for (double i_axis : cfg.inertia_diag_kg_m2) {
        if (!std::isfinite(i_axis) || i_axis <= 0.0) {
            throw std::invalid_argument("Inertia diagonal terms must be finite and positive");
        }
    }

    const int steps = std::max(1, static_cast<int>(std::ceil(cfg.duration_s / cfg.dt_s - 1e-12)));
    if (steps > 50000) {
        throw std::invalid_argument("Requested RK4 steps exceed 50000 step mobile/desktop safety cap");
    }

    MultirotorSimStepResult res;
    res.ok = true;
    State s = {0.0, 0.0, cfg.initial_altitude_m, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
    res.times_s.push_back(0.0);
    res.positions_m.push_back({s[0], s[1], s[2]});
    res.quaternions_wxyz.push_back({s[6], s[7], s[8], s[9]});
    res.max_altitude_m = s[2];
    res.min_bus_voltage_v = cfg.nominal_bus_voltage_v;

    const double rho_scale = cfg.air_density_kg_m3 / 1.225;
    const double max_thrust_scaled = cfg.max_total_thrust_n * rho_scale;
    const double kp_z = 0.85 * cfg.mass_kg;
    const double kd_z = 1.80 * cfg.mass_kg;
    double t = 0.0;

    for (int idx = 0; idx < steps; ++idx) {
        const double h = std::min(cfg.dt_s, cfg.duration_s - t);
        const double total_thrust_cmd = std::max(
            0.0, cfg.mass_kg * kGravity + kp_z * (cfg.target_altitude_m - s[2]) - kd_z * s[5]);
        if (total_thrust_cmd > max_thrust_scaled) {
            res.aborted = true;
            res.error_or_reason = "Propulsion thrust demand exceeds density-scaled max thrust";
            break;
        }
        const double est_current_a = total_thrust_cmd * std::max(0.1, cfg.current_per_n_a);
        const double sag_rate = 0.0006 * cfg.nominal_bus_voltage_v;
        const double v_bus = std::max(0.0, cfg.nominal_bus_voltage_v - cfg.pack_r0_ohm * est_current_a - sag_rate * idx * h);
        if (v_bus < cfg.min_bus_voltage_v) {
            res.aborted = true;
            res.error_or_reason = "Battery bus voltage dropped below cutoff threshold";
            break;
        }
        res.min_bus_voltage_v = std::min(res.min_bus_voltage_v, v_bus);
        s = rk4_step(s, cfg, total_thrust_cmd, h);
        t += h;
        res.step_count += 1;
        res.final_time_s = t;
        res.max_altitude_m = std::max(res.max_altitude_m, s[2]);
        res.times_s.push_back(t);
        res.positions_m.push_back({s[0], s[1], s[2]});
        res.quaternions_wxyz.push_back({s[6], s[7], s[8], s[9]});
    }
    res.final_position_m = {s[0], s[1], s[2]};
    res.final_quaternion_wxyz = {s[6], s[7], s[8], s[9]};
    return res;
}

} // namespace lab
