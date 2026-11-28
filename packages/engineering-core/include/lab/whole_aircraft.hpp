#pragma once

namespace lab {

struct CoupledJetParams {
    double mach = 0.30;
    double altitude_m = 0.0;
    double oat_c = 25.0;
    double wing_area_m2 = 0.35;
    double sweep_deg = 26.0;
    double wing_tc_ratio = 0.09;
    double cl_incomp = 0.25;
    double intake_area_m2 = 0.0032;
    double nozzle_area_ratio = 1.15; // A_exit / A_throat
    double throttle_frac = 0.85;
    double static_thrust_n = 44.15;
    double max_egt_c = 720.0;
    double max_mach = 1.65;
    double fuel_mass_kg = 0.85;
    double fuel_flow_max_kg_min = 0.150;
    double total_mass_kg = 4.9;
    double mfg_tolerance_frac = 0.05;
    int cooling_grade = 1; // 0=poor, 1=med, 2=good
    bool is_turbine = true;
};

struct CoupledJetResult {
    bool valid = false;
    double inlet_recovery_eta = 1.0;
    double spillage_cd = 0.0;
    double nozzle_thrust_n = 0.0;
    double mdot_kg_s = 0.0;
    double egt_c = 500.0;
    double mach_dd = 0.80;
    double cd_wave = 0.0;
    double mach_cone_half_angle_deg = 90.0;
    double fuel_endurance_min = 0.0;
    bool egt_ok = true;
    bool mach_ok = true;
    bool thrust_ok = true;
};

struct CargoSlungLoadParams {
    double carrier_mass_kg = 4.2;
    double cargo_mass_kg = 1.8;
    double cable_length_m = 1.2;
    double box_area_m2 = 0.09;
    double box_cd = 1.35;
    double cg_offset_m = 0.02;
    double airspeed_m_s = 12.0;
    double rho_kg_m3 = 1.225;
    double max_thrust_n = 92.0;
    bool payload_released = false;
};

struct CargoSlungLoadResult {
    bool valid = false;
    double effective_mass_kg = 0.0;
    double pendulum_freq_hz = 0.0;
    double blowback_drag_n = 0.0;
    double trail_angle_deg = 0.0;
    double cg_offset_torque_nm = 0.0;
    double residual_tw = 0.0;
    bool stable_ok = false;
};

struct CreatorArchetypeParams {
    int mode = 0; // 0=Tailsitter, 1=FlyingWing
    double mass_kg = 1.4;
    double wingspan_m = 1.15;
    double wing_area_m2 = 0.28;
    double sweep_deg = 22.0;
    double max_thrust_n = 28.0;
    double airspeed_m_s = 14.0;
    double transition_pitch_deg = 70.0; // 90 = vertical hover, 0 = level cruise
    double elevon_deflect_deg = 12.0;
    double duct_area_ratio = 1.0;
    double rho_kg_m3 = 1.225;
};

struct CreatorArchetypeResult {
    bool valid = false;
    double propwash_slip_m_s = 0.0;
    double control_moment_nm = 0.0;
    double static_margin_pct = 0.0;
    double duct_thrust_gain = 1.0;
    double effective_lift_n = 0.0;
    bool authority_ok = false;
};

struct FastenerHarnessParams {
    int screw_size_idx = 2; // 0=M2, 1=M2.5, 2=M3, 3=M4, 4=M5, 5=M6
    bool titanium_grade5 = false;
    int fasteners_per_joint = 4;
    double joint_shear_load_n = 120.0;
    int wire_awg = 12; // 10,12,14,16,18,20,22
    double harness_length_m = 0.6;
    double continuous_current_a = 24.0;
};

struct FastenerHarnessResult {
    bool valid = false;
    double single_bolt_shear_n = 0.0;
    double joint_shear_fos = 0.0;
    double fastener_mass_kg = 0.0;
    double wire_drop_v = 0.0;
    double wire_mass_kg = 0.0;
    double wire_ampacity_a = 35.0;
    bool bolt_ok = false;
    bool wire_ok = false;
};

CoupledJetResult evaluate_coupled_jet_cycle(const CoupledJetParams &p);
CargoSlungLoadResult evaluate_cargo_slung_load(const CargoSlungLoadParams &p);
CreatorArchetypeResult evaluate_creator_archetypes(const CreatorArchetypeParams &p);
FastenerHarnessResult evaluate_fastener_and_harness_safety(const FastenerHarnessParams &p);

} // namespace lab
