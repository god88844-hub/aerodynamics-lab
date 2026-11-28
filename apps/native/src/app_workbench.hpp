#pragma once

#include "cad_mesh_builder.hpp"
#include "cad_types.hpp"
#include "freeform_sketch_cad.hpp"
#include "viewport_gl.hpp"
#include "worker_ipc.hpp"

#include <memory>
#include <string>
#include <vector>

struct GLFWwindow;

namespace aerolab {

class AppWorkbench {
public:
    AppWorkbench() = default;
    ~AppWorkbench() = default;

    bool init(gl33::Dispatch *gl, const std::filesystem::path &repo_root);
    void shutdown();

    void apply_light_cad_theme();
    void render_ui_and_scene(float dt_s, int fb_w, int fb_h);
    bool export_viewport_png(const std::string &path);

    // State manipulation + undo/redo
    void switch_family(VehicleFamily family);
    void push_undo_snapshot();
    void undo();
    void redo();
    void rebuild_geometry();

    AircraftDesignParams params;
    ViewportLayout viewport_layout = ViewportLayout::Single3D;
    ShadingMode shading_mode = ShadingMode::ShadedEdges;
    bool dark_canvas = false;
    bool show_wake = true;
    bool show_cog = true;
    int selected_part_idx = -1;

    CameraOrbitState camera;
    GeneratedCADScene scene;
    LiveEvidenceSummary evidence;
    std::vector<FeatureNode> feature_tree;
    FreeformBrepCache brep_cache;
    FreeformSketchUiState freeform_ui;

    void trigger_freeform_occt_build();
    WorkerIPC *worker() { return ipc_.get(); }

    // Modals (kept cleanly off the main toolbar)
    bool show_about_modal = false;
    bool show_verification_modal = false;
    bool show_part_export_modal = false;
    bool show_equations_modal = false;
    bool show_failure_atlas_modal = false;
    std::string export_banner;

private:
    void draw_menu_bar();
    void draw_quick_toolstrip();
    void draw_left_feature_tree();
    void draw_center_viewport(float dt_s);
    void draw_right_inspector();
    void draw_rc_hud();
    void draw_modals();
    void sync_feature_tree();

    gl33::Dispatch *gl_ = nullptr;
    std::filesystem::path repo_root_;
    std::unique_ptr<ViewportGL> viewport_;
    std::unique_ptr<WorkerIPC> ipc_;

    std::vector<AircraftDesignParams> undo_stack_;
    std::vector<AircraftDesignParams> redo_stack_;
    int last_vp_w_ = 960;
    int last_vp_h_ = 640;
};

} // namespace aerolab
