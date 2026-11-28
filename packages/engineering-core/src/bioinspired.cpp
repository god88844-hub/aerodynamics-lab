#include "lab/bioinspired.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace lab {
namespace {
constexpr double kPi = std::numbers::pi_v<double>;
constexpr double kGravity = 9.80665;
} // namespace

double compute_theodorsen_mag(double k) {
    if (!std::isfinite(k) || k <= 0.0) return 1.0;
    const double a1 = 0.0455 / k;
    const double a2 = 0.3000 / k;
    const double d1 = 1.0 + a1 * a1;
    const double d2 = 1.0 + a2 * a2;
    const double re = 1.0 - (0.165 / d1) - (0.335 / d2);
    const double im = -((0.165 * a1) / d1 + (0.335 * a2) / d2);
    return std::hypot(re, im);
}

double compute_wagner_phi(double tau) {
    if (!std::isfinite(tau) || tau <= 0.0) return 0.5;
    return 1.0 - 0.165 * std::exp(-0.0455 * tau) - 0.335 * std::exp(-0.30 * tau);
}

FlappingResult evaluate_flapping_strip_bemt(const FlappingParams &p) {
    FlappingResult out{};
    if (!std::isfinite(p.wing_radius_m) || p.wing_radius_m <= 0.0 ||
        !std::isfinite(p.mean_chord_m) || p.mean_chord_m <= 0.0 ||
        !std::isfinite(p.flap_freq_hz) || p.flap_freq_hz <= 0.0 ||
        !std::isfinite(p.stroke_amp_rad) || p.stroke_amp_rad <= 0.0 ||
        !std::isfinite(p.vehicle_mass_kg) || p.vehicle_mass_kg <= 0.0 ||
        !std::isfinite(p.rho_kg_m3) || p.rho_kg_m3 <= 0.0) {
        return out;
    }

    const int n_strips = std::max(4, p.n_strips);
    const double dr_hat = 1.0 / static_cast<double>(n_strips);
    const double omega = 2.0 * kPi * p.flap_freq_hz;
    const double rms_phidot = omega * p.stroke_amp_rad / std::sqrt(2.0);
    const double u_tip = omega * p.stroke_amp_rad * p.wing_radius_m;
    out.tip_mach = u_tip / 340.3;
    out.wagner_phi = compute_wagner_phi(p.reduced_time_tau);

    const double cl_trans = std::max(0.05, 0.225 + 1.58 * std::sin(2.13 * p.mean_aoa_rad - 0.125));
    const double cd_trans = std::max(0.10, 1.92 - 1.55 * std::cos(2.04 * p.mean_aoa_rad - 0.171));
    const double rot_boost = 1.0 + 0.18 * (p.feathering_amp_rad / 1.2);
    const double tol_factor = std::clamp(1.0 - p.mfg_tolerance_frac, 0.5, 1.0);

    double lift_sum = 0.0;
    double power_sum = 0.0;
    double area_sum = 0.0;
    double k_weighted = 0.0;

    for (int i = 0; i < n_strips; ++i) {
        const double r_hat = (static_cast<double>(i) + 0.5) * dr_hat;
        // Mild rounded/elliptic bio-wing planform maintaining mean_chord
        const double c_local = p.mean_chord_m * (1.12 - 0.24 * r_hat * r_hat);
        const double u_flap = rms_phidot * (r_hat * p.wing_radius_m);
        const double u_eff = std::max(0.20, std::hypot(p.forward_airspeed_m_s, u_flap));
        const double ds = c_local * (dr_hat * p.wing_radius_m);
        const double k_i = std::min(1.8, (omega * c_local) / (2.0 * u_eff));
        const double c_k_i = compute_theodorsen_mag(k_i);

        const double q_flap = 0.5 * p.rho_kg_m3 * u_flap * u_flap;
        lift_sum += q_flap * ds * cl_trans * rot_boost * (0.75 + 0.25 * c_k_i) * out.wagner_phi;
        power_sum += 0.5 * p.rho_kg_m3 * ds * (u_flap * u_flap * u_flap) * cd_trans;
        area_sum += ds;
        k_weighted += k_i * ds;
    }

    const double u_ref_global = std::max(0.25, std::hypot(p.forward_airspeed_m_s, rms_phidot * p.wing_radius_m * std::sqrt(0.3333)));
    out.reduced_freq_k = (area_sum > 0.0) ? (k_weighted / area_sum) : ((omega * p.mean_chord_m) / (2.0 * u_ref_global));
    out.theodorsen_mag = compute_theodorsen_mag(std::min(1.5, out.reduced_freq_k));
    const double stroke_arc = 2.0 * p.wing_radius_m * std::sin(p.stroke_amp_rad);
    out.strouhal = (p.forward_airspeed_m_s > 0.25) ? ((p.flap_freq_hz * stroke_arc) / p.forward_airspeed_m_s) : 0.0;

    out.mean_lift_n = static_cast<double>(p.n_wings) * lift_sum * tol_factor;
    out.mean_drag_n = 0.5 * p.rho_kg_m3 * p.forward_airspeed_m_s * p.forward_airspeed_m_s * (static_cast<double>(p.n_wings) * area_sum) * 0.14;
    out.aero_shaft_power_w = static_cast<double>(p.n_wings) * power_sum;
    const double w_n = p.vehicle_mass_kg * kGravity;
    out.hover_tw = out.mean_lift_n / w_n;
    out.envelope_ok = (out.tip_mach <= 0.25) && (out.hover_tw >= 1.05);
    out.valid = true;
    return out;
}

MorphingResult evaluate_morphing_stability(const MorphingParams &p) {
    MorphingResult out{};
    if (!std::isfinite(p.baseline_span_m) || p.baseline_span_m <= 0.0 ||
        !std::isfinite(p.baseline_area_m2) || p.baseline_area_m2 <= 0.0 ||
        !std::isfinite(p.airspeed_m_s) || p.airspeed_m_s < 0.0 ||
        !std::isfinite(p.rho_kg_m3) || p.rho_kg_m3 <= 0.0 ||
        !std::isfinite(p.vehicle_mass_kg) || p.vehicle_mass_kg <= 0.0) {
        return out;
    }

    const double tuck = std::clamp(p.wing_tuck_frac, 0.0, 1.0);
    const double tail_spr = std::clamp(p.tail_spread_frac, 0.0, 1.0);
    out.effective_span_m = p.baseline_span_m * (1.0 - 0.38 * tuck);
    out.effective_area_m2 = p.baseline_area_m2 * (1.0 - 0.30 * tuck);

    const double ar_eff = std::max(2.0, (out.effective_span_m * out.effective_span_m) / std::max(0.01, out.effective_area_m2));
    const double cl_alpha = (2.0 * kPi * ar_eff) / (ar_eff + 2.0);
    out.cl = cl_alpha * (p.alpha_rad + 0.045 * (1.0 - 0.4 * tuck));
    out.cd = 0.022 + 0.008 * tail_spr + (out.cl * out.cl) / (kPi * ar_eff * 0.85);

    const double q = 0.5 * p.rho_kg_m3 * p.airspeed_m_s * p.airspeed_m_s;
    out.lift_n = q * out.effective_area_m2 * out.cl;
    out.drag_n = q * out.effective_area_m2 * out.cd;
    out.roll_moment_nm = q * out.effective_area_m2 * out.effective_span_m * (0.14 * std::clamp(p.wing_asym_diff, -0.5, 0.5));
    out.yaw_damping_coeff = (0.04 + 0.08 * tail_spr) * std::cos(p.tail_tilt_rad);
    out.wing_loading_n_m2 = (p.vehicle_mass_kg * kGravity) / out.effective_area_m2;
    out.valid = true;
    return out;
}

FlexBeamResult evaluate_compliant_flex_aeroelastic(const FlexBeamParams &p) {
    FlexBeamResult out{};
    if (!std::isfinite(p.span_m) || p.span_m <= 0.0 ||
        !std::isfinite(p.section_mass_kg) || p.section_mass_kg <= 0.0 ||
        !std::isfinite(p.ei_nm2) || p.ei_nm2 <= 0.0 ||
        !std::isfinite(p.gj_nm2) || p.gj_nm2 <= 0.0) {
        return out;
    }

    const double m_prime = p.section_mass_kg / p.span_m;
    out.first_mode_hz = (1.875 * 1.875 / (2.0 * kPi)) * std::sqrt(p.ei_nm2 / (m_prime * std::pow(p.span_m, 4.0)));
    const double w_dist = std::max(0.01, std::abs(p.peak_lift_n) / p.span_m);
    const double tip_m = (w_dist * std::pow(p.span_m, 4.0)) / (8.0 * p.ei_nm2);
    out.tip_deflection_mm = tip_m * 1000.0;
    out.deflection_span_ratio = tip_m / p.span_m;

    const double root_moment = 0.5 * w_dist * p.span_m * p.span_m;
    const double I_eq = std::max(1e-14, p.ei_nm2 / std::max(1e6, p.youngs_modulus_pa));
    out.peak_root_stress_pa = (root_moment * (p.thickness_m * 0.5)) / I_eq;
    out.fatigue_stress_ratio = out.peak_root_stress_pa / std::max(1e3, p.endurance_limit_pa);

    const double ec_arm = std::max(0.002, 0.20 * p.chord_m);
    out.divergence_q_pa = (kPi * kPi * p.gj_nm2) / (4.0 * p.span_m * p.span_m * p.chord_m * ec_arm * 0.8);
    const double q_dyn = std::max(0.5, 0.5 * p.rho_kg_m3 * p.airspeed_m_s * p.airspeed_m_s);
    out.divergence_margin = out.divergence_q_pa / q_dyn;

    const bool cycles_ok = p.applied_cycles <= p.max_cycles_budget;
    out.structural_ok = cycles_ok &&
                        (out.deflection_span_ratio < 0.25) &&
                        (out.fatigue_stress_ratio <= 0.80) &&
                        (out.divergence_margin >= 1.50);
    out.valid = true;
    return out;
}

SeaplanePlaningResult evaluate_savitsky_seaplane(const SeaplanePlaningParams &p) {
    SeaplanePlaningResult out{};
    if (!std::isfinite(p.total_mass_kg) || p.total_mass_kg <= 0.0 ||
        !std::isfinite(p.float_beam_m) || p.float_beam_m <= 0.0 ||
        !std::isfinite(p.float_length_m) || p.float_length_m <= 0.0 ||
        !std::isfinite(p.speed_m_s) || p.speed_m_s < 0.0) {
        return out;
    }
    constexpr double kRhoWater = 1000.0;
    constexpr double kNuWater = 1.004e-6;
    const double weight_n = p.total_mass_kg * kGravity;
    const double b = p.float_beam_m;
    const double l = p.float_length_m;
    const double vol_both = 2.0 * (0.58 * b * b * l);
    out.buoyancy_reserve_ratio = (vol_both * kRhoWater * kGravity) / weight_n;

    const double v_hump = 0.45 * std::sqrt(kGravity * l);
    const double q_hump = 0.5 * p.air_rho_kg_m3 * v_hump * v_hump;
    const double aero_l_hump = q_hump * p.wing_area_m2 * std::max(0.2, p.wing_cl * 0.7);
    const double w_water_hump = std::max(0.0, weight_n - aero_l_hump);
    const double chop_pen = 1.0 + 1.8 * std::max(0.0, p.water_chop_m / b);
    out.hump_resistance_n = w_water_hump * (0.24 + 0.002 * p.deadrise_deg) * chop_pen;

    out.speed_coef_cv = p.speed_m_s / std::sqrt(kGravity * b);
    if (out.speed_coef_cv >= 1.0 && p.trim_deg > 0.2) {
        const double lam = std::clamp(l / b, 1.0, 6.0);
        const double cv_term = 0.0120 * std::sqrt(lam) + 0.0055 * (std::pow(lam, 2.5) / (out.speed_coef_cv * out.speed_coef_cv));
        const double cl0 = std::pow(p.trim_deg, 1.1) * cv_term;
        const double cl_beta = std::max(0.0, cl0 - 0.0065 * p.deadrise_deg * std::pow(std::max(1e-6, cl0), 0.60));
        const double q_w = 0.5 * kRhoWater * p.speed_m_s * p.speed_m_s;
        out.hydro_lift_n = 2.0 * q_w * (b * b) * cl_beta;
        const double re_w = std::max(1e4, (p.speed_m_s * lam * b) / kNuWater);
        const double cf = 0.075 / std::pow(std::log10(re_w) - 2.0, 2.0);
        const double drag_friction = 2.0 * q_w * (lam * b * b) * cf;
        out.hydro_drag_n = out.hydro_lift_n * std::tan(p.trim_deg * kPi / 180.0) + drag_friction;
    } else {
        out.hydro_lift_n = std::min(weight_n, out.buoyancy_reserve_ratio * weight_n);
        out.hydro_drag_n = out.hump_resistance_n * std::min(1.0, p.speed_m_s / std::max(0.5, v_hump));
    }

    out.planing_or_buoyant_ok = out.buoyancy_reserve_ratio >= 1.80;
    out.valid = true;
    return out;
}

} // namespace lab
