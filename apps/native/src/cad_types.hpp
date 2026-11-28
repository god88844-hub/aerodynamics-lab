#pragma once

#include "lab/mechanical_mates.hpp"
#include "lab/standard_library.hpp"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace aerolab {

enum class VehicleFamily {
    Multirotor = 0,
    FixedWing = 1,
    Helicopter = 2,
    VTOL = 3,
    CustomPart = 4,
    Benchmark200 = 5,
    Seaplane = 6,
    Jet = 7,
    InsectFlapper = 8,
    MorphingWing = 9,
    CargoUAV = 10,
    Tailsitter = 11,
    FlyingWing = 12,
    RocketSpacecraft = 13,
    Airliner = 14,
};

enum class ViewportLayout {
    Single3D = 0,
    Ortho4View = 1,
};

enum class ShadingMode {
    ShadedEdges = 0,
    ShadedOnly = 1,
    Wireframe = 2,
    SurfaceCp = 3,
    StressVonMises = 4,
};

enum class SketchShapeKind {
    RoundedPlate = 0,
    RingDuct = 1,
    AirfoilSection = 2,
    HexMount = 3,
    CustomPropeller = 4,
    CustomBodyShell = 5,
    FreeformBrep = 6,
};

enum class FreeformEntityKind { Line = 0, Circle = 1, Arc = 2, Spline = 3 };
enum class FreeformConstraintKind {
    Horizontal = 0,
    Vertical = 1,
    Length = 2,
    Radius = 3,
    Fixed = 4,
    Coincident = 5,
    Perpendicular = 6,
    Parallel = 7,
    Tangent = 8,
    Equal = 9,
    Distance = 10,
};
enum class FreeformOpKind {
    ExtrudeBoss = 0,
    ExtrudeCut = 1,
    Revolve = 2,
    Loft = 3,
    Fillet = 4,
    Chamfer = 5,
    Shell = 6,
};

struct FreeformSketchEntity {
    std::string id;
    FreeformEntityKind kind = FreeformEntityKind::Line;
    bool construction = false;
    bool closed = true;
    float x0 = 0.0f, y0 = 0.0f;
    float x1 = 0.06f, y1 = 0.0f;
    float radius = 0.015f;
    float start_deg = 0.0f, end_deg = 180.0f;
    std::vector<std::array<float, 2>> spline_pts;
};

struct FreeformSketchConstraint {
    FreeformConstraintKind kind = FreeformConstraintKind::Length;
    std::string a;
    std::string b;
    int pt_a = 0;
    int pt_b = 0;
    float value = 0.05f;
    float target_x = 0.0f, target_y = 0.0f;
};

struct WorkplaneSpec {
    std::string preset = "XY";
    int picked_face_id = -1;
    std::array<float, 3> origin_m{0.0f, 0.0f, 0.0f};
    std::array<float, 3> normal{0.0f, 0.0f, 1.0f};
    std::array<float, 3> u_axis{1.0f, 0.0f, 0.0f};
    std::array<float, 3> v_axis{0.0f, 1.0f, 0.0f};
};

struct FreeformSketchState {
    std::vector<FreeformSketchEntity> entities;
    std::vector<FreeformSketchConstraint> constraints;
    WorkplaneSpec workplane{};
    int dof = 0;
    bool converged = true;
    double max_residual = 0.0;
};

struct FreeformCadFeature {
    FreeformOpKind op = FreeformOpKind::ExtrudeBoss;
    bool suppressed = false;
    bool symmetric = false;
    float depth_m = 0.030f;
    float angle_deg = 360.0f;
    float radius_m = 0.002f;
    float loft_offset_m = 0.060f;
    float loft_scale = 0.55f;
    std::vector<int> target_indices;
    FreeformSketchState sketch{};
};

struct InsertedLibraryPart {
    std::string instance_id;
    std::string catalog_id;
    std::string name;
    std::string category;
    lab::StandardPartShape shape = lab::StandardPartShape::MotorCan;
    double mass_kg = 0.01;
    float od_mm = 20.0f;
    float id_mm = 5.0f;
    float length_mm = 20.0f;
    float width_mm = 20.0f;
    float height_mm = 10.0f;
    int blades = 2;
    float pitch_deg = 15.0f;
    std::array<float, 3> pos_m{0.0f, 0.0f, 0.0f};
    std::array<float, 3> rot_deg{0.0f, 0.0f, 0.0f};
    std::string attached_body_id = "chassis";
    std::string provenance = "UNVERIFIED_ESTIMATE";
};

struct CustomPartParams {
    std::string part_name = "Custom Motor Arm";
    SketchShapeKind sketch_kind = SketchShapeKind::RoundedPlate;
    float width_m = 0.048f;
    float length_m = 0.240f;
    float thickness_m = 0.012f;
    float hole_radius_m = 0.008f;
    bool revolve_360 = false;
    int circular_pattern_count = 1;
    std::string material_name = "Carbon Fiber CFRP";
    float density_kg_m3 = 1580.0f;
    bool freeform_mode = false;
    int picked_face_id = -1;
    WorkplaneSpec active_workplane{};
    FreeformSketchState freeform_sketch{};
    std::vector<FreeformCadFeature> freeform_features{};
};

struct AircraftDesignParams {
    std::string project_name = "Quad MN3508 Baseline";
    VehicleFamily family = VehicleFamily::Multirotor;

    // Multirotor / Rotor / VTOL frame
    int rotor_count = 4;
    float arm_length_m = 0.300f;
    float frame_width_m = 0.145f;
    float hub_height_m = 0.048f;
    float prop_diameter_m = 0.381f; // 15 in
    float prop_pitch_deg = 16.0f;
    int prop_blades = 2;
    float vtol_tilt_deg = 0.0f; // 0 = hover, 90 = cruise

    // Fixed-wing / Tail / Fuselage
    float wingspan_m = 1.65f;
    float root_chord_m = 0.28f;
    float tip_chord_m = 0.16f;
    float sweep_deg = 12.0f;
    float dihedral_deg = 4.5f;
    float twist_tip_deg = -2.5f;
    std::string airfoil_code = "2412";
    float fuselage_length_m = 1.12f;
    float fuselage_radius_m = 0.085f;

    // Helicopter main + tail rotor
    float main_rotor_diameter_m = 1.48f;
    float tail_boom_length_m = 0.88f;

    // Propulsion / Electronics / Stress / Weather state
    float battery_mass_kg = 1.55f;
    float payload_mass_kg = 0.35f;
    float frame_mass_kg = 1.20f;
    float motor_mass_kg = 0.103f;
    float battery_capacity_ah = 10.0f;
    float battery_r0_ohm = 0.025f;
    int battery_cells_s = 6;
    float rotor_rpm = 4800.0f;
    float alpha_deg = 5.5f;
    float airspeed_m_s = 18.0f;
    float rain_mm_h = 0.0f;
    float oat_c = 25.0f;
    float altitude_asl_m = 0.0f;
    float wind_x_m_s = 0.0f;
    float wind_y_m_s = 0.0f;
    float turbulence_pct = 10.0f;     // Gust / chaotic wind margin [0..50 %]
    float mfg_tolerance_pct = 5.0f;   // Manufacturing tolerance / defect margin [0..25 %]
    int motor_cooling_grade = 1;      // 0=Poor, 1=Medium, 2=Good (eCalc style)

    // Preloaded hardware catalog selector (designers invent airframe/wings/props/hulls, not motors/batteries/turbines)
    int hardware_catalog_idx = 0;     // 0=MN3508+6S, 1=ECOII+4S, 2=70mmEDF+6S, 3=MicroCoreless+1S, 4=KingTechK45, 5=JetCatP100

    // Seaplane / Hydrodynamics
    float float_beam_m = 0.14f;
    float float_deadrise_deg = 18.0f;
    float water_chop_m = 0.04f;

    // Jets / Compressible High-Speed & Coupled Cycle
    float jet_throttle_pct = 85.0f;
    float wing_tc_ratio = 0.09f;
    float intake_area_m2 = 0.0032f;
    float nozzle_area_ratio = 1.15f;
    float fuel_mass_kg = 0.85f;

    // Cargo Package Carrier & Creator Archetypes (Jays_rcgarage / dRehmFlight / Project-Air)
    float cargo_mass_kg = 1.80f;
    float cable_length_m = 1.20f;
    bool payload_released = false;
    float transition_pitch_deg = 70.0f;
    float duct_area_ratio = 1.0f;

    // Standards BOM: ISO 4762 Fasteners (0=M2, 1=M2.5, 2=M3, 3=M4, 4=M5, 5=M6) & AWG Wire
    int screw_size_idx = 2;
    bool titanium_screws = false;
    int wire_awg = 12;

    // Virtual Dual-Stick + USB HID RC Controller & Live Visual Motion / CAD Kinematics
    bool show_rc_hud = false;
    bool use_usb_joystick = false;
    float rc_throttle = 0.65f;
    float rc_yaw = 0.0f;
    float rc_pitch = 0.0f;
    float rc_roll = 0.0f;
    float spin_phase_rad = 0.0f;
    float explode_factor = 0.0f;
    bool motion_study_active = false;
    float motion_study_time_s = 0.0f;
    bool show_streamlines = true;

    // Multiphysics: RF Telemetry, Stealth RCS & Helicopter VRS Descent
    float rf_distance_km = 2.5f;
    bool stealth_shaping = false;
    float heli_descent_m_s = 0.0f;

    // Phase 4: Multi-Stage Rockets, Orbital & Hypersonic Re-entry
    float rocket_stage1_prop_kg = 18500.0f;
    float rocket_stage2_prop_kg = 4200.0f;
    float rocket_isp1_s = 295.0f;
    float rocket_thrust_kn = 340.0f;
    float rocket_nose_radius_m = 0.85f;
    float reentry_speed_km_s = 7.65f;
    float reentry_alt_km = 68.0f;
    bool jet_afterburner = false;
    bool jet_ramjet = false;
    bool rocket_saturn_v_preset = false;

    // Tiny Insect-Sized Flapping & Morphing MAV (Uncrewed)
    float flap_freq_hz = 40.0f;
    float stroke_amp_deg = 78.0f;
    float morph_tuck_pct = 0.0f;
    float wing_asymmetry_diff = 0.0f;
    float tail_spread_pct = 70.0f;
    float tail_tilt_deg = 5.0f;
    bool animate_flapping = false;
    float flap_anim_phase_rad = 0.0f;

    // Editable Part Studio feature
    CustomPartParams active_part{};
    bool attach_custom_part = false;

    // Standard Part & Propulsion Library + Full Multi-Body Mechanical Mates
    std::vector<InsertedLibraryPart> inserted_parts{};
    std::vector<lab::RigidBodyNode> mate_bodies{};
    std::vector<lab::MechanicalMateSpec> mechanical_mates{};
    bool show_mate_gizmos = false;
    bool animate_mates = false;
    float mate_anim_time_s = 0.0f;
    std::string active_propulsion_part_id = "motor_mn3508_kv380";
    std::string active_battery_part_id = "bat_6s_10000_hv";
};

struct FeatureNode {
    std::string id;
    std::string label;
    std::string kind; // "Sketch", "Extrude", "Revolve", "WingLoft", "RotorArray", "PartSwap", "Fuselage"
    bool suppressed = false;
};

struct AssemblyPartSummary {
    std::string name;
    std::string category;
    double mass_kg = 0.0;
    std::array<double, 3> position_m{0.0, 0.0, 0.0};
    bool is_custom_part = false;
};

struct MeshVertex {
    float px, py, pz;
    float nx, ny, nz;
    float r, g, b;
    float cp; // normalized pressure coefficient scalar [-1.5 .. 1.0]
};

struct EdgeVertex {
    float px, py, pz;
    float r, g, b;
};

struct BrepFaceMeta {
    int face_id = 0;
    std::string kind = "plane";
    double area_m2 = 0.0;
    std::array<float, 3> center_m{0.0f, 0.0f, 0.0f};
    std::array<float, 3> normal{0.0f, 0.0f, 1.0f};
    std::array<float, 3> u_axis{1.0f, 0.0f, 0.0f};
    std::array<float, 3> v_axis{0.0f, 1.0f, 0.0f};
};

struct FreeformBrepCache {
    bool has_occt_mesh = false;
    bool occt_exact_brep = false;
    std::vector<MeshVertex> vertices;
    std::vector<std::uint32_t> indices;
    std::vector<int> tri_face_ids;
    std::vector<EdgeVertex> edges;
    std::vector<BrepFaceMeta> faces;
    double volume_m3 = 0.0;
    double mass_kg = 0.0;
    std::array<double, 3> cog_m{0.0, 0.0, 0.0};
    std::string status_summary = "No OCCT B-rep build yet";
};

struct EmbeddedCfdFeaCache {
    bool has_field = false;
    int n_fluid_cells = 0;
    int n_boundary_cut_cells = 0;
    int n_solid_elems = 0;
    double integrated_cl = 0.0;
    double integrated_cd = 0.0;
    double peak_suction_cp = 0.0;
    double peak_vm_mpa = 0.0;
    double max_disp_mm = 0.0;
    double structural_fos = 5.0;
    std::vector<float> panel_cp;
    std::vector<float> panel_vm_mpa;
    std::vector<std::vector<std::array<float, 3>>> streamlines_3d;
    std::string status_summary = "Analytical proxy (click Run 3D CFD/FEA)";
};

struct GeneratedCADScene {
    std::vector<MeshVertex> vertices;
    std::vector<std::uint32_t> indices;
    std::vector<int> tri_face_ids;
    std::vector<EdgeVertex> cad_edges;
    std::vector<EdgeVertex> wake_lines;
    std::vector<EdgeVertex> path_lines;
    std::vector<AssemblyPartSummary> assembly_parts;
    double custom_part_volume_m3 = 0.0;
    double custom_part_mass_kg = 0.0;
    double reference_area_m2 = 0.0;
    double aspect_ratio = 0.0;
    lab::MechanicalMatesSolution latest_mates_solution{};
};

struct CameraOrbitState {
    float yaw_deg = 42.0f;
    float pitch_deg = 28.0f;
    float distance_m = 1.85f;
    std::array<float, 3> target_m{0.0f, 0.0f, 0.05f};
};

struct LiveEvidenceSummary {
    double total_mass_kg = 0.0;
    std::array<double, 3> center_of_mass_m{0.0, 0.0, 0.0};
    bool clearance_ok = true;
    double min_tip_clearance_m = 0.0;

    // Aero, Electronics & Stress KPIs
    double lift_n = 0.0;
    double drag_n = 0.0;
    double cl = 0.0;
    double cd = 0.0;
    double lift_to_drag = 0.0;
    double reynolds = 0.0;
    double mach = 0.0;
    double hover_or_cruise_current_a = 18.0;
    double loaded_bus_voltage_v = 24.7;
    double cutoff_voltage_v = 19.2;
    double est_endurance_min = 24.0;
    double rotor_tip_mach = 0.28;
    double thrust_to_weight = 2.0;
    double hover_throttle_pct = 44.0;
    double structural_fos = 3.2;
    double fem_peak_vm_mpa = 0.0;
    double fem_max_disp_mm = 0.0;
    int cfd_fluid_cells = 0;
    int fem_solid_elems = 0;
    bool cfd_fea_solved = false;
    int library_parts_count = 0;
    double library_parts_mass_kg = 0.0;
    int mates_active_count = 0;
    int mates_free_dof = 0;
    double mates_min_fos = 5.0;
    double mates_min_clearance_mm = 999.0;
    bool mates_limit_violated = false;
    bool mates_interference = false;
    std::string mates_summary = "Mates ready";
    double air_density_kg_m3 = 1.225;
    double wind_speed_m_s = 0.0;
    double motor_temp_c = 38.0;
    double m_dd = 0.0;
    double cd_wave = 0.0;
    double hump_resistance_n = 0.0;
    double strouhal = 0.0;
    double theodorsen_ck = 1.0;
    double wagner_phi = 1.0;
    double flex_tip_deflection_mm = 0.0;
    double first_bending_mode_hz = 0.0;
    double fatigue_stress_ratio = 0.0;
    double divergence_margin = 10.0;
    double yaw_damping_cn = 0.0;
    double roll_moment_nm = 0.0;
    double wing_flex_tip_m = 0.0;
    double inlet_recovery_eta = 0.985;
    double mach_cone_deg = 90.0;
    double trail_angle_deg = 0.0;
    double pendulum_hz = 0.0;
    double propwash_slip_m_s = 0.0;
    double bolt_shear_fos = 4.5;
    double wire_drop_v = 0.12;
    double wire_ampacity_a = 65.0;
    bool bolt_ok = true;
    bool wire_ok = true;
    double spl_dba = 68.0;
    double bpf_hz = 160.0;
    double sonic_boom_psf = 0.0;
    double heli_mu = 0.0;
    double heli_gyro_nm = 0.0;
    bool heli_vrs = false;
    double cavitation_sigma = 2.0;
    double rf_margin_db = 22.0;
    double rcs_dbsm = -12.0;
    double rocket_dv_m_s = 0.0;
    double rocket_tps_c = 0.0;
    double rocket_kn = 0.0;
    bool rocket_orbit_ok = false;
    double skin_temp_c = 25.0;
    double cabin_delta_p_kpa = 0.0;
    double hoop_fos = 5.0;
    double predicted_readiness_pct = 92.5;
    double benchmark_match_pct = 94.2; // < 0 means N/A (custom unmeasured geometry)
    std::string benchmark_source_tag = "Pinned UIUC + SIT + QDrone Ref (DEVELOPMENT)";
    std::string validation_status = "DEVELOPMENT"; // DEVELOPMENT | PHYSICAL_PENDING | UNVALIDATED_CUSTOM | FAIL
    std::string status_detail = "C++20 lab_core mass/CoG & Prandtl/BEMT analytical check active";

    // Cached 6-DoF RK4 trajectory
    bool has_trajectory = false;
    bool playing = false;
    float playback_time_s = 0.0f;
    float duration_s = 2.0f;
    double max_altitude_m = 0.0;
    double min_bus_voltage_v = 25.2;
    std::vector<double> traj_t_s;
    std::vector<std::array<double, 3>> traj_pos_m;
    std::vector<std::array<double, 4>> traj_quat_wxyz;

    // Curve samples for polar & rocket ascent charts
    std::vector<float> curve_alpha_deg;
    std::vector<float> curve_cl;
    std::vector<float> curve_cd;
    std::vector<float> rocket_traj_t_s;
    std::vector<float> rocket_traj_alt_km;
    std::vector<float> rocket_traj_q_kpa;
};

} // namespace aerolab
