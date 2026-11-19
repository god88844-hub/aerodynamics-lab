#include "lab/mass_properties.hpp"

#include <cmath>
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

} // namespace lab
