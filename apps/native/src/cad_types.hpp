#pragma once

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
};

enum class SketchShapeKind {
    RoundedPlate = 0,
    RingDuct = 1,
    AirfoilSection = 2,
    HexMount = 3,
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
    float wind_x_m_s = 0.0f;
    float wind_y_m_s = 0.0f;

    // Editable Part Studio feature
    CustomPartParams active_part{};
    bool attach_custom_part = false;
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

struct GeneratedCADScene {
    std::vector<MeshVertex> vertices;
    std::vector<std::uint32_t> indices;
    std::vector<EdgeVertex> cad_edges;
    std::vector<EdgeVertex> wake_lines;
    std::vector<EdgeVertex> path_lines;
    std::vector<AssemblyPartSummary> assembly_parts;
    double custom_part_volume_m3 = 0.0;
    double custom_part_mass_kg = 0.0;
    double reference_area_m2 = 0.0;
    double aspect_ratio = 0.0;
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
    double structural_fos = 3.2;
    double motor_temp_c = 38.0;
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

    // Curve samples for polar chart
    std::vector<float> curve_alpha_deg;
    std::vector<float> curve_cl;
    std::vector<float> curve_cd;
};

} // namespace aerolab
