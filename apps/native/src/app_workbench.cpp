#include "app_workbench.hpp"

#include "imgui.h"
#include "imgui_internal.h"

namespace aerolab {

bool AppWorkbench::init(gl33::Dispatch *gl, const std::filesystem::path &repo_root) {
    gl_ = gl;
    repo_root_ = repo_root;
    viewport_ = std::make_unique<ViewportGL>();
    if (!viewport_->init(gl_)) return false;
    ipc_ = std::make_unique<WorkerIPC>(repo_root_);
    apply_light_cad_theme();
    rebuild_geometry();
    return true;
}

void AppWorkbench::shutdown() {
    if (viewport_) {
        viewport_->shutdown();
        viewport_.reset();
    }
    ipc_.reset();
}

void AppWorkbench::apply_light_cad_theme() {
    ImGui::StyleColorsLight();
    ImGuiStyle &style = ImGui::GetStyle();
    style.WindowRounding = 0.0f;
    style.ChildRounding = 4.0f;
    style.FrameRounding = 4.0f;
    style.PopupRounding = 4.0f;
    style.TabRounding = 3.0f;
    style.FrameBorderSize = 1.0f;
    style.WindowBorderSize = 1.0f;
    style.WindowPadding = ImVec2(10.0f, 8.0f);
    style.ItemSpacing = ImVec2(8.0f, 6.0f);

    auto *colors = style.Colors;
    colors[ImGuiCol_WindowBg] = ImVec4(0.97f, 0.98f, 0.99f, 1.00f);
    colors[ImGuiCol_ChildBg] = ImVec4(1.00f, 1.00f, 1.00f, 1.00f);
    colors[ImGuiCol_PopupBg] = ImVec4(1.00f, 1.00f, 1.00f, 0.98f);
    colors[ImGuiCol_MenuBarBg] = ImVec4(0.94f, 0.95f, 0.97f, 1.00f);
    colors[ImGuiCol_Border] = ImVec4(0.81f, 0.85f, 0.90f, 1.00f);
    colors[ImGuiCol_FrameBg] = ImVec4(1.00f, 1.00f, 1.00f, 1.00f);
    colors[ImGuiCol_FrameBgHovered] = ImVec4(0.92f, 0.95f, 0.99f, 1.00f);
    colors[ImGuiCol_FrameBgActive] = ImVec4(0.85f, 0.91f, 0.98f, 1.00f);
    colors[ImGuiCol_TitleBg] = ImVec4(0.92f, 0.94f, 0.97f, 1.00f);
    colors[ImGuiCol_TitleBgActive] = ImVec4(0.89f, 0.92f, 0.96f, 1.00f);
    colors[ImGuiCol_Button] = ImVec4(0.94f, 0.96f, 0.98f, 1.00f);
    colors[ImGuiCol_ButtonHovered] = ImVec4(0.84f, 0.90f, 0.98f, 1.00f);
    colors[ImGuiCol_ButtonActive] = ImVec4(0.75f, 0.84f, 0.96f, 1.00f);
    colors[ImGuiCol_Header] = ImVec4(0.90f, 0.93f, 0.97f, 1.00f);
    colors[ImGuiCol_HeaderHovered] = ImVec4(0.82f, 0.89f, 0.98f, 1.00f);
    colors[ImGuiCol_SliderGrab] = ImVec4(0.15f, 0.39f, 0.92f, 1.00f);
    colors[ImGuiCol_SliderGrabActive] = ImVec4(0.10f, 0.31f, 0.80f, 1.00f);
    colors[ImGuiCol_CheckMark] = ImVec4(0.15f, 0.39f, 0.92f, 1.00f);
    colors[ImGuiCol_Text] = ImVec4(0.11f, 0.14f, 0.18f, 1.00f);
}

void AppWorkbench::switch_family(VehicleFamily family) {
    push_undo_snapshot();
    params.family = family;
    selected_part_idx = -1;
    if (family == VehicleFamily::Multirotor) {
        params.project_name = "Quad MN3508 Baseline";
        params.rotor_rpm = 4800.0f;
        camera.distance_m = 1.65f;
    } else if (family == VehicleFamily::FixedWing) {
        params.project_name = "Fixed-Wing Trainer";
        params.rotor_rpm = 6200.0f;
        camera.distance_m = 2.40f;
    } else if (family == VehicleFamily::Helicopter) {
        params.project_name = "Helicopter Rotorcraft";
        params.rotor_rpm = 1450.0f;
        camera.distance_m = 2.25f;
    } else if (family == VehicleFamily::VTOL) {
        params.project_name = "VTOL Tiltrotor";
        params.rotor_rpm = 4200.0f;
        camera.distance_m = 2.45f;
    } else {
        params.project_name = "Part Designer Studio";
        camera.distance_m = 0.75f;
    }
    rebuild_geometry();
}

void AppWorkbench::push_undo_snapshot() {
    undo_stack_.push_back(params);
    if (undo_stack_.size() > 32) undo_stack_.erase(undo_stack_.begin());
    redo_stack_.clear();
}

void AppWorkbench::undo() {
    if (undo_stack_.empty()) return;
    redo_stack_.push_back(params);
    params = undo_stack_.back();
    undo_stack_.pop_back();
    rebuild_geometry();
}

void AppWorkbench::redo() {
    if (redo_stack_.empty()) return;
    undo_stack_.push_back(params);
    params = redo_stack_.back();
    redo_stack_.pop_back();
    rebuild_geometry();
}

void AppWorkbench::sync_feature_tree() {
    feature_tree.clear();
    if (params.family == VehicleFamily::CustomPart || params.attach_custom_part) {
        feature_tree.push_back({"sketch_1", "2D Profile Sketch", "Sketch"});
        feature_tree.push_back({"solid_1", params.active_part.revolve_360 ? "Revolve Boss" : "Extrude Boss",
                                params.active_part.revolve_360 ? "Revolve" : "Extrude"});
        if (params.active_part.circular_pattern_count > 1) {
            feature_tree.push_back({"pat_1", "Circular Pattern x" + std::to_string(params.active_part.circular_pattern_count), "Pattern"});
        }
    }
    if (params.family == VehicleFamily::Multirotor) {
        feature_tree.push_back({"frame_1", "Center Plate & Avionics", "Solid"});
        feature_tree.push_back({"rotors_1", "Rotor Array (" + std::to_string(params.rotor_count) + "x Twisted)", "RotorArray"});
    } else if (params.family == VehicleFamily::FixedWing || params.family == VehicleFamily::VTOL) {
        feature_tree.push_back({"fuse_1", "Fuselage Nose-Tail Loft", "Fuselage"});
        feature_tree.push_back({"wing_1", "NACA " + params.airfoil_code + " Wing Loft", "WingLoft"});
        feature_tree.push_back({"tail_1", "Empennage Stabilizers", "WingLoft"});
    } else if (params.family == VehicleFamily::Helicopter) {
        feature_tree.push_back({"heli_fuse", "Pod & Tail Boom", "Fuselage"});
        feature_tree.push_back({"main_rotor", "Main + Tail Rotors", "RotorArray"});
    }
}

void AppWorkbench::rebuild_geometry() {
    scene = build_cad_scene(params, selected_part_idx);
    if (viewport_) {
        viewport_->upload_scene(scene);
    }
    evaluate_live_physics_and_curves(params, scene, evidence);
    sync_feature_tree();
}

void AppWorkbench::render_ui_and_scene(float dt_s, int fb_w, int fb_h) {
    (void)fb_w;
    (void)fb_h;
    if (ipc_ && ipc_->poll_completed_results(evidence) && viewport_) {
        viewport_->upload_trajectory_path(evidence.traj_pos_m);
    }
    const ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(vp->WorkPos);
    ImGui::SetNextWindowSize(vp->WorkSize);
    ImGui::SetNextWindowViewport(vp->ID);

    ImGuiWindowFlags host_flags = ImGuiWindowFlags_MenuBar | ImGuiWindowFlags_NoDocking |
                                  ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoCollapse |
                                  ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoMove |
                                  ImGuiWindowFlags_NoBringToFrontOnFocus | ImGuiWindowFlags_NoNavFocus;

    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 0.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(6.0f, 4.0f));
    ImGui::Begin("AerodynamicsLabHost", nullptr, host_flags);
    ImGui::PopStyleVar(3);

    draw_menu_bar();
    draw_quick_toolstrip();

    const ImGuiID dockspace_id = ImGui::GetID("AerolabMainDockspace");
    static bool layout_initialized = false;
    if (!layout_initialized) {
        layout_initialized = true;
        ImGui::DockBuilderRemoveNode(dockspace_id);
        ImGui::DockBuilderAddNode(dockspace_id, ImGuiDockNodeFlags_DockSpace);
        ImGui::DockBuilderSetNodeSize(dockspace_id, vp->WorkSize);

        ImGuiID dock_main = dockspace_id;
        ImGuiID dock_left = ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Left, 0.22f, nullptr, &dock_main);
        ImGuiID dock_right = ImGui::DockBuilderSplitNode(dock_main, ImGuiDir_Right, 0.28f, nullptr, &dock_main);

        ImGui::DockBuilderDockWindow("Model & Feature Tree", dock_left);
        ImGui::DockBuilderDockWindow("3D CAD Viewport", dock_main);
        ImGui::DockBuilderDockWindow("Parameters & Evidence", dock_right);
        ImGui::DockBuilderFinish(dockspace_id);
    }
    ImGui::DockSpace(dockspace_id, ImVec2(0.0f, 0.0f), ImGuiDockNodeFlags_NoCloseButton);
    ImGui::End();

    draw_left_feature_tree();
    draw_center_viewport(dt_s);
    draw_right_inspector();
    draw_modals();
}

bool AppWorkbench::export_viewport_png(const std::string &path) {
    std::vector<std::uint8_t> rgba;
    if (!viewport_ || !viewport_->read_fbo_rgba(last_vp_w_, last_vp_h_, rgba)) return false;
    return write_png_rgba(path, last_vp_w_, last_vp_h_, rgba);
}

} // namespace aerolab
