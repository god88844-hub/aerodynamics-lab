#include "lab/multiphysics_and_rockets.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace lab {
namespace {
constexpr double kPi = std::numbers::pi_v<double>;
constexpr double kGravity = 9.80665;
constexpr double kStefanBoltzmann = 5.670374419e-8;
constexpr double kEarthMu = 3.986004418e14;
constexpr double kEarthRadiusM = 6371000.0;
} // namespace

AeroacousticsResult evaluate_aeroacoustics(const AeroacousticsParams &p) {
    AeroacousticsResult out{};
    if (!std::isfinite(p.rotor_rpm) || p.rotor_rpm < 0.0 || !std::isfinite(p.distance_m) || p.distance_m <= 0.1 ||
        !std::isfinite(p.a_sound_m_s) || p.a_sound_m_s <= 50.0) {
        return out;
    }
    if (!p.is_jet) {
        const int nr = std::max(1, p.rotor_count);
        const int nb = std::max(1, p.blade_count);
        out.bpf_hz = (static_cast<double>(nb) * p.rotor_rpm) / 60.0;
        const double omega = p.rotor_rpm * 2.0 * kPi / 60.0;
        const double v_tip = omega * std::max(0.02, p.rotor_diameter_m) * 0.5;
        const double m_tip = std::max(0.05, v_tip / p.a_sound_m_s);
        const double t_each = std::max(0.1, p.total_thrust_n) / static_cast<double>(nr);
        // Gutin / Lowson dipole SPL @ 15 m reference scaled by tip-Mach & blade loading
        const double spl_one_15m = 56.0 + 26.0 * std::log10(std::max(0.05, m_tip / 0.25)) +
                                   14.0 * std::log10(std::max(0.5, t_each / 5.0));
        const double dist_corr = -20.0 * std::log10(std::max(0.5, p.distance_m) / 15.0);
        out.rotor_spl_dba = spl_one_15m + 10.0 * std::log10(static_cast<double>(nr)) + dist_corr;
        out.total_spl_dba = out.rotor_spl_dba;
        out.noise_ok = (out.total_spl_dba <= p.max_spl_dba);
    } else {
        out.bpf_hz = 0.0;
        const double v_jet = std::max(20.0, p.jet_exhaust_vel_m_s);
        // Lighthill / Stone 8th-power mixing noise scaled to 30 m and shifted to distance_m
        const double d_area = std::max(1e-4, p.jet_nozzle_diam_m * p.jet_nozzle_diam_m);
        const double spl_30m = 82.0 + 35.0 * std::log10(v_jet / 320.0) + 10.0 * std::log10(d_area / 0.008);
        out.jet_spl_db = spl_30m - 20.0 * std::log10(std::max(1.0, p.distance_m) / 30.0);
        out.total_spl_dba = out.jet_spl_db;
        if (p.jet_mach > 1.02) {
            const double h = std::max(80.0, p.altitude_m);
            const double len = std::max(0.4, p.fuselage_len_m);
            const double kr = 1.9;
            const double mach_term = std::pow(p.jet_mach * p.jet_mach - 1.0, 0.125);
            // Carlson simplified N-wave peak ground overpressure
            out.sonic_boom_pa = kr * std::sqrt(std::max(1000.0, p.p_atm_pa)) * mach_term *
                                std::pow(len, 0.25) / std::pow(h, 0.75) * 28.0;
            out.sonic_boom_psf = out.sonic_boom_pa * 0.0208854;
        }
        out.noise_ok = (out.total_spl_dba <= std::max(115.0, p.max_spl_dba)) && (out.sonic_boom_psf <= 2.5);
    }
    out.valid = true;
    return out;
}

HelicopterHighSpeedResult evaluate_helicopter_highspeed(const HelicopterHighSpeedParams &p) {
    HelicopterHighSpeedResult out{};
    if (!std::isfinite(p.mass_kg) || p.mass_kg <= 0.0 || p.rotor_diameter_m <= 0.1 || p.rotor_rpm <= 10.0) {
        return out;
    }
    const double r = p.rotor_diameter_m * 0.5;
    const double omega = p.rotor_rpm * 2.0 * kPi / 60.0;
    const double v_tip = omega * r;
    const double v_horiz = std::abs(p.horizontal_speed_m_s);
    out.advance_ratio_mu = v_horiz / std::max(1.0, v_tip);
    out.advancing_tip_mach = (v_tip + v_horiz) / std::max(50.0, p.a_sound_m_s);

    const double area = kPi * r * r;
    const double weight = p.mass_kg * kGravity;
    out.hover_induced_vel_m_s = std::sqrt(weight / std::max(0.05, 2.0 * p.rho_kg_m3 * area));
    out.vrs_ratio = p.vertical_speed_m_s / std::max(0.5, out.hover_induced_vel_m_s);
    out.vrs_entered = (out.vrs_ratio <= -0.35 && out.vrs_ratio >= -1.25) && (v_horiz < 0.70 * out.hover_induced_vel_m_s);
    out.retreating_stall_risk = (out.advance_ratio_mu > 0.42);
    out.gyro_precession_torque_nm = std::max(0.01, p.rotor_inertia_kg_m2) * omega * std::abs(p.pitch_or_roll_rate_rad_s);
    out.envelope_ok = (!out.vrs_entered) && (!out.retreating_stall_risk) && (out.advancing_tip_mach <= 0.90);
    out.valid = true;
    return out;
}

HydroCavitationResult evaluate_hydro_cavitation(const HydroCavitationParams &p) {
    HydroCavitationResult out{};
    if (!std::isfinite(p.prop_diameter_m) || p.prop_diameter_m <= 0.01 || p.prop_rpm <= 0.0) {
        return out;
    }
    const double omega = p.prop_rpm * 2.0 * kPi / 60.0;
    out.tip_speed_m_s = omega * (p.prop_diameter_m * 0.5);
    // Antoine approximation for water vapor pressure (Pa) between 0 and 60 C
    const double tc = std::clamp(p.water_temp_c, 0.0, 60.0);
    const double mmhg = std::pow(10.0, 8.07131 - 1730.63 / (233.426 + tc));
    out.vapor_pressure_pa = mmhg * 133.322;
    const double p_local = p.p_atm_pa + p.water_rho_kg_m3 * kGravity * std::max(0.0, p.submergence_depth_m);
    const double q_w = 0.5 * p.water_rho_kg_m3 * out.tip_speed_m_s * out.tip_speed_m_s;
    out.cavitation_number = (p_local - out.vapor_pressure_pa) / std::max(1.0, q_w);
    out.cavitating = (out.cavitation_number < p.sigma_crit);
    out.valid = true;
    return out;
}

RfStealthResult evaluate_rf_and_rcs(const RfStealthParams &p) {
    RfStealthResult out{};
    if (!std::isfinite(p.distance_km) || p.distance_km <= 0.001 || !std::isfinite(p.frequency_mhz) || p.frequency_mhz <= 1.0) {
        return out;
    }
    out.fspl_db = 32.44 + 20.0 * std::log10(p.frequency_mhz) + 20.0 * std::log10(p.distance_km);
    // ITU-R P.838 rain attenuation approximation scaled by frequency GHz and path km
    const double f_ghz = p.frequency_mhz / 1000.0;
    const double k_rain = 0.00018 * std::pow(f_ghz, 2.2);
    out.rain_fade_db = (p.rain_mm_h > 0.0) ? (k_rain * std::pow(p.rain_mm_h, 1.05) * p.distance_km) : 0.0;
    out.received_power_dbm = p.tx_power_dbm + p.tx_gain_dbi + p.rx_gain_dbi - out.fspl_db - out.rain_fade_db;
    out.link_margin_db = out.received_power_dbm - p.rx_sensitivity_dbm;
    out.link_ok = (out.link_margin_db >= 6.0);

    // Physical-optics swept/faceted X-band RCS estimate (sweep reduces head-on specular lobe)
    const double cos_sw = std::max(0.25, std::cos(std::clamp(std::abs(p.sweep_deg), 0.0, 68.0) * kPi / 180.0));
    const double shape_factor = p.stealth_shaping ? 0.08 : 1.0;
    out.rcs_m2 = std::max(1e-4, p.frontal_area_m2 * 1.45 * std::pow(cos_sw, 2.4) * shape_factor);
    out.rcs_dbsm = 10.0 * std::log10(out.rcs_m2);
    out.valid = true;
    return out;
}

RocketSpaceflightResult evaluate_rocket_and_hypersonics(const RocketSpaceflightParams &p) {
    RocketSpaceflightResult out{};
    if (p.dry_mass_stage1_kg <= 0.0 || p.dry_mass_stage2_kg <= 0.0 || p.payload_mass_kg < 0.0 ||
        p.isp_stage1_s <= 50.0 || p.isp_stage2_s <= 50.0 || p.liftoff_thrust_n <= 0.0) {
        return out;
    }
    const double m_stage3_full = std::max(0.0, p.dry_mass_stage3_kg + p.prop_mass_stage3_kg);
    const double m_upper_full = p.dry_mass_stage2_kg + p.prop_mass_stage2_kg + m_stage3_full + p.payload_mass_kg;
    const double m_upper_empty = p.dry_mass_stage2_kg + m_stage3_full + p.payload_mass_kg;
    const double m0 = p.dry_mass_stage1_kg + p.prop_mass_stage1_kg + m_upper_full;
    const double m1_burnout = p.dry_mass_stage1_kg + m_upper_full;
    out.total_mass_kg = m0;
    out.liftoff_tw = p.liftoff_thrust_n / (m0 * kGravity);

    out.delta_v_stage1_m_s = p.isp_stage1_s * kGravity * std::log(m0 / std::max(1.0, m1_burnout));
    out.delta_v_stage2_m_s = p.isp_stage2_s * kGravity * std::log(m_upper_full / std::max(1.0, m_upper_empty));
    if (p.prop_mass_stage3_kg > 1.0 && p.dry_mass_stage3_kg > 0.0 && p.isp_stage3_s > 50.0) {
        const double m3_full = p.dry_mass_stage3_kg + p.prop_mass_stage3_kg + p.payload_mass_kg;
        const double m3_empty = p.dry_mass_stage3_kg + p.payload_mass_kg;
        out.delta_v_stage3_m_s = p.isp_stage3_s * kGravity * std::log(m3_full / std::max(1.0, m3_empty));
    }
    out.total_delta_v_m_s = out.delta_v_stage1_m_s + out.delta_v_stage2_m_s + out.delta_v_stage3_m_s;
    const double grav_drag_loss = 1450.0 + std::max(0.0, 1.35 - out.liftoff_tw) * 650.0;
    out.net_delta_v_m_s = std::max(0.0, out.total_delta_v_m_s - grav_drag_loss);

    const double r_orbit = kEarthRadiusM + std::max(80000.0, p.target_altitude_m);
    out.orbital_vel_req_m_s = std::sqrt(kEarthMu / r_orbit);
    out.orbit_capable = (out.net_delta_v_m_s >= out.orbital_vel_req_m_s * 0.96);

    // Peak dynamic pressure (Max-Q around ~11 km) amplified by upper-altitude launch wind shear & turbulence gusts
    const double rho_maxq = 0.36;
    const double v_maxq = 380.0 * std::clamp(out.liftoff_tw / 1.4, 0.7, 1.6);
    const double wind_gust_factor = 1.0 + 0.025 * std::max(0.0, p.wind_speed_m_s) * (1.0 + std::clamp(p.turbulence_frac, 0.0, 0.6));
    out.max_q_pa = 0.5 * rho_maxq * v_maxq * v_maxq * wind_gust_factor;

    const double h_re = std::clamp(p.reentry_altitude_m, 20000.0, 140000.0);
    const double rho_re = 1.225 * std::exp(-h_re / 7200.0);
    const double k_sg = 1.7415e-4; // Earth air Sutton-Graves constant
    const double rn = std::max(0.02, p.nose_radius_m);
    out.reentry_heat_flux_w_m2 = k_sg * std::sqrt(rho_re / rn) * std::pow(std::max(0.0, p.reentry_speed_m_s), 3.0);
    const double emissivity = 0.85;
    const double t_k = std::pow(out.reentry_heat_flux_w_m2 / (emissivity * kStefanBoltzmann) + std::pow(250.0, 4.0), 0.25);
    out.tps_wall_temp_c = t_k - 273.15;

    // Mean free path scales inversely with density: lambda_0 ~ 6.6e-8 m at sea level
    const double lambda_m = 6.6e-8 * (1.225 / std::max(1e-12, rho_re));
    out.knudsen_number = lambda_m / std::max(0.05, p.diameter_m);

    out.liftoff_ok = (out.liftoff_tw >= 1.15);
    out.tps_ok = (out.tps_wall_temp_c <= p.tps_max_temp_c);
    out.flight_ok = out.liftoff_ok && out.tps_ok && (out.max_q_pa <= 65000.0);
    out.valid = true;
    return out;
}

std::vector<RocketAscentSample> compute_rocket_ascent_trajectory(const RocketSpaceflightParams &p) {
    const auto r = evaluate_rocket_and_hypersonics(p);
    std::vector<RocketAscentSample> pts;
    const double t_total = std::max(120.0, p.stage_separation_t_s * 3.0);
    const double target_alt_km = std::max(90.0, p.target_altitude_m / 1000.0);
    for (int i = 0; i <= 11; ++i) {
        const double u = static_cast<double>(i) / 11.0;
        const double t = u * t_total;
        const double h_km = target_alt_km * std::pow(u, 1.55);
        const double vel = r.net_delta_v_m_s * (0.28 * u + 0.72 * u * u);
        const double rho = 1.225 * std::exp(-(h_km * 1000.0) / 7200.0);
        const double q_kpa = 0.5 * rho * vel * vel * 0.001;
        pts.push_back({t, h_km, vel, q_kpa});
    }
    return pts;
}

} // namespace lab
