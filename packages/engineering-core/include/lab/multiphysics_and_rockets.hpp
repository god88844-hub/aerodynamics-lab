#pragma once

namespace lab {

struct AeroacousticsParams {
    int rotor_count = 4;
    int blade_count = 2;
    double rotor_rpm = 4800.0;
    double rotor_diameter_m = 0.381;
    double total_thrust_n = 35.0;
    double rho_kg_m3 = 1.225;
    double a_sound_m_s = 340.3;
    double distance_m = 15.0;
    bool is_jet = false;
    double jet_mach = 0.30;
    double jet_exhaust_vel_m_s = 380.0;
    double jet_nozzle_diam_m = 0.095;
    double fuselage_len_m = 1.32;
    double altitude_m = 500.0;
    double p_atm_pa = 101325.0;
    double max_spl_dba = 88.0;
};

struct AeroacousticsResult {
    bool valid = false;
    double bpf_hz = 0.0;
    double rotor_spl_dba = 0.0;
    double jet_spl_db = 0.0;
    double total_spl_dba = 0.0;
    double sonic_boom_pa = 0.0;
    double sonic_boom_psf = 0.0;
    bool noise_ok = true;
};

struct HelicopterHighSpeedParams {
    double mass_kg = 3.2;
    double rotor_diameter_m = 1.48;
    double rotor_rpm = 1450.0;
    double rotor_inertia_kg_m2 = 0.14;
    double horizontal_speed_m_s = 12.0;
    double vertical_speed_m_s = 0.0; // negative = descent
    double pitch_or_roll_rate_rad_s = 0.35;
    double rho_kg_m3 = 1.225;
    double a_sound_m_s = 340.3;
};

struct HelicopterHighSpeedResult {
    bool valid = false;
    double advance_ratio_mu = 0.0;
    double advancing_tip_mach = 0.0;
    double hover_induced_vel_m_s = 0.0;
    double vrs_ratio = 0.0;
    bool vrs_entered = false;
    bool retreating_stall_risk = false;
    double gyro_precession_torque_nm = 0.0;
    bool envelope_ok = true;
};

struct HydroCavitationParams {
    double prop_diameter_m = 0.14;
    double prop_rpm = 3800.0;
    double submergence_depth_m = 0.35;
    double water_temp_c = 20.0;
    double water_rho_kg_m3 = 1025.0;
    double p_atm_pa = 101325.0;
    double sigma_crit = 0.35;
};

struct HydroCavitationResult {
    bool valid = false;
    double tip_speed_m_s = 0.0;
    double vapor_pressure_pa = 0.0;
    double cavitation_number = 0.0;
    bool cavitating = false;
};

struct RfStealthParams {
    double distance_km = 2.5;
    double frequency_mhz = 2400.0;
    double tx_power_dbm = 20.0;
    double tx_gain_dbi = 2.0;
    double rx_gain_dbi = 5.0;
    double rx_sensitivity_dbm = -98.0;
    double rain_mm_h = 0.0;
    double sweep_deg = 26.0;
    double frontal_area_m2 = 0.08;
    bool stealth_shaping = false;
};

struct RfStealthResult {
    bool valid = false;
    double fspl_db = 0.0;
    double rain_fade_db = 0.0;
    double received_power_dbm = 0.0;
    double link_margin_db = 0.0;
    double rcs_m2 = 0.0;
    double rcs_dbsm = 0.0;
    bool link_ok = true;
};

struct RocketSpaceflightParams {
    double dry_mass_stage1_kg = 2200.0;
    double prop_mass_stage1_kg = 18500.0;
    double isp_stage1_s = 295.0;
    double dry_mass_stage2_kg = 480.0;
    double prop_mass_stage2_kg = 4200.0;
    double isp_stage2_s = 348.0;
    double payload_mass_kg = 250.0;
    double liftoff_thrust_n = 340000.0;
    double diameter_m = 1.65;
    double target_altitude_m = 220000.0; // LEO default 220 km
    double nose_radius_m = 0.85;         // Blunt re-entry heatshield radius (m)
    double reentry_speed_m_s = 7650.0;
    double reentry_altitude_m = 68000.0;
    double tps_max_temp_c = 1850.0;
    double stage_separation_t_s = 125.0;
};

struct RocketSpaceflightResult {
    bool valid = false;
    double total_mass_kg = 0.0;
    double liftoff_tw = 0.0;
    double delta_v_stage1_m_s = 0.0;
    double delta_v_stage2_m_s = 0.0;
    double total_delta_v_m_s = 0.0;
    double net_delta_v_m_s = 0.0;
    double orbital_vel_req_m_s = 0.0;
    double max_q_pa = 0.0;
    double reentry_heat_flux_w_m2 = 0.0;
    double tps_wall_temp_c = 0.0;
    double knudsen_number = 0.0;
    bool orbit_capable = false;
    bool tps_ok = true;
    bool liftoff_ok = true;
    bool flight_ok = true;
};

AeroacousticsResult evaluate_aeroacoustics(const AeroacousticsParams &p);
HelicopterHighSpeedResult evaluate_helicopter_highspeed(const HelicopterHighSpeedParams &p);
HydroCavitationResult evaluate_hydro_cavitation(const HydroCavitationParams &p);
RfStealthResult evaluate_rf_and_rcs(const RfStealthParams &p);
RocketSpaceflightResult evaluate_rocket_and_hypersonics(const RocketSpaceflightParams &p);

} // namespace lab
