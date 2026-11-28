#pragma once

#include "cad_types.hpp"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace aerolab {

struct AirfoilSectionPoint {
    float x; // chordwise [0..1]
    float z; // thickness/camber
};

std::vector<AirfoilSectionPoint> sample_naca4_airfoil(const std::string &code, int n_per_surface = 22);

GeneratedCADScene build_cad_scene(const AircraftDesignParams &params, int selected_part_idx = -1,
                                  const FreeformBrepCache *brep = nullptr);

GeneratedCADScene build_200part_benchmark_scene(int selected_part_idx = -1);

void evaluate_live_physics_and_curves(const AircraftDesignParams &params, const GeneratedCADScene &scene,
                                      LiveEvidenceSummary &summary);

bool write_png_rgba(const std::string &path, int width, int height, const std::vector<std::uint8_t> &rgba_bottom_up);

} // namespace aerolab
