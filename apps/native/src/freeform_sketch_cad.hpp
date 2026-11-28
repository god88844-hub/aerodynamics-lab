#pragma once

#include "cad_types.hpp"

#include <array>
#include <filesystem>
#include <functional>
#include <string>

namespace aerolab {

enum class SketchTool {
    SelectDrag = 0,
    DrawLine = 1,
    DrawRect = 2,
    DrawCircle = 3,
    DrawArc = 4,
    DrawSpline = 5,
};

struct FreeformSketchUiState {
    bool open_window = false;
    bool pick_face_mode = false;
    SketchTool active_tool = SketchTool::SelectDrag;
    int selected_entity_idx = -1;
    int second_entity_idx = -1;
    int drag_entity_idx = -1;
    int drag_pt_idx = 0;
    bool snap_grid = true;
    float grid_step_m = 0.005f;
    float dim_input_mm = 40.0f;
    float op_depth_mm = 30.0f;
    float op_angle_deg = 360.0f;
    float op_radius_mm = 2.0f;
    float op_loft_offset_mm = 60.0f;
    float op_loft_scale = 0.55f;
    bool op_symmetric = false;
    std::vector<std::array<float, 2>> pending_pts;
};

struct PickedFaceResult {
    bool hit = false;
    int face_id = -1;
    std::array<float, 3> hit_pos_m{0.0f, 0.0f, 0.0f};
    WorkplaneSpec workplane{};
};

void init_default_freeform_sketch(CustomPartParams &part);

bool solve_sketch_constraints_cpp(FreeformSketchState &sketch);

PickedFaceResult pick_face_under_cursor(const GeneratedCADScene &scene, const FreeformBrepCache &brep,
                                        const CameraOrbitState &cam, ViewportLayout layout, int vp_w, int vp_h,
                                        float local_mx, float local_my);

std::string build_freeform_cad_payload_json(const CustomPartParams &part, const std::filesystem::path &mesh_out_path,
                                            const std::filesystem::path &export_dir);

bool load_occt_mesh_json(const std::filesystem::path &mesh_json_path, FreeformBrepCache &cache);

std::string build_embedded_cfd_fea_payload_json(const AircraftDesignParams &params, const GeneratedCADScene &scene,
                                                const LiveEvidenceSummary &summary,
                                                const std::filesystem::path &field_out_path,
                                                const std::filesystem::path &export_dir);

bool load_embedded_cfd_fea_json(const std::filesystem::path &field_json_path, EmbeddedCfdFeaCache &cache);

std::string serialize_freeform_part_json(const CustomPartParams &part);
bool deserialize_freeform_part_json(const std::string &json_text, CustomPartParams &part);

void draw_freeform_sketcher_window(FreeformSketchUiState &ui, AircraftDesignParams &params,
                                   const FreeformBrepCache &brep,
                                   const std::function<void()> &on_push_undo,
                                   const std::function<void()> &on_rebuild_local,
                                   const std::function<void()> &on_build_occt);

} // namespace aerolab
