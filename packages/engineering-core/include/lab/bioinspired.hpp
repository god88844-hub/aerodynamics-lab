#pragma once

namespace lab {

struct FlappingParams {
    double wing_radius_m = 0.080;
    double mean_chord_m = 0.028;
    double flap_freq_hz = 40.0;
    double stroke_amp_rad = 1.3613568; // 78 deg
    double feathering_amp_rad = 0.785;
    double mean_aoa_rad = 0.65;
    double vehicle_mass_kg = 0.032;
    double forward_airspeed_m_s = 2.2;
    double rho_kg_m3 = 1.225;
    double reduced_time_tau = 4.0;
    double mfg_tolerance_frac = 0.05;
    int n_wings = 2;
    int n_strips = 16;
};

struct FlappingResult {
    bool valid = false;
    double tip_mach = 0.0;
    double reduced_freq_k = 0.0;
    double strouhal = 0.0;
    double theodorsen_mag = 1.0;
    double wagner_phi = 1.0;
    double mean_lift_n = 0.0;
    double mean_drag_n = 0.0;
    double hover_tw = 0.0;
    double aero_shaft_power_w = 0.0;
    bool envelope_ok = true;
};

struct MorphingParams {
    double baseline_span_m = 1.15;
    double baseline_area_m2 = 0.21;
    double wing_tuck_frac = 0.25;
    double wing_asym_diff = 0.0;
    double tail_spread_frac = 0.65;
    double tail_tilt_rad = 0.0;
    double alpha_rad = 0.08;
    double airspeed_m_s = 14.0;
    double rho_kg_m3 = 1.225;
    double vehicle_mass_kg = 1.05;
};

struct MorphingResult {
    bool valid = false;
    double effective_span_m = 0.0;
    double effective_area_m2 = 0.0;
    double cl = 0.0;
    double cd = 0.0;
    double lift_n = 0.0;
    double drag_n = 0.0;
    double roll_moment_nm = 0.0;
    double yaw_damping_coeff = 0.0;
    double wing_loading_n_m2 = 0.0;
};

struct FlexBeamParams {
    double span_m = 0.080;
    double section_mass_kg = 0.004;
    double ei_nm2 = 0.045;
    double gj_nm2 = 0.025;
    double youngs_modulus_pa = 3.2e9;
    double thickness_m = 0.0012;
    double chord_m = 0.028;
    double endurance_limit_pa = 45.0e6;
    double peak_lift_n = 0.25;
    double airspeed_m_s = 8.0;
    double rho_kg_m3 = 1.225;
    int applied_cycles = 50000;
    int max_cycles_budget = 250000;
};

struct FlexBeamResult {
    bool valid = false;
    double first_mode_hz = 0.0;
    double tip_deflection_mm = 0.0;
    double deflection_span_ratio = 0.0;
    double peak_root_stress_pa = 0.0;
    double fatigue_stress_ratio = 0.0;
    double divergence_q_pa = 0.0;
    double divergence_margin = 10.0;
    bool structural_ok = false;
};

struct SeaplanePlaningParams {
    double total_mass_kg = 2.75;
    double float_beam_m = 0.14;
    double float_length_m = 1.06;
    double deadrise_deg = 18.0;
    double water_chop_m = 0.04;
    double wing_area_m2 = 0.40;
    double wing_cl = 0.75;
    double speed_m_s = 12.0;
    double trim_deg = 6.0;
    double air_rho_kg_m3 = 1.225;
};

struct SeaplanePlaningResult {
    bool valid = false;
    double speed_coef_cv = 0.0;
    double hydro_lift_n = 0.0;
    double hydro_drag_n = 0.0;
    double hump_resistance_n = 0.0;
    double buoyancy_reserve_ratio = 0.0;
    bool planing_or_buoyant_ok = false;
};

double compute_theodorsen_mag(double k);
double compute_wagner_phi(double tau);
FlappingResult evaluate_flapping_strip_bemt(const FlappingParams &p);
MorphingResult evaluate_morphing_stability(const MorphingParams &p);
FlexBeamResult evaluate_compliant_flex_aeroelastic(const FlexBeamParams &p);
SeaplanePlaningResult evaluate_savitsky_seaplane(const SeaplanePlaningParams &p);

} // namespace lab
