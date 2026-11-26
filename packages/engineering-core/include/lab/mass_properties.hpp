#pragma once

#include <array>
#include <span>

namespace lab {

using Vector3 = std::array<double, 3>;
using QuaternionWxyz = std::array<double, 4>;

struct MassPoint {
    double mass_kg;
    Vector3 position_m;
};

struct MassProperties {
    double mass_kg;
    Vector3 center_of_mass_m;
};

struct RotorDisk {
    Vector3 position_m;
    double radius_m;
};

struct ClearanceResult {
    bool clear;
    double minimum_tip_clearance_m;
};

MassProperties combine_mass_points(std::span<const MassPoint> parts);
Vector3 transform_point_wxyz(const Vector3 &translation_m, const QuaternionWxyz &q_wxyz, const Vector3 &local_m);
ClearanceResult evaluate_rotor_pair_clearance(std::span<const RotorDisk> rotors, double minimum_required_m);

} // namespace lab
