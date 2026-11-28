#pragma once

#include "cad_types.hpp"

#include <array>
#include <functional>
#include <string>

namespace aerolab {

struct LibraryAndMatesUiState {
    bool open_library_window = false;
    bool open_mates_window = false;
    int selected_cat_idx = 0;
    char search_buf[64] = "";
    int selected_catalog_row = 0;
    float insert_pos[3] = {0.0f, 0.14f, 0.05f};
    int attach_body_idx = 0;

    int new_mate_kind = 1; // Revolute default
    int new_parent_idx = 0;
    int new_child_idx = 1;
    float new_axis[3] = {0.0f, 1.0f, 0.0f};
    float new_anchor[3] = {0.0f, 0.25f, 0.0f};
    float new_limit_min = -45.0f;
    float new_limit_max = 45.0f;
    float new_gear_ratio = -1.0f;
};

void init_default_mates_for_params(AircraftDesignParams &params);

void apply_library_item_to_params(const lab::StandardPartSpec &item, AircraftDesignParams &params, std::string &banner);

void insert_library_item_into_scene(const lab::StandardPartSpec &item, AircraftDesignParams &params,
                                    const std::array<float, 3> &pos_m, const std::string &parent_body);

std::string serialize_library_and_mates_json(const AircraftDesignParams &params);
void deserialize_library_and_mates_json(const std::string &json_text, AircraftDesignParams &params);

void draw_standard_library_window(LibraryAndMatesUiState &ui, AircraftDesignParams &params,
                                  const LiveEvidenceSummary &evidence, std::string &banner,
                                  const std::function<void()> &on_push_undo,
                                  const std::function<void()> &on_rebuild);

void draw_mechanical_mates_window(LibraryAndMatesUiState &ui, AircraftDesignParams &params,
                                  const GeneratedCADScene &scene,
                                  const std::function<void()> &on_push_undo,
                                  const std::function<void()> &on_rebuild);

} // namespace aerolab
