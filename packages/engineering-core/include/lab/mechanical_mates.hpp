#pragma once

#include <array>
#include <string>
#include <utility>
#include <vector>

namespace lab {

enum class MateKind {
    Rigid = 0,
    Revolute = 1,
    Prismatic = 2,
    Cylindrical = 3,
    Spherical = 4,
    Gear = 5,
    RackPinion = 6,
    Planar = 7,
};

struct RigidBodyNode {
    std::string id;
    std::string name;
    double mass_kg = 0.25;
    std::array<double, 3> half_extents_m{0.05, 0.05, 0.02};
    bool grounded = false;
    bool collision_enabled = true;
};

struct MechanicalMateSpec {
    std::string id;
    MateKind kind = MateKind::Revolute;
    std::string parent_body;
    std::string child_body;
    std::array<double, 3> anchor_parent_m{0.0, 0.0, 0.0};
    std::array<double, 3> anchor_child_m{0.0, 0.0, 0.0};
    std::array<double, 3> axis_local{0.0, 0.0, 1.0};
    double drive_value = 0.0;      // deg for Revolute/Spherical/Gear; m for Prismatic/Cylindrical/Planar
    double secondary_value = 0.0;  // deg spin for Cylindrical; roll deg for Spherical; Y slide m for Planar
    double limit_min = -180.0;
    double limit_max = 180.0;
    bool enforce_limits = true;
    double gear_ratio = 1.0;       // Child / Parent ratio for Gear
    double pitch_radius_m = 0.02;  // Linear travel per radian for RackPinion
    std::string coupled_mate_id;   // Driver mate id for Gear / RackPinion
    double load_capacity_n = 475.0;
    bool suppressed = false;
};

struct ClosedLoopTarget {
    std::string tip_body_id;
    std::array<double, 3> tip_local_offset_m{0.0, 0.0, 0.0};
    std::array<double, 3> target_world_m{0.0, 0.0, 0.0};
    std::string driver_mate_id;
    bool active = false;
};

struct SolvedBodyPose {
    std::string body_id;
    std::array<double, 3> world_pos_m{0.0, 0.0, 0.0};
    std::array<double, 4> quat_wxyz{1.0, 0.0, 0.0, 0.0}; // Active Hamilton wxyz
    bool visited = false;
};

struct SolvedMateState {
    std::string mate_id;
    MateKind kind = MateKind::Rigid;
    double effective_drive = 0.0;
    double effective_secondary = 0.0;
    bool limit_violated = false;
    double reaction_force_n = 0.0;
    double reaction_torque_nm = 0.0;
    double joint_fos = 5.0;
    int free_dof = 0;
    std::array<double, 3> joint_world_pos_m{0.0, 0.0, 0.0};
    std::array<double, 3> joint_world_axis{0.0, 0.0, 1.0};
};

struct MechanicalMatesSolution {
    bool valid = false;
    int total_free_dof = 0;
    int active_mates = 0;
    double max_loop_error_mm = 0.0;
    double min_clearance_mm = 999.0;
    bool any_limit_violated = false;
    bool any_interference = false;
    std::vector<SolvedBodyPose> body_poses;
    std::vector<SolvedMateState> mate_states;
    std::vector<std::pair<std::string, std::string>> interference_pairs;
    std::string summary;
};

MechanicalMatesSolution solve_mechanical_mates(
    const std::vector<RigidBodyNode> &bodies,
    const std::vector<MechanicalMateSpec> &mates,
    bool animate = false,
    double anim_time_s = 0.0,
    double external_load_scale = 1.0,
    const ClosedLoopTarget *loop_closure = nullptr);

const char *mate_kind_name(MateKind kind);

} // namespace lab
