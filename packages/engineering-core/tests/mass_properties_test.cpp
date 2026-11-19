#include "lab/mass_properties.hpp"

#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

int main() {
    const std::array<lab::MassPoint, 2> parts = {{{2.0, {1e9, 0.0, -1.0}},
                                               {1.0, {1e9 + 3.0, 0.0, 2.0}}}};
    const auto result = lab::combine_mass_points(parts);
    if (result.mass_kg != 3.0 || std::abs(result.center_of_mass_m[0] - (1e9 + 1.0)) > 1e-7
        || std::abs(result.center_of_mass_m[2]) > 1e-14) {
        std::cerr << "Mass combination disagrees with the analytical result\n";
        return 1;
    }
    for (const double mass : {0.0, -1.0, std::numeric_limits<double>::infinity()}) {
        const std::array<lab::MassPoint, 1> invalid = {{{mass, {0.0, 0.0, 0.0}}}};
        try {
            lab::combine_mass_points(invalid);
            return 2;
        } catch (const std::invalid_argument &) {
        }
    }
    try {
        lab::combine_mass_points({});
        return 3;
    } catch (const std::invalid_argument &) {
    }
    std::cout << "Engineering mass-property checks passed\n";
    return 0;
}
