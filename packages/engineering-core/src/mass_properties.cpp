#include "lab/mass_properties.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace lab {

MassProperties combine_mass_points(std::span<const MassPoint> parts) {
    if (parts.empty()) {
        throw std::invalid_argument("At least one part is required");
    }
    const Vector3 origin = parts.front().position_m;
    Vector3 moment = {0.0, 0.0, 0.0};
    double total_mass = 0.0;
    for (const auto &part : parts) {
        if (!std::isfinite(part.mass_kg) || part.mass_kg <= 0.0) {
            throw std::invalid_argument("Part masses must be finite and positive");
        }
        total_mass += part.mass_kg;
        for (std::size_t axis = 0; axis < 3; ++axis) {
            if (!std::isfinite(part.position_m[axis])) {
                throw std::invalid_argument("Part coordinates must be finite");
            }
            moment[axis] += part.mass_kg * (part.position_m[axis] - origin[axis]);
        }
    }
    if (!std::isfinite(total_mass)) {
        throw std::overflow_error("Combined mass exceeds the numerical range");
    }
    Vector3 center;
    for (std::size_t axis = 0; axis < 3; ++axis) {
        center[axis] = origin[axis] + moment[axis] / total_mass;
        if (!std::isfinite(center[axis])) {
            throw std::overflow_error("Mass moment exceeds the numerical range");
        }
    }
    return {total_mass, center};
}

Vector3 transform_point_wxyz(const Vector3 &translation_m, const QuaternionWxyz &q_wxyz, const Vector3 &local_m) {
    for (std::size_t i = 0; i < 3; ++i) {
        if (!std::isfinite(translation_m[i]) || !std::isfinite(local_m[i])) {
            throw std::invalid_argument("Datum coordinates must be finite");
        }
    }
    double norm2 = 0.0;
    for (double c : q_wxyz) {
        if (!std::isfinite(c)) {
            throw std::invalid_argument("Quaternion components must be finite");
        }
        norm2 += c * c;
    }
    if (std::abs(norm2 - 1.0) > 1e-8) {
        throw std::invalid_argument("Datum orientation must be a unit quaternion");
    }
    const double w = q_wxyz[0];
    const double x = q_wxyz[1];
    const double y = q_wxyz[2];
    const double z = q_wxyz[3];
    const double vx = local_m[0];
    const double vy = local_m[1];
    const double vz = local_m[2];

    const double tx = 2.0 * (y * vz - z * vy);
    const double ty = 2.0 * (z * vx - x * vz);
    const double tz = 2.0 * (x * vy - y * vx);

    return {
        translation_m[0] + vx + w * tx + (y * tz - z * ty),
        translation_m[1] + vy + w * ty + (z * tx - x * tz),
        translation_m[2] + vz + w * tz + (x * ty - y * tx),
    };
}

ClearanceResult evaluate_rotor_pair_clearance(std::span<const RotorDisk> rotors, double minimum_required_m) {
    if (!std::isfinite(minimum_required_m) || minimum_required_m < 0.0) {
        throw std::invalid_argument("Minimum clearance must be finite and non-negative");
    }
    if (rotors.size() < 2) {
        throw std::invalid_argument("At least two rotors are required for pairwise clearance");
    }
    for (const auto &r : rotors) {
        if (!std::isfinite(r.radius_m) || r.radius_m <= 0.0) {
            throw std::invalid_argument("Rotor radii must be finite and positive");
        }
        for (double c : r.position_m) {
            if (!std::isfinite(c)) {
                throw std::invalid_argument("Rotor positions must be finite");
            }
        }
    }
    double min_gap = std::numeric_limits<double>::infinity();
    for (std::size_t i = 0; i < rotors.size(); ++i) {
        for (std::size_t j = i + 1; j < rotors.size(); ++j) {
            const double dx = rotors[i].position_m[0] - rotors[j].position_m[0];
            const double dy = rotors[i].position_m[1] - rotors[j].position_m[1];
            const double dz = rotors[i].position_m[2] - rotors[j].position_m[2];
            const double dist = std::sqrt(dx * dx + dy * dy + dz * dz);
            const double gap = dist - (rotors[i].radius_m + rotors[j].radius_m);
            if (gap < min_gap) {
                min_gap = gap;
            }
        }
    }
    return {min_gap >= minimum_required_m, min_gap};
}

} // namespace lab
