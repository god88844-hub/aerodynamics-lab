#pragma once

#include <array>
#include <span>

namespace lab {

using Vector3 = std::array<double, 3>;

struct MassPoint {
    double mass_kg;
    Vector3 position_m;
};

struct MassProperties {
    double mass_kg;
    Vector3 center_of_mass_m;
};

MassProperties combine_mass_points(std::span<const MassPoint> parts);

} // namespace lab
