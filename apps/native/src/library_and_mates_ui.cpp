#include "library_and_mates_ui.hpp"

#include "imgui.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <sstream>

namespace aerolab {
namespace {

const char *shape_str(lab::StandardPartShape s) {
    switch (s) {
    case lab::StandardPartShape::MotorCan: return "motor_can";
    case lab::StandardPartShape::Turbine: return "turbine";
    case lab::StandardPartShape::Propeller: return "propeller";
    case lab::StandardPartShape::BatteryBox: return "battery_box";
    case lab::StandardPartShape::PcbModule: return "pcb_module";
    case lab::StandardPartShape::FastenerBolt: return "fastener_bolt";
    case lab::StandardPartShape::BallBearing: return "ball_bearing";
    case lab::StandardPartShape::StructuralTube: return "structural_tube";
    case lab::StandardPartShape::ServoBlock: return "servo_block";
    }
    return "motor_can";
}

lab::StandardPartShape parse_shape_str(const std::string &s) {
    if (s == "turbine") return lab::StandardPartShape::Turbine;
    if (s == "propeller") return lab::StandardPartShape::Propeller;
    if (s == "battery_box") return lab::StandardPartShape::BatteryBox;
    if (s == "pcb_module") return lab::StandardPartShape::PcbModule;
    if (s == "fastener_bolt") return lab::StandardPartShape::FastenerBolt;
    if (s == "ball_bearing") return lab::StandardPartShape::BallBearing;
    if (s == "structural_tube") return lab::StandardPartShape::StructuralTube;
    if (s == "servo_block") return lab::StandardPartShape::ServoBlock;
    return lab::StandardPartShape::MotorCan;
}

const char *mate_kind_str(lab::MateKind k) {
    switch (k) {
    case lab::MateKind::Rigid: return "rigid";
    case lab::MateKind::Revolute: return "revolute";
    case lab::MateKind::Prismatic: return "prismatic";
    case lab::MateKind::Cylindrical: return "cylindrical";
    case lab::MateKind::Spherical: return "spherical";
    case lab::MateKind::Gear: return "gear";
    case lab::MateKind::RackPinion: return "rack_pinion";
    case lab::MateKind::Planar: return "planar";
    }
    return "revolute";
}

lab::MateKind parse_mate_kind_str(const std::string &s) {
    if (s == "rigid") return lab::MateKind::Rigid;
    if (s == "prismatic") return lab::MateKind::Prismatic;
    if (s == "cylindrical") return lab::MateKind::Cylindrical;
    if (s == "spherical") return lab::MateKind::Spherical;
    if (s == "gear") return lab::MateKind::Gear;
    if (s == "rack_pinion") return lab::MateKind::RackPinion;
    if (s == "planar") return lab::MateKind::Planar;
    return lab::MateKind::Revolute;
}

std::string find_arr(const std::string &txt, const std::string &key) {
    const auto kp = txt.find("\"" + key + "\"");
    if (kp == std::string::npos) return {};
    const auto lb = txt.find('[', kp);
    if (lb == std::string::npos) return {};
    int depth = 0;
    for (std::size_t i = lb; i < txt.size(); ++i) {
        if (txt[i] == '[') ++depth;
        else if (txt[i] == ']') {
            --depth;
            if (depth == 0) return txt.substr(lb, i - lb + 1);
        }
    }
    return {};
}

std::vector<std::string> split_objs(const std::string &arr) {
    std::vector<std::string> out;
    int depth = 0;
    std::size_t st = std::string::npos;
    for (std::size_t i = 0; i < arr.size(); ++i) {
        if (arr[i] == '{') {
            if (depth == 0) st = i;
            ++depth;
        } else if (arr[i] == '}') {
            --depth;
            if (depth == 0 && st != std::string::npos) {
                out.push_back(arr.substr(st, i - st + 1));
                st = std::string::npos;
            }
        }
    }
    return out;
}

std::string r_str(const std::string &obj, const char *k, const char *def = "") {
    const std::string p = std::string("\"") + k + "\"";
    const auto kp = obj.find(p);
    if (kp == std::string::npos) return def;
    const auto c = obj.find(':', kp + p.size());
    if (c == std::string::npos) return def;
    const auto q1 = obj.find('"', c + 1);
    if (q1 == std::string::npos) return def;
    const auto q2 = obj.find('"', q1 + 1);
    return (q2 != std::string::npos) ? obj.substr(q1 + 1, q2 - q1 - 1) : def;
}

double r_num(const std::string &obj, const char *k, double def) {
    const std::string p = std::string("\"") + k + "\"";
    const auto kp = obj.find(p);
    if (kp == std::string::npos) return def;
    const auto c = obj.find(':', kp + p.size());
    if (c == std::string::npos) return def;
    return std::atof(obj.c_str() + c + 1);
}

bool r_bool(const std::string &obj, const char *k, bool def) {
    const std::string p = std::string("\"") + k + "\"";
    const auto kp = obj.find(p);
    if (kp == std::string::npos) return def;
    const auto c = obj.find(':', kp + p.size());
    if (c == std::string::npos) return def;
    const auto sub = obj.substr(c + 1, 12);
    if (sub.find("true") != std::string::npos) return true;
    if (sub.find("false") != std::string::npos) return false;
    return def;
}

std::array<double, 3> r_vec3(const std::string &obj, const char *k, std::array<double, 3> def) {
    const auto arr = find_arr(obj, k);
    if (arr.empty()) return def;
    double a = def[0], b = def[1], c = def[2];
    if (std::sscanf(arr.c_str() + 1, " %lf , %lf , %lf", &a, &b, &c) == 3) {
        return {a, b, c};
    }
    return def;
}

} // namespace

void init_default_mates_for_params(AircraftDesignParams &params) {
    params.mate_bodies.clear();
    params.mechanical_mates.clear();

    if (params.family == VehicleFamily::VTOL) {
        params.mate_bodies = {
            {"chassis", "Airframe & Wing", params.frame_mass_kg, {0.20, 0.45, 0.06}, true, true},
            {"nacelle_l", "Left Tilt Nacelle", 0.35, {0.05, 0.05, 0.05}, false, true},
            {"nacelle_r", "Right Tilt Nacelle", 0.35, {0.05, 0.05, 0.05}, false, true},
            {"rotor_l", "Left Tilt Rotor", params.motor_mass_kg, {0.14, 0.03, 0.015}, false, true},
            {"rotor_r", "Right Tilt Rotor", params.motor_mass_kg, {0.14, 0.03, 0.015}, false, true},
            {"actuator_pushrod", "Tilt Servo Pushrod", 0.04, {0.03, 0.02, 0.02}, false, false},
        };
        params.mechanical_mates = {
            {"tilt_left", lab::MateKind::Revolute, "chassis", "nacelle_l", {0.15, params.wingspan_m * 0.28, 0.05}, {0, 0, 0}, {0, 1, 0}, params.vtol_tilt_deg, 0.0, 0.0, 95.0, true, 1.0, 0.02, "", 1710.0, false},
            {"tilt_right_gear", lab::MateKind::Gear, "chassis", "nacelle_r", {0.15, -params.wingspan_m * 0.28, 0.05}, {0, 0, 0}, {0, 1, 0}, 0.0, 0.0, 0.0, 95.0, true, 1.0, 0.02, "tilt_left", 1710.0, false},
            {"spin_left", lab::MateKind::Revolute, "nacelle_l", "rotor_l", {0, 0, 0.06}, {0, 0, 0}, {0, 0, 1}, 0.0, 0.0, -360.0, 360.0, false, 1.0, 0.02, "", 3350.0, false},
            {"spin_right_gear", lab::MateKind::Gear, "nacelle_r", "rotor_r", {0, 0, 0.06}, {0, 0, 0}, {0, 0, 1}, 0.0, 0.0, -360.0, 360.0, false, -1.0, 0.02, "spin_left", 3350.0, false},
            {"servo_rack", lab::MateKind::RackPinion, "chassis", "actuator_pushrod", {-0.05, 0.0, 0.02}, {0, 0, 0}, {1, 0, 0}, 0.0, 0.0, -0.05, 0.08, true, 1.0, 0.018, "tilt_left", 475.0, false},
        };
    } else if (params.family == VehicleFamily::Helicopter) {
        params.mate_bodies = {
            {"chassis", "Helicopter Fuselage", params.frame_mass_kg, {0.25, 0.12, 0.12}, true, true},
            {"main_hub", "Main Rotor Mast", 0.32, {0.10, 0.10, 0.04}, false, true},
            {"tail_rotor", "Tail Anti-Torque Hub", 0.11, {0.04, 0.04, 0.04}, false, true},
            {"swashplate", "Cyclic Swashplate", 0.09, {0.06, 0.06, 0.015}, false, false},
            {"skid_oleo", "Landing Gear Oleo", 0.22, {0.22, 0.12, 0.03}, false, true},
        };
        params.mechanical_mates = {
            {"main_mast", lab::MateKind::Revolute, "chassis", "main_hub", {0.05, 0.0, params.fuselage_radius_m * 1.8}, {0, 0, 0}, {0, 0, 1}, 0.0, 0.0, -360.0, 360.0, false, 1.0, 0.02, "", 6890.0, false},
            {"tail_bevel_gear", lab::MateKind::Gear, "chassis", "tail_rotor", {-params.tail_boom_length_m * 0.90, 0.045, 0.08}, {0, 0, 0}, {0, 1, 0}, 0.0, 0.0, -360.0, 360.0, false, -3.5, 0.02, "main_mast", 1710.0, false},
            {"swash_ball", lab::MateKind::Spherical, "chassis", "swashplate", {0.05, 0.0, params.fuselage_radius_m * 1.3}, {0, 0, 0}, {0, 0, 1}, 4.0, -2.0, -18.0, 18.0, true, 1.0, 0.02, "", 855.0, false},
            {"skid_slider", lab::MateKind::Prismatic, "chassis", "skid_oleo", {0.08, 0.0, -0.14}, {0, 0, 0}, {0, 0, 1}, 0.0, 0.0, -0.04, 0.04, true, 1.0, 0.02, "", 2080.0, false},
        };
    } else if (params.family == VehicleFamily::CargoUAV) {
        params.mate_bodies = {
            {"chassis", "Cargo Hex Airframe", params.frame_mass_kg, {0.25, 0.25, 0.06}, true, true},
            {"winch_drum", "Servo Winch Drum", 0.18, {0.04, 0.04, 0.04}, false, true},
            {"cargo_tether", "Retractable Tether", 0.06, {0.02, 0.02, 0.20}, false, false},
            {"cargo_parcel", "Slung Payload Box", params.cargo_mass_kg, {0.14, 0.14, 0.10}, false, true},
        };
        params.mechanical_mates = {
            {"winch_spin", lab::MateKind::Revolute, "chassis", "winch_drum", {0, 0, -0.08}, {0, 0, 0}, {0, 1, 0}, 0.0, 0.0, -720.0, 720.0, false, 1.0, 0.02, "", 3350.0, false},
            {"winch_rack", lab::MateKind::Prismatic, "chassis", "cargo_tether", {0, 0, -0.10}, {0, 0, 0}, {0, 0, -1}, 0.0, 0.0, -0.15, 0.45, true, 1.0, 0.03, "", 2440.0, false},
            {"slung_gimbal", lab::MateKind::Spherical, "cargo_tether", "cargo_parcel", {0, 0, -params.cable_length_m}, {0, 0, 0}, {0, 1, 0}, 6.0, 0.0, -35.0, 35.0, true, 1.0, 0.02, "", 1400.0, false},
        };
    } else if (params.family == VehicleFamily::FixedWing || params.family == VehicleFamily::FlyingWing || params.family == VehicleFamily::Jet) {
        params.mate_bodies = {
            {"chassis", "Fuselage & Wing Box", params.frame_mass_kg, {0.32, 0.12, 0.08}, true, true},
            {"aileron_l", "Left Aileron Surface", 0.08, {0.04, 0.18, 0.01}, false, true},
            {"aileron_r", "Right Aileron Surface", 0.08, {0.04, 0.18, 0.01}, false, true},
            {"elevator", "Elevator Hinge", 0.09, {0.04, 0.16, 0.01}, false, true},
            {"prop_shaft", "Spinner / Rotor Shaft", params.motor_mass_kg, {0.05, 0.05, 0.04}, false, true},
        };
        params.mechanical_mates = {
            {"hinge_ail_l", lab::MateKind::Revolute, "chassis", "aileron_l", {-0.08, params.wingspan_m * 0.30, 0.03}, {0, 0, 0}, {0, 1, 0}, 8.0, 0.0, -28.0, 28.0, true, 1.0, 0.02, "", 475.0, false},
            {"gear_ail_r", lab::MateKind::Gear, "chassis", "aileron_r", {-0.08, -params.wingspan_m * 0.30, 0.03}, {0, 0, 0}, {0, 1, 0}, 0.0, 0.0, -28.0, 28.0, true, -1.0, 0.02, "hinge_ail_l", 475.0, false},
            {"hinge_elev", lab::MateKind::Revolute, "chassis", "elevator", {-params.fuselage_length_m * 0.44, 0.0, 0.02}, {0, 0, 0}, {0, 1, 0}, -4.0, 0.0, -25.0, 25.0, true, 1.0, 0.02, "", 475.0, false},
            {"motor_bearing", lab::MateKind::Cylindrical, "chassis", "prop_shaft", {params.fuselage_length_m * 0.50, 0.0, 0.0}, {0, 0, 0}, {1, 0, 0}, 0.0, 0.0, -0.002, 0.002, true, 1.0, 0.02, "", 1710.0, false},
        };
    } else {
        // Multirotor / Morphing / Tailsitter / Custom Part baseline assembly mates
        params.mate_bodies = {
            {"chassis", "Primary Structure", std::max(0.25, static_cast<double>(params.frame_mass_kg)), {0.12, 0.12, 0.04}, true, true},
            {"rotor_1", "CW Rotor #1 Bearing", params.motor_mass_kg, {0.06, 0.06, 0.03}, false, true},
            {"rotor_2", "CCW Rotor #2 Bearing", params.motor_mass_kg, {0.06, 0.06, 0.03}, false, true},
            {"payload_rail", "Underslung Payload Rail", 0.12, {0.06, 0.04, 0.02}, false, true},
        };
        params.mechanical_mates = {
            {"spin_m1", lab::MateKind::Revolute, "chassis", "rotor_1", {params.arm_length_m * 0.707, params.arm_length_m * 0.707, 0.02}, {0, 0, 0}, {0, 0, 1}, 0.0, 0.0, -360.0, 360.0, false, 1.0, 0.02, "", 1710.0, false},
            {"spin_m2_counter", lab::MateKind::Gear, "chassis", "rotor_2", {params.arm_length_m * 0.707, -params.arm_length_m * 0.707, 0.02}, {0, 0, 0}, {0, 0, 1}, 0.0, 0.0, -360.0, 360.0, false, -1.0, 0.02, "spin_m1", 1710.0, false},
            {"rail_slide", lab::MateKind::Prismatic, "chassis", "payload_rail", {0.0, 0.0, -0.04}, {0, 0, 0}, {1, 0, 0}, 0.0, 0.0, -0.06, 0.06, true, 1.0, 0.02, "", 475.0, false},
        };
    }
}

void apply_library_item_to_params(const lab::StandardPartSpec &item, AircraftDesignParams &params, std::string &banner) {
    if (item.category == "Motors") {
        params.active_propulsion_part_id = item.id;
        params.motor_mass_kg = static_cast<float>(item.mass_kg);
        if (item.voltage_s > 0) params.battery_cells_s = item.voltage_s;
        if (item.id.find("p80") != std::string::npos || item.id.find("u8ii") != std::string::npos || item.id.find("x11") != std::string::npos) {
            params.hardware_catalog_idx = 0;
        } else if (item.id.find("coreless") != std::string::npos || item.id.find("1103") != std::string::npos) {
            params.hardware_catalog_idx = 3;
        } else {
            params.hardware_catalog_idx = (item.voltage_s >= 6) ? 0 : 1;
        }
    } else if (item.category == "Turbines & EDFs") {
        params.active_propulsion_part_id = item.id;
        params.motor_mass_kg = static_cast<float>(item.mass_kg);
        if (item.id == "turbine_kingtech_k45g4") params.hardware_catalog_idx = 4;
        else if (item.id == "turbine_jetcat_p100rx" || item.id == "turbine_jetcat_p220rxi") params.hardware_catalog_idx = 5;
        else params.hardware_catalog_idx = 2;
    } else if (item.category == "Propellers") {
        params.prop_diameter_m = static_cast<float>(item.od_mm / 1000.0);
        params.prop_pitch_deg = static_cast<float>(item.pitch_deg);
        params.prop_blades = std::max(2, item.blades);
    } else if (item.category == "Batteries & Tanks") {
        params.active_battery_part_id = item.id;
        params.battery_mass_kg = static_cast<float>(item.mass_kg);
        params.battery_cells_s = std::max(1, item.voltage_s);
        params.battery_capacity_ah = static_cast<float>(item.capacity_ah);
        params.battery_r0_ohm = static_cast<float>(item.r0_ohm);
    } else if (item.category == "Fasteners" && item.screw_size_idx >= 0) {
        params.screw_size_idx = std::clamp(item.screw_size_idx, 0, 5);
        params.titanium_screws = (item.id.find("_ti") != std::string::npos);
    }
    banner = "Applied library spec: " + item.name + " [" + item.provenance + "]";
}

void insert_library_item_into_scene(const lab::StandardPartSpec &item, AircraftDesignParams &params,
                                    const std::array<float, 3> &pos_m, const std::string &parent_body) {
    InsertedLibraryPart p;
    p.instance_id = "lib_" + std::to_string(params.inserted_parts.size() + 1) + "_" + item.id;
    p.catalog_id = item.id;
    p.name = item.name;
    p.category = item.category;
    p.shape = item.shape;
    p.mass_kg = item.mass_kg;
    p.od_mm = static_cast<float>(item.od_mm);
    p.id_mm = static_cast<float>(item.id_mm);
    p.length_mm = static_cast<float>(item.length_mm);
    p.width_mm = static_cast<float>(item.width_mm);
    p.height_mm = static_cast<float>(item.height_mm);
    p.blades = item.blades;
    p.pitch_deg = static_cast<float>(item.pitch_deg);
    p.pos_m = pos_m;
    p.attached_body_id = parent_body.empty() ? "chassis" : parent_body;
    p.provenance = item.provenance;
    params.inserted_parts.push_back(p);

    // Register corresponding rigid body + mate into multi-body mechanism graph cleanly
    const std::string body_id = p.instance_id;
    lab::RigidBodyNode bn;
    bn.id = body_id;
    bn.name = item.name;
    bn.mass_kg = std::max(0.0005, item.mass_kg);
    bn.half_extents_m = {
        std::max(0.008, p.length_mm * 0.0005),
        std::max(0.008, p.width_mm * 0.0005),
        std::max(0.008, p.height_mm * 0.0005),
    };
    bn.grounded = false;
    bn.collision_enabled = true;
    params.mate_bodies.push_back(bn);

    lab::MechanicalMateSpec jm;
    jm.id = "mate_" + body_id;
    jm.parent_body = p.attached_body_id;
    jm.child_body = body_id;
    jm.anchor_parent_m = {pos_m[0], pos_m[1], pos_m[2]};
    jm.anchor_child_m = {0.0, 0.0, 0.0};
    jm.axis_local = {0.0, 0.0, 1.0};
    jm.load_capacity_n = (item.dynamic_load_cr_n > 0.0) ? item.dynamic_load_cr_n
                                                       : ((item.shear_capacity_n > 0.0) ? item.shear_capacity_n : 850.0);
    if (item.shape == lab::StandardPartShape::BallBearing || item.shape == lab::StandardPartShape::Propeller ||
        item.shape == lab::StandardPartShape::MotorCan || item.shape == lab::StandardPartShape::ServoBlock) {
        jm.kind = lab::MateKind::Revolute;
        jm.limit_min = -180.0;
        jm.limit_max = 180.0;
        jm.enforce_limits = false;
    } else if (item.id.find("lm8uu") != std::string::npos) {
        jm.kind = lab::MateKind::Prismatic;
        jm.limit_min = -0.05;
        jm.limit_max = 0.05;
    } else {
        jm.kind = lab::MateKind::Rigid;
    }
    params.mechanical_mates.push_back(jm);
}

std::string serialize_library_and_mates_json(const AircraftDesignParams &params) {
    std::ostringstream oss;
    oss << "{\n"
        << "  \"active_propulsion_part_id\": \"" << params.active_propulsion_part_id << "\",\n"
        << "  \"active_battery_part_id\": \"" << params.active_battery_part_id << "\",\n"
        << "  \"show_mate_gizmos\": " << (params.show_mate_gizmos ? "true" : "false") << ",\n"
        << "  \"animate_mates\": " << (params.animate_mates ? "true" : "false") << ",\n"
        << "  \"inserted_parts\": [\n";
    for (std::size_t i = 0; i < params.inserted_parts.size(); ++i) {
        const auto &p = params.inserted_parts[i];
        oss << "    {\"instance_id\": \"" << p.instance_id << "\", \"catalog_id\": \"" << p.catalog_id
            << "\", \"name\": \"" << p.name << "\", \"category\": \"" << p.category
            << "\", \"shape\": \"" << shape_str(p.shape) << "\", \"mass_kg\": " << p.mass_kg
            << ", \"od_mm\": " << p.od_mm << ", \"id_mm\": " << p.id_mm
            << ", \"length_mm\": " << p.length_mm << ", \"width_mm\": " << p.width_mm << ", \"height_mm\": " << p.height_mm
            << ", \"blades\": " << p.blades << ", \"pitch_deg\": " << p.pitch_deg
            << ", \"pos_m\": [" << p.pos_m[0] << ", " << p.pos_m[1] << ", " << p.pos_m[2] << "]"
            << ", \"attached_body_id\": \"" << p.attached_body_id << "\""
            << ", \"provenance\": \"" << p.provenance << "\"}"
            << (i + 1 < params.inserted_parts.size() ? "," : "") << "\n";
    }
    oss << "  ],\n  \"mate_bodies\": [\n";
    for (std::size_t i = 0; i < params.mate_bodies.size(); ++i) {
        const auto &b = params.mate_bodies[i];
        oss << "    {\"id\": \"" << b.id << "\", \"name\": \"" << b.name << "\", \"mass_kg\": " << b.mass_kg
            << ", \"half_extents_m\": [" << b.half_extents_m[0] << ", " << b.half_extents_m[1] << ", " << b.half_extents_m[2] << "]"
            << ", \"grounded\": " << (b.grounded ? "true" : "false")
            << ", \"collision_enabled\": " << (b.collision_enabled ? "true" : "false") << "}"
            << (i + 1 < params.mate_bodies.size() ? "," : "") << "\n";
    }
    oss << "  ],\n  \"mechanical_mates\": [\n";
    for (std::size_t i = 0; i < params.mechanical_mates.size(); ++i) {
        const auto &m = params.mechanical_mates[i];
        oss << "    {\"id\": \"" << m.id << "\", \"kind\": \"" << mate_kind_str(m.kind)
            << "\", \"parent_body\": \"" << m.parent_body << "\", \"child_body\": \"" << m.child_body
            << "\", \"anchor_parent_m\": [" << m.anchor_parent_m[0] << ", " << m.anchor_parent_m[1] << ", " << m.anchor_parent_m[2] << "]"
            << ", \"axis_local\": [" << m.axis_local[0] << ", " << m.axis_local[1] << ", " << m.axis_local[2] << "]"
            << ", \"drive_value\": " << m.drive_value << ", \"secondary_value\": " << m.secondary_value
            << ", \"limit_min\": " << m.limit_min << ", \"limit_max\": " << m.limit_max
            << ", \"enforce_limits\": " << (m.enforce_limits ? "true" : "false")
            << ", \"gear_ratio\": " << m.gear_ratio << ", \"pitch_radius_m\": " << m.pitch_radius_m
            << ", \"coupled_mate_id\": \"" << m.coupled_mate_id << "\", \"load_capacity_n\": " << m.load_capacity_n
            << ", \"suppressed\": " << (m.suppressed ? "true" : "false") << "}"
            << (i + 1 < params.mechanical_mates.size() ? "," : "") << "\n";
    }
    oss << "  ]\n}";
    return oss.str();
}

void deserialize_library_and_mates_json(const std::string &json_text, AircraftDesignParams &params) {
    if (json_text.find("\"library_mates_payload\"") == std::string::npos &&
        json_text.find("\"mechanical_mates\"") == std::string::npos) {
        return;
    }
    if (const auto pid = r_str(json_text, "active_propulsion_part_id", ""); !pid.empty()) params.active_propulsion_part_id = pid;
    if (const auto bid = r_str(json_text, "active_battery_part_id", ""); !bid.empty()) params.active_battery_part_id = bid;
    params.show_mate_gizmos = r_bool(json_text, "show_mate_gizmos", params.show_mate_gizmos);
    params.animate_mates = r_bool(json_text, "animate_mates", params.animate_mates);

    const std::string p_arr = find_arr(json_text, "inserted_parts");
    if (!p_arr.empty()) {
        params.inserted_parts.clear();
        for (const auto &po : split_objs(p_arr)) {
            InsertedLibraryPart p;
            p.instance_id = r_str(po, "instance_id", "lib_1");
            p.catalog_id = r_str(po, "catalog_id", "");
            p.name = r_str(po, "name", "Standard Part");
            p.category = r_str(po, "category", "Motors");
            p.shape = parse_shape_str(r_str(po, "shape", "motor_can"));
            p.mass_kg = r_num(po, "mass_kg", 0.05);
            p.od_mm = static_cast<float>(r_num(po, "od_mm", 20.0));
            p.id_mm = static_cast<float>(r_num(po, "id_mm", 5.0));
            p.length_mm = static_cast<float>(r_num(po, "length_mm", 20.0));
            p.width_mm = static_cast<float>(r_num(po, "width_mm", 20.0));
            p.height_mm = static_cast<float>(r_num(po, "height_mm", 10.0));
            p.blades = static_cast<int>(r_num(po, "blades", 2.0));
            p.pitch_deg = static_cast<float>(r_num(po, "pitch_deg", 15.0));
            const auto pm = r_vec3(po, "pos_m", {0, 0, 0});
            p.pos_m = {static_cast<float>(pm[0]), static_cast<float>(pm[1]), static_cast<float>(pm[2])};
            p.attached_body_id = r_str(po, "attached_body_id", "chassis");
            p.provenance = r_str(po, "provenance", "UNVERIFIED_ESTIMATE");
            params.inserted_parts.push_back(std::move(p));
        }
    }

    const std::string b_arr = find_arr(json_text, "mate_bodies");
    if (!b_arr.empty()) {
        params.mate_bodies.clear();
        for (const auto &bo : split_objs(b_arr)) {
            lab::RigidBodyNode bn;
            bn.id = r_str(bo, "id", "chassis");
            bn.name = r_str(bo, "name", bn.id.c_str());
            bn.mass_kg = r_num(bo, "mass_kg", 0.25);
            bn.half_extents_m = r_vec3(bo, "half_extents_m", {0.05, 0.05, 0.02});
            bn.grounded = r_bool(bo, "grounded", false);
            bn.collision_enabled = r_bool(bo, "collision_enabled", true);
            params.mate_bodies.push_back(std::move(bn));
        }
    }

    const std::string m_arr = find_arr(json_text, "mechanical_mates");
    if (!m_arr.empty()) {
        params.mechanical_mates.clear();
        for (const auto &mo : split_objs(m_arr)) {
            lab::MechanicalMateSpec m;
            m.id = r_str(mo, "id", "mate_1");
            m.kind = parse_mate_kind_str(r_str(mo, "kind", "revolute"));
            m.parent_body = r_str(mo, "parent_body", "chassis");
            m.child_body = r_str(mo, "child_body", "chassis");
            m.anchor_parent_m = r_vec3(mo, "anchor_parent_m", {0, 0, 0});
            m.axis_local = r_vec3(mo, "axis_local", {0, 0, 1});
            m.drive_value = r_num(mo, "drive_value", 0.0);
            m.secondary_value = r_num(mo, "secondary_value", 0.0);
            m.limit_min = r_num(mo, "limit_min", -180.0);
            m.limit_max = r_num(mo, "limit_max", 180.0);
            m.enforce_limits = r_bool(mo, "enforce_limits", true);
            m.gear_ratio = r_num(mo, "gear_ratio", 1.0);
            m.pitch_radius_m = r_num(mo, "pitch_radius_m", 0.02);
            m.coupled_mate_id = r_str(mo, "coupled_mate_id", "");
            m.load_capacity_n = r_num(mo, "load_capacity_n", 475.0);
            m.suppressed = r_bool(mo, "suppressed", false);
            params.mechanical_mates.push_back(std::move(m));
        }
    }
}

void draw_standard_library_window(LibraryAndMatesUiState &ui, AircraftDesignParams &params,
                                  const LiveEvidenceSummary &evidence, std::string &banner,
                                  const std::function<void()> &on_push_undo,
                                  const std::function<void()> &on_rebuild) {
    if (!ui.open_library_window) return;
    ImGui::SetNextWindowSize(ImVec2(510.0f, 560.0f), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImVec2(290.0f, 92.0f), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Standard Part & Propulsion Library (81 ISO/DIN/UAV Items)", &ui.open_library_window)) {
        ImGui::End();
        return;
    }

    const auto &cats = lab::standard_library_categories();
    ui.selected_cat_idx = std::clamp(ui.selected_cat_idx, 0, static_cast<int>(cats.size()) - 1);
    ImGui::SetNextItemWidth(175.0f);
    if (ImGui::BeginCombo("Category", cats[ui.selected_cat_idx].c_str())) {
        for (int i = 0; i < static_cast<int>(cats.size()); ++i) {
            if (ImGui::Selectable(cats[i].c_str(), ui.selected_cat_idx == i)) {
                ui.selected_cat_idx = i;
                ui.selected_catalog_row = 0;
            }
        }
        ImGui::EndCombo();
    }
    ImGui::SameLine();
    ImGui::SetNextItemWidth(180.0f);
    ImGui::InputTextWithHint("##lib_search", "Search M4, 608ZZ, MN3508...", ui.search_buf, sizeof(ui.search_buf));

    const auto matches = lab::search_standard_library(cats[ui.selected_cat_idx], ui.search_buf);
    ImGui::TextDisabled("%zu matching catalog parts | Inserted in 3D assembly: %d (%.3f kg)",
                        matches.size(), evidence.library_parts_count, evidence.library_parts_mass_kg);

    ImGui::BeginChild("##lib_list", ImVec2(0.0f, 225.0f), true);
    if (!matches.empty()) {
        ui.selected_catalog_row = std::clamp(ui.selected_catalog_row, 0, static_cast<int>(matches.size()) - 1);
    } else {
        ui.selected_catalog_row = -1;
    }
    for (int i = 0; i < static_cast<int>(matches.size()); ++i) {
        const auto *it = matches[i];
        char row_lbl[192];
        std::snprintf(row_lbl, sizeof(row_lbl), "[%s] %s  (%.4g kg)", it->category.c_str(), it->name.c_str(), it->mass_kg);
        if (ImGui::Selectable(row_lbl, i == ui.selected_catalog_row)) {
            ui.selected_catalog_row = i;
        }
    }
    ImGui::EndChild();

    if (ui.selected_catalog_row >= 0 && ui.selected_catalog_row < static_cast<int>(matches.size())) {
        const auto *sel = matches[ui.selected_catalog_row];
        ImGui::Separator();
        ImGui::Text("Spec: %s (%s)", sel->name.c_str(), sel->id.c_str());
        ImGui::Text("OD: %.2f mm | ID: %.2f mm | LxWxH: %.1f x %.1f x %.1f mm",
                    sel->od_mm, sel->id_mm, sel->length_mm, sel->width_mm, sel->height_mm);
        ImGui::Text("Mass: %.4f kg | Thrust: %.1f N | Shear/Cr: %.0f N | EI: %.1f Nm2",
                    sel->mass_kg, sel->max_thrust_n,
                    std::max(sel->shear_capacity_n, sel->dynamic_load_cr_n), sel->ei_nm2);
        ImGui::TextDisabled("Provenance: %s (custom additions -> UNVALIDATED_CUSTOM)", sel->provenance.c_str());

        ImGui::SetNextItemWidth(220.0f);
        ImGui::InputFloat3("Insert XYZ (m)", ui.insert_pos, "%.3f");
        if (!params.mate_bodies.empty()) {
            ui.attach_body_idx = std::clamp(ui.attach_body_idx, 0, static_cast<int>(params.mate_bodies.size()) - 1);
            ImGui::SameLine();
            ImGui::SetNextItemWidth(135.0f);
            if (ImGui::BeginCombo("Attach Body", params.mate_bodies[ui.attach_body_idx].id.c_str())) {
                for (int bi = 0; bi < static_cast<int>(params.mate_bodies.size()); ++bi) {
                    if (ImGui::Selectable(params.mate_bodies[bi].id.c_str(), bi == ui.attach_body_idx)) {
                        ui.attach_body_idx = bi;
                    }
                }
                ImGui::EndCombo();
            }
        }
        if (ImGui::Button("Insert Into 3D Scene")) {
            on_push_undo();
            const std::string pbody = params.mate_bodies.empty()
                                          ? std::string("chassis")
                                          : params.mate_bodies[ui.attach_body_idx].id;
            insert_library_item_into_scene(*sel, params, {ui.insert_pos[0], ui.insert_pos[1], ui.insert_pos[2]}, pbody);
            banner = "Inserted 3D part: " + sel->name + " (coupled to CoG & Mates)";
            on_rebuild();
        }
        ImGui::SameLine();
        if (ImGui::Button("Apply Spec To Vehicle")) {
            on_push_undo();
            apply_library_item_to_params(*sel, params, banner);
            on_rebuild();
        }
    }

    ImGui::Separator();
    ImGui::Text("Inserted Hardware BOM (%zu items):", params.inserted_parts.size());
    ImGui::BeginChild("##inserted_bom", ImVec2(0.0f, 110.0f), true);
    for (int i = 0; i < static_cast<int>(params.inserted_parts.size()); ++i) {
        const auto &ip = params.inserted_parts[i];
        ImGui::PushID(i);
        ImGui::Text("%d. %s @ (%.2f, %.2f, %.2f)m [->%s]",
                    i + 1, ip.name.c_str(), ip.pos_m[0], ip.pos_m[1], ip.pos_m[2], ip.attached_body_id.c_str());
        ImGui::SameLine();
        if (ImGui::SmallButton("Del")) {
            on_push_undo();
            const std::string bid = ip.instance_id;
            params.inserted_parts.erase(params.inserted_parts.begin() + i);
            std::erase_if(params.mate_bodies, [&](const lab::RigidBodyNode &b) { return b.id == bid; });
            std::erase_if(params.mechanical_mates, [&](const lab::MechanicalMateSpec &m) { return m.child_body == bid; });
            on_rebuild();
            ImGui::PopID();
            break;
        }
        ImGui::PopID();
    }
    ImGui::EndChild();
    ImGui::End();
}

void draw_mechanical_mates_window(LibraryAndMatesUiState &ui, AircraftDesignParams &params,
                                  const GeneratedCADScene &scene,
                                  const std::function<void()> &on_push_undo,
                                  const std::function<void()> &on_rebuild) {
    if (!ui.open_mates_window) return;
    ImGui::SetNextWindowSize(ImVec2(540.0f, 540.0f), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImVec2(320.0f, 110.0f), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Multi-Body Mechanical Mates & Kinematic Solver", &ui.open_mates_window)) {
        ImGui::End();
        return;
    }

    const auto &sol = scene.latest_mates_solution;
    ImGui::Text("Solver: %d Active Mates | Free DoF: %d | Min FoS: %.2fx | Min Clear: %.1f mm",
                sol.active_mates, sol.total_free_dof,
                [&]() {
                    double mn = 99.0;
                    for (const auto &ms : sol.mate_states) mn = std::min(mn, ms.joint_fos);
                    return mn > 50.0 ? 50.0 : mn;
                }(),
                sol.min_clearance_mm);
    if (sol.any_limit_violated || sol.any_interference) {
        ImGui::TextColored(ImVec4(0.82f, 0.14f, 0.14f, 1.0f), "ALERT: %s%s",
                           sol.any_limit_violated ? "Joint stop limit exceeded! " : "",
                           sol.any_interference ? "Multi-body collision interference detected!" : "");
    } else {
        ImGui::TextColored(ImVec4(0.10f, 0.55f, 0.25f, 1.0f), "Kinematic Tree OK (SE(3) Hamilton wxyz + Collision Clear)");
    }

    bool changed = false;
    if (ImGui::Checkbox("Animate Mechanism", &params.animate_mates)) changed = true;
    ImGui::SameLine();
    if (ImGui::Checkbox("Show 3D Joint Gizmos", &params.show_mate_gizmos)) changed = true;
    ImGui::SameLine();
    if (ImGui::SmallButton("Reset Preset Mates")) {
        on_push_undo();
        init_default_mates_for_params(params);
        changed = true;
    }

    // Active mates editor
    ImGui::Separator();
    ImGui::BeginChild("##mates_list", ImVec2(0.0f, 240.0f), true);
    for (int mi = 0; mi < static_cast<int>(params.mechanical_mates.size()); ++mi) {
        auto &m = params.mechanical_mates[mi];
        ImGui::PushID(mi);
        bool enabled = !m.suppressed;
        if (ImGui::Checkbox("##m_en", &enabled)) {
            m.suppressed = !enabled;
            changed = true;
        }
        ImGui::SameLine();
        ImGui::Text("%s [%s]: %s -> %s", m.id.c_str(), lab::mate_kind_name(m.kind),
                    m.parent_body.c_str(), m.child_body.c_str());

        if (m.kind == lab::MateKind::Revolute || m.kind == lab::MateKind::Spherical) {
            float dv = static_cast<float>(m.drive_value);
            ImGui::SetNextItemWidth(160.0f);
            if (ImGui::SliderFloat("Angle (deg)", &dv, static_cast<float>(m.limit_min), static_cast<float>(m.limit_max), "%.1f")) {
                m.drive_value = dv;
                if (m.id == "tilt_left" && params.family == VehicleFamily::VTOL) {
                    params.vtol_tilt_deg = dv;
                }
                changed = true;
            }
        } else if (m.kind == lab::MateKind::Prismatic || m.kind == lab::MateKind::Cylindrical || m.kind == lab::MateKind::Planar) {
            float dv = static_cast<float>(m.drive_value);
            ImGui::SetNextItemWidth(160.0f);
            if (ImGui::SliderFloat("Stroke (m)", &dv, static_cast<float>(m.limit_min), static_cast<float>(m.limit_max), "%.3f")) {
                m.drive_value = dv;
                changed = true;
            }
        } else if (m.kind == lab::MateKind::Gear) {
            float gr = static_cast<float>(m.gear_ratio);
            ImGui::SetNextItemWidth(140.0f);
            if (ImGui::SliderFloat("Ratio", &gr, -6.0f, 6.0f, "%.2fx")) {
                m.gear_ratio = gr;
                changed = true;
            }
            ImGui::SameLine();
            ImGui::TextDisabled("coupled -> %s", m.coupled_mate_id.c_str());
        } else if (m.kind == lab::MateKind::RackPinion) {
            float pr = static_cast<float>(m.pitch_radius_m * 1000.0);
            ImGui::SetNextItemWidth(140.0f);
            if (ImGui::SliderFloat("Pitch R (mm)", &pr, 5.0f, 80.0f, "%.1f")) {
                m.pitch_radius_m = pr * 0.001;
                changed = true;
            }
        }

        for (const auto &ms : sol.mate_states) {
            if (ms.mate_id == m.id) {
                ImGui::SameLine();
                ImGui::TextDisabled("F=%.1fN FoS=%.1fx", ms.reaction_force_n, ms.joint_fos);
                break;
            }
        }
        ImGui::PopID();
    }
    ImGui::EndChild();

    // Add Mate builder
    ImGui::Separator();
    if (params.mate_bodies.size() >= 2) {
        const char *mkinds[] = {"Rigid", "Revolute", "Prismatic", "Cylindrical", "Spherical", "Gear", "RackPinion", "Planar"};
        ImGui::SetNextItemWidth(120.0f);
        ImGui::Combo("Type", &ui.new_mate_kind, mkinds, 8);
        ui.new_parent_idx = std::clamp(ui.new_parent_idx, 0, static_cast<int>(params.mate_bodies.size()) - 1);
        ui.new_child_idx = std::clamp(ui.new_child_idx, 0, static_cast<int>(params.mate_bodies.size()) - 1);
        ImGui::SameLine();
        ImGui::SetNextItemWidth(115.0f);
        if (ImGui::BeginCombo("Parent", params.mate_bodies[ui.new_parent_idx].id.c_str())) {
            for (int bi = 0; bi < static_cast<int>(params.mate_bodies.size()); ++bi) {
                if (ImGui::Selectable(params.mate_bodies[bi].id.c_str(), bi == ui.new_parent_idx)) ui.new_parent_idx = bi;
            }
            ImGui::EndCombo();
        }
        ImGui::SameLine();
        ImGui::SetNextItemWidth(115.0f);
        if (ImGui::BeginCombo("Child", params.mate_bodies[ui.new_child_idx].id.c_str())) {
            for (int bi = 0; bi < static_cast<int>(params.mate_bodies.size()); ++bi) {
                if (ImGui::Selectable(params.mate_bodies[bi].id.c_str(), bi == ui.new_child_idx)) ui.new_child_idx = bi;
            }
            ImGui::EndCombo();
        }
        ImGui::SetNextItemWidth(200.0f);
        ImGui::InputFloat3("Joint Axis", ui.new_axis, "%.2f");
        ImGui::SameLine();
        if (ImGui::Button("Add Mate") && ui.new_parent_idx != ui.new_child_idx) {
            on_push_undo();
            lab::MechanicalMateSpec nm;
            nm.id = "user_mate_" + std::to_string(params.mechanical_mates.size() + 1);
            nm.kind = static_cast<lab::MateKind>(std::clamp(ui.new_mate_kind, 0, 7));
            nm.parent_body = params.mate_bodies[ui.new_parent_idx].id;
            nm.child_body = params.mate_bodies[ui.new_child_idx].id;
            nm.axis_local = {ui.new_axis[0], ui.new_axis[1], ui.new_axis[2]};
            nm.anchor_parent_m = {ui.new_anchor[0], ui.new_anchor[1], ui.new_anchor[2]};
            nm.limit_min = ui.new_limit_min;
            nm.limit_max = ui.new_limit_max;
            nm.gear_ratio = ui.new_gear_ratio;
            if (!params.mechanical_mates.empty()) nm.coupled_mate_id = params.mechanical_mates[0].id;
            params.mechanical_mates.push_back(std::move(nm));
            changed = true;
        }
    }

    if (changed) on_rebuild();
    ImGui::End();
}

} // namespace aerolab
