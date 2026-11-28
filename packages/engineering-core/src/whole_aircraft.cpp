#include "lab/whole_aircraft.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace lab {
namespace {
constexpr double kPi = std::numbers::pi_v<double>;
constexpr double kGravity = 9.80665;
} // namespace

CoupledJetResult evaluate_coupled_jet_cycle(const CoupledJetParams &p) {
    CoupledJetResult out{};
    if (!std::isfinite(p.mach) || p.mach < 0.0 || !std::isfinite(p.wing_area_m2) || p.wing_area_m2 <= 0.0 ||
        !std::isfinite(p.intake_area_m2) || p.intake_area_m2 <= 0.0 || !std::isfinite(p.total_mass_kg) || p.total_mass_kg <= 0.0) {
        return out;
    }

    const double alt = std::clamp(p.altitude_m, 0.0, 20000.0);
    const double t_k = std::max(216.65, 273.15 + p.oat_c - 0.0065 * alt);
    const double p_atm = 101325.0 * std::pow(1.0 - (0.0065 * alt) / 288.15, 5.25588);
    const double rho = p_atm / (287.058 * t_k);
    const double a_sound = std::sqrt(1.4 * 287.058 * t_k);
    const double v0 = p.mach * a_sound;
    const double q = 0.5 * rho * v0 * v0;
    const double tol_factor = std::clamp(1.0 - p.mfg_tolerance_frac, 0.65, 1.0);

    // MIL-E-5008B inlet total-pressure recovery eta_r(M) + intake spillage penalty if over-captured
    const double eta_r = (p.mach <= 1.0)
                             ? (0.985 - 0.015 * p.mach * p.mach)
                             : std::max(0.45, 1.0 - 0.075 * std::pow(p.mach - 1.0, 1.35));
    out.inlet_recovery_eta = eta_r;
    const double capture_ratio = std::clamp(p.intake_area_m2 / 0.0032, 0.35, 3.0);
    out.spillage_cd = (capture_ratio > 1.25) ? (0.004 * (capture_ratio - 1.25)) : 0.0;
    const double throat_choke_factor = std::min(1.0, capture_ratio / 0.65);

    // Modified Korn wave drag + supersonic shock cone half angle mu = asin(1/M)
    const double cos_sw = std::max(0.35, std::cos(std::abs(p.sweep_deg) * kPi / 180.0));
    out.mach_dd = (0.87 / cos_sw) - (std::clamp(p.wing_tc_ratio, 0.04, 0.18) / (cos_sw * cos_sw)) -
                  (std::abs(p.cl_incomp) / (10.0 * std::pow(cos_sw, 3.0)));
    const double m_cr = std::max(0.40, out.mach_dd - 0.108);
    if (p.mach <= 1.0) {
        out.cd_wave = (p.mach > m_cr) ? std::min(0.18, 20.0 * std::pow(p.mach - m_cr, 4.0)) : 0.0;
    } else {
        // Post-sonic wave drag decay / Ackeret wave drag contribution
        out.cd_wave = std::min(0.24, 0.085 / std::sqrt(std::max(0.15, p.mach * p.mach - 1.0 + 0.18)));
    }
    out.mach_cone_half_angle_deg = (p.mach > 1.001) ? (std::asin(1.0 / p.mach) * 180.0 / kPi) : 90.0;

    // Coupled nozzle expansion & turbine/EDF Brayton cycle
    const double sigma = rho / 1.225;
    const double th = std::clamp(p.throttle_frac, 0.0, 1.08);
    const double nozzle_exp_gain = 1.0 - 0.18 * std::pow(std::clamp(p.nozzle_area_ratio, 0.7, 2.2) - (1.0 + 0.35 * p.mach), 2.0);
    if (p.is_turbine) {
        const double ram_mult = 1.0 + 0.14 * std::min(p.mach * p.mach, 1.8);
        out.nozzle_thrust_n = p.static_thrust_n * std::pow(sigma, 0.85) * eta_r * throat_choke_factor * ram_mult *
                              nozzle_exp_gain * th * tol_factor;
        out.mdot_kg_s = (0.11 + 0.04 * (p.static_thrust_n / 45.0)) * sigma * eta_r * th * (p.intake_area_m2 / 0.0032);
        const double mdot_fuel_kg_min = std::max(0.01, p.fuel_flow_max_kg_min * (0.20 + 0.80 * th) / std::max(0.55, eta_r));
        out.fuel_endurance_min = (p.fuel_mass_kg * tol_factor) / mdot_fuel_kg_min;
        out.egt_c = 280.0 + 435.0 * std::pow(th, 1.25) + 0.5 * p.oat_c + 65.0 * alt / 8000.0 +
                    (p.cooling_grade == 0 ? 48.0 : 0.0) + (throat_choke_factor < 0.90 ? 65.0 : 0.0);
    } else {
        out.nozzle_thrust_n = p.static_thrust_n * sigma * eta_r * throat_choke_factor *
                              std::max(0.05, 1.0 - 0.52 * p.mach) * nozzle_exp_gain * std::pow(th, 1.35) * tol_factor;
        out.mdot_kg_s = 0.08 * sigma * std::max(0.2, th);
        out.fuel_endurance_min = 7.0 / std::max(0.15, th);
        out.egt_c = p.oat_c + 58.0 * std::pow(th, 1.6) + (p.cooling_grade == 0 ? 18.0 : 0.0);
    }

    const double cd_total = 0.020 + out.spillage_cd + out.cd_wave + (p.cl_incomp * p.cl_incomp) / (kPi * 5.2 * 0.82);
    const double total_drag_n = q * p.wing_area_m2 * cd_total;
    out.egt_ok = (out.egt_c <= p.max_egt_c);
    out.mach_ok = (p.mach <= p.max_mach);
    out.thrust_ok = (out.nozzle_thrust_n >= total_drag_n * 0.95);
    out.valid = true;
    return out;
}

CargoSlungLoadResult evaluate_cargo_slung_load(const CargoSlungLoadParams &p) {
    CargoSlungLoadResult out{};
    if (!std::isfinite(p.carrier_mass_kg) || p.carrier_mass_kg <= 0.0 ||
        !std::isfinite(p.cable_length_m) || p.cable_length_m <= 0.05 ||
        !std::isfinite(p.max_thrust_n) || p.max_thrust_n <= 0.0) {
        return out;
    }
    const double m_cargo = p.payload_released ? 0.0 : std::max(0.0, p.cargo_mass_kg);
    out.effective_mass_kg = p.carrier_mass_kg + m_cargo;
    out.pendulum_freq_hz = (1.0 / (2.0 * kPi)) * std::sqrt(kGravity / p.cable_length_m);
    const double q = 0.5 * std::max(0.2, p.rho_kg_m3) * p.airspeed_m_s * p.airspeed_m_s;
    out.blowback_drag_n = p.payload_released ? 0.0 : (q * std::max(0.0, p.box_area_m2) * std::max(0.1, p.box_cd));
    const double w_cargo = m_cargo * kGravity;
    out.trail_angle_deg = (w_cargo > 1e-3) ? (std::atan2(out.blowback_drag_n, w_cargo) * 180.0 / kPi) : 0.0;
    const double cable_tension = std::hypot(w_cargo, out.blowback_drag_n);
    out.cg_offset_torque_nm = cable_tension * std::abs(p.cg_offset_m);
    const double req_thrust = std::hypot(out.effective_mass_kg * kGravity, out.blowback_drag_n);
    out.residual_tw = p.max_thrust_n / std::max(0.1, req_thrust);
    out.stable_ok = (out.residual_tw >= 1.15) && (out.trail_angle_deg <= 38.0) && (out.cg_offset_torque_nm <= 4.5);
    out.valid = true;
    return out;
}

CreatorArchetypeResult evaluate_creator_archetypes(const CreatorArchetypeParams &p) {
    CreatorArchetypeResult out{};
    if (!std::isfinite(p.mass_kg) || p.mass_kg <= 0.0 || !std::isfinite(p.wing_area_m2) || p.wing_area_m2 <= 0.0) {
        return out;
    }
    const double a_disk = std::max(0.015, 0.22 * p.wing_area_m2);
    const double sigma_d = std::clamp(p.duct_area_ratio, 1.0, 1.65);
    out.duct_thrust_gain = (sigma_d > 1.01) ? std::sqrt(2.0 * sigma_d * 0.68) : 1.0;
    const double t_eff = p.max_thrust_n * out.duct_thrust_gain;
    out.propwash_slip_m_s = std::sqrt(p.airspeed_m_s * p.airspeed_m_s + (2.0 * t_eff) / (std::max(0.2, p.rho_kg_m3) * a_disk));

    const double q_slip = 0.5 * p.rho_kg_m3 * out.propwash_slip_m_s * out.propwash_slip_m_s;
    const double elev_rad = std::abs(p.elevon_deflect_deg) * (kPi / 180.0);
    const double chord_est = p.wing_area_m2 / std::max(0.25, p.wingspan_m);
    out.control_moment_nm = q_slip * (0.28 * p.wing_area_m2) * (0.5 * chord_est) * (1.8 * elev_rad);

    if (p.mode == 0) {
        // Tailsitter: transition pitch 90 deg vertical hover -> 0 deg horizontal cruise
        const double theta_rad = std::clamp(p.transition_pitch_deg, 0.0, 90.0) * (kPi / 180.0);
        const double q_air = 0.5 * p.rho_kg_m3 * p.airspeed_m_s * p.airspeed_m_s;
        const double aero_lift = q_air * p.wing_area_m2 * (1.25 * std::sin(2.0 * theta_rad) * 0.45 + 0.55 * std::cos(theta_rad));
        out.effective_lift_n = t_eff * std::sin(theta_rad) + aero_lift;
        out.static_margin_pct = 8.0 + 0.2 * std::abs(p.sweep_deg);
        out.authority_ok = (out.effective_lift_n >= p.mass_kg * kGravity * 1.05) && (out.control_moment_nm >= 0.12);
    } else {
        // Flying Wing: requires swept reflex stability
        const double q_air = 0.5 * p.rho_kg_m3 * p.airspeed_m_s * p.airspeed_m_s;
        out.effective_lift_n = q_air * p.wing_area_m2 * 0.62;
        out.static_margin_pct = -4.0 + 0.55 * std::abs(p.sweep_deg); // Need sweep >= 12 deg for positive static margin
        out.authority_ok = (out.static_margin_pct >= 2.5) && (out.effective_lift_n >= p.mass_kg * kGravity * 0.95);
    }
    out.valid = true;
    return out;
}

FastenerHarnessResult evaluate_fastener_and_harness_safety(const FastenerHarnessParams &p) {
    FastenerHarnessResult out{};
    // ISO 4762 M2, M2.5, M3, M4, M5, M6 shear capacities (Grade 12.9 ~720 MPa * stress area) and steel masses (kg)
    static constexpr double kShear12_9[6] = {1490.0, 2440.0, 3620.0, 6320.0, 10220.0, 14470.0};
    static constexpr double kMassSteel[6] = {0.000255, 0.000525, 0.001000, 0.002300, 0.004000, 0.007600};
    const int idx = std::clamp(p.screw_size_idx, 0, 5);
    const double mat_shear_scale = p.titanium_grade5 ? 0.79 : 1.0;
    const double mat_mass_scale = p.titanium_grade5 ? 0.57 : 1.0;

    out.single_bolt_shear_n = kShear12_9[idx] * mat_shear_scale;
    const int n_bolts = std::max(1, p.fasteners_per_joint);
    out.fastener_mass_kg = static_cast<double>(n_bolts) * kMassSteel[idx] * mat_mass_scale * 4.0;
    out.joint_shear_fos = (out.single_bolt_shear_n * static_cast<double>(n_bolts)) / std::max(0.5, std::abs(p.joint_shear_load_n));
    out.bolt_ok = out.joint_shear_fos >= 1.50;

    // AWG 10..22 Silicone copper lookup
    struct AwgRow { int awg; double r_per_m; double g_per_m; double amp; };
    static constexpr AwgRow kAwg[] = {
        {10, 0.0033, 75.0, 50.0},
        {12, 0.0053, 50.0, 35.0},
        {14, 0.0086, 30.0, 22.0},
        {16, 0.0137, 19.0, 14.0},
        {18, 0.0219, 11.0, 9.0},
        {20, 0.0348, 8.0, 6.0},
        {22, 0.0552, 5.5, 4.0},
    };
    AwgRow sel = kAwg[1]; // default 12 AWG
    int best_diff = 999;
    for (const auto &row : kAwg) {
        const int d = std::abs(row.awg - p.wire_awg);
        if (d < best_diff) {
            best_diff = d;
            sel = row;
        }
    }
    const double wire_len = std::max(0.05, p.harness_length_m);
    out.wire_drop_v = std::abs(p.continuous_current_a) * sel.r_per_m * wire_len * 2.0; // positive + ground return
    out.wire_mass_kg = (sel.g_per_m * 0.001) * wire_len * 2.0;
    out.wire_ampacity_a = sel.amp;
    out.wire_ok = (std::abs(p.continuous_current_a) <= sel.amp * 1.10) && (out.wire_drop_v <= 0.80);
    out.valid = true;
    return out;
}

} // namespace lab
