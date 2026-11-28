#include "app_workbench.hpp"

#include "imgui.h"
#include "imgui_internal.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <numbers>

namespace aerolab {
namespace {

constexpr float kPi = std::numbers::pi_v<float>;

void draw_polar_plot(const LiveEvidenceSummary &ev) {
    if (ev.rocket_traj_t_s.size() >= 2) {
        ImGui::TextUnformatted("Rocket Ascent (Alt km [Blue] & q kPa [Orange])");
        const ImVec2 avail = ImGui::GetContentRegionAvail();
        const ImVec2 size(std::max(140.0f, avail.x), 118.0f);
        const ImVec2 p0 = ImGui::GetCursorScreenPos();
        const ImVec2 p1(p0.x + size.x, p0.y + size.y);
        ImDrawList *dl = ImGui::GetWindowDrawList();

        dl->AddRectFilled(p0, p1, IM_COL32(250, 252, 255, 255), 4.0f);
        dl->AddRect(p0, p1, IM_COL32(204, 213, 224, 255), 4.0f);

        const float pad_l = 32.0f, pad_r = 10.0f, pad_t = 10.0f, pad_b = 18.0f;
        const float gx0 = p0.x + pad_l, gx1 = p1.x - pad_r;
        const float gy0 = p0.y + pad_t, gy1 = p1.y - pad_b;
        const float t_max = std::max(10.0f, ev.rocket_traj_t_s.back());
        float alt_max = 100.0f, q_max = 35.0f;
        for (float a : ev.rocket_traj_alt_km) alt_max = std::max(alt_max, a);
        for (float qk : ev.rocket_traj_q_kpa) q_max = std::max(q_max, qk);

        for (std::size_t i = 0; i + 1 < ev.rocket_traj_t_s.size(); ++i) {
            const float u0 = ev.rocket_traj_t_s[i] / t_max;
            const float u1 = ev.rocket_traj_t_s[i + 1] / t_max;
            const float va0 = std::clamp(ev.rocket_traj_alt_km[i] / alt_max, 0.0f, 1.0f);
            const float va1 = std::clamp(ev.rocket_traj_alt_km[i + 1] / alt_max, 0.0f, 1.0f);
            dl->AddLine(ImVec2(gx0 + u0 * (gx1 - gx0), gy1 - va0 * (gy1 - gy0)),
                        ImVec2(gx0 + u1 * (gx1 - gx0), gy1 - va1 * (gy1 - gy0)),
                        IM_COL32(37, 99, 235, 255), 2.2f);
            const float vq0 = std::clamp(ev.rocket_traj_q_kpa[i] / q_max, 0.0f, 1.0f);
            const float vq1 = std::clamp(ev.rocket_traj_q_kpa[i + 1] / q_max, 0.0f, 1.0f);
            dl->AddLine(ImVec2(gx0 + u0 * (gx1 - gx0), gy1 - vq0 * (gy1 - gy0)),
                        ImVec2(gx0 + u1 * (gx1 - gx0), gy1 - vq1 * (gy1 - gy0)),
                        IM_COL32(234, 88, 12, 255), 2.0f);
        }
        char top_lbl[32], q_lbl[32];
        std::snprintf(top_lbl, sizeof(top_lbl), "%.0fkm", alt_max);
        std::snprintf(q_lbl, sizeof(q_lbl), "MaxQ %.0fkPa", q_max);
        dl->AddText(ImVec2(p0.x + 3.0f, gy0), IM_COL32(37, 99, 235, 255), top_lbl);
        dl->AddText(ImVec2(gx1 - 76.0f, gy0), IM_COL32(234, 88, 12, 255), q_lbl);
        dl->AddText(ImVec2(gx0, p1.y - 16.0f), IM_COL32(95, 108, 125, 255), "0s");
        dl->AddText(ImVec2(gx1 - 36.0f, p1.y - 16.0f), IM_COL32(95, 108, 125, 255), "420s");
        ImGui::Dummy(size);
        return;
    }
    if (ev.curve_alpha_deg.size() < 2) return;
    ImGui::TextUnformatted("Lift Coefficient (CL vs Alpha)");
    const ImVec2 avail = ImGui::GetContentRegionAvail();
    const ImVec2 size(std::max(140.0f, avail.x), 118.0f);
    const ImVec2 p0 = ImGui::GetCursorScreenPos();
    const ImVec2 p1(p0.x + size.x, p0.y + size.y);
    ImDrawList *dl = ImGui::GetWindowDrawList();

    dl->AddRectFilled(p0, p1, IM_COL32(250, 252, 255, 255), 4.0f);
    dl->AddRect(p0, p1, IM_COL32(204, 213, 224, 255), 4.0f);

    const float pad_l = 28.0f, pad_r = 10.0f, pad_t = 10.0f, pad_b = 18.0f;
    const float gx0 = p0.x + pad_l, gx1 = p1.x - pad_r;
    const float gy0 = p0.y + pad_t, gy1 = p1.y - pad_b;

    for (int g = 0; g <= 3; ++g) {
        const float t = static_cast<float>(g) / 3.0f;
        const float y = gy0 + t * (gy1 - gy0);
        dl->AddLine(ImVec2(gx0, y), ImVec2(gx1, y), IM_COL32(230, 236, 244, 255));
    }

    const float cl_min = -0.3f, cl_max = 1.6f;
    auto to_px = [&](float alpha, float cl) -> ImVec2 {
        const float u = (alpha + 4.0f) / 18.0f;
        const float v = std::clamp((cl - cl_min) / (cl_max - cl_min), 0.0f, 1.0f);
        return ImVec2(gx0 + u * (gx1 - gx0), gy1 - v * (gy1 - gy0));
    };

    for (std::size_t i = 0; i + 1 < ev.curve_alpha_deg.size(); ++i) {
        dl->AddLine(to_px(ev.curve_alpha_deg[i], ev.curve_cl[i]),
                    to_px(ev.curve_alpha_deg[i + 1], ev.curve_cl[i + 1]),
                    IM_COL32(37, 99, 235, 255), 2.2f);
    }
    dl->AddText(ImVec2(p0.x + 4.0f, gy0), IM_COL32(95, 108, 125, 255), "1.6");
    dl->AddText(ImVec2(p0.x + 4.0f, gy1 - 12.0f), IM_COL32(95, 108, 125, 255), "-.3");
    dl->AddText(ImVec2(gx0, p1.y - 16.0f), IM_COL32(95, 108, 125, 255), "-4 deg");
    dl->AddText(ImVec2(gx1 - 42.0f, p1.y - 16.0f), IM_COL32(95, 108, 125, 255), "+14 deg");
    ImGui::Dummy(size);
}

bool draw_interactive_2d_sketch_canvas(CustomPartParams &part) {
    bool modified = false;
    ImGui::Text("Interactive 2D Sketch (Drag blue handle in XY):");
    const ImVec2 avail = ImGui::GetContentRegionAvail();
    const ImVec2 size(std::max(150.0f, avail.x), 116.0f);
    const ImVec2 p0 = ImGui::GetCursorScreenPos();
    const ImVec2 p1(p0.x + size.x, p0.y + size.y);
    ImDrawList *dl = ImGui::GetWindowDrawList();

    dl->AddRectFilled(p0, p1, IM_COL32(252, 253, 255, 255), 4.0f);
    dl->AddRect(p0, p1, IM_COL32(198, 208, 222, 255), 4.0f);
    const float ox = p0.x + 26.0f;
    const float oy = 0.5f * (p0.y + p1.y);
    dl->AddLine(ImVec2(p0.x + 6.0f, oy), ImVec2(p1.x - 6.0f, oy), IM_COL32(226, 232, 240, 255), 1.0f);
    dl->AddLine(ImVec2(ox, p0.y + 6.0f), ImVec2(ox, p1.y - 6.0f), IM_COL32(226, 232, 240, 255), 1.0f);

    const float px_per_m = (size.x - 44.0f) / 0.62f;
    const float len_px = std::clamp(part.length_m * px_per_m, 12.0f, size.x - 42.0f);
    const float half_w_px = std::clamp(part.width_m * 0.5f * px_per_m, 6.0f, 44.0f);
    const ImVec2 r0(ox, oy - half_w_px);
    const ImVec2 r1(ox + len_px, oy + half_w_px);
    dl->AddRectFilled(r0, r1, IM_COL32(219, 234, 254, 180), 3.0f);
    dl->AddRect(r0, r1, IM_COL32(37, 99, 235, 255), 3.0f, 0, 1.8f);
    if (part.hole_radius_m > 0.001f) {
        dl->AddCircle(ImVec2(ox + len_px, oy), std::clamp(part.hole_radius_m * px_per_m, 3.0f, 22.0f),
                      IM_COL32(220, 38, 38, 255), 16, 1.5f);
    }
    const ImVec2 handle(ox + len_px, oy - half_w_px);
    dl->AddCircleFilled(handle, 5.5f, IM_COL32(37, 99, 235, 255));
    char dim_lbl[64];
    std::snprintf(dim_lbl, sizeof(dim_lbl), "%.0f x %.0f mm", part.length_m * 1000.0f, part.width_m * 1000.0f);
    dl->AddText(ImVec2(p0.x + 8.0f, p1.y - 16.0f), IM_COL32(71, 85, 105, 255), dim_lbl);

    ImGui::InvisibleButton("##sketch2d_canvas", size);
    if (ImGui::IsItemActive() && ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
        const ImVec2 mp = ImGui::GetIO().MousePos;
        part.length_m = std::clamp((mp.x - ox) / px_per_m, 0.04f, 0.60f);
        part.width_m = std::clamp((std::abs(oy - mp.y) * 2.0f) / px_per_m, 0.015f, 0.25f);
        modified = true;
    }
    return modified;
}

void draw_view_cube_and_triad(ImDrawList *dl, ImVec2 vp_pos, ImVec2 vp_size,
                              CameraOrbitState &cam, ViewportLayout layout) {
    // 1. Bottom-left RGB Axis Triad
    const ImVec2 origin(vp_pos.x + 42.0f, vp_pos.y + vp_size.y - 42.0f);
    const float yaw = cam.yaw_deg * kPi / 180.0f;
    const float pitch = cam.pitch_deg * kPi / 180.0f;
    auto proj_dir = [&](float dx, float dy, float dz) -> ImVec2 {
        const float cx = -std::sin(yaw) * dx + std::cos(yaw) * dy;
        const float cy = -std::sin(pitch) * (std::cos(yaw) * dx + std::sin(yaw) * dy) + std::cos(pitch) * dz;
        return ImVec2(origin.x + cx * 28.0f, origin.y - cy * 28.0f);
    };
    const ImVec2 ax = proj_dir(1, 0, 0);
    const ImVec2 ay = proj_dir(0, 1, 0);
    const ImVec2 az = proj_dir(0, 0, 1);
    dl->AddLine(origin, ax, IM_COL32(215, 55, 55, 255), 2.2f);
    dl->AddLine(origin, ay, IM_COL32(45, 165, 68, 255), 2.2f);
    dl->AddLine(origin, az, IM_COL32(37, 99, 235, 255), 2.2f);
    dl->AddText(ax, IM_COL32(190, 35, 35, 255), "X");
    dl->AddText(ay, IM_COL32(30, 130, 50, 255), "Y");
    dl->AddText(az, IM_COL32(25, 80, 210, 255), "Z");

    // 2. Quadrant divider lines & clean labels in Ortho 4-View
    if (layout == ViewportLayout::Ortho4View) {
        const float mx = vp_pos.x + vp_size.x * 0.5f;
        const float my = vp_pos.y + vp_size.y * 0.5f;
        dl->AddLine(ImVec2(mx, vp_pos.y), ImVec2(mx, vp_pos.y + vp_size.y), IM_COL32(180, 192, 208, 255), 1.5f);
        dl->AddLine(ImVec2(vp_pos.x, my), ImVec2(vp_pos.x + vp_size.x, my), IM_COL32(180, 192, 208, 255), 1.5f);
        dl->AddText(ImVec2(vp_pos.x + 10, vp_pos.y + 8), IM_COL32(45, 55, 72, 255), "TOP (Z+)");
        dl->AddText(ImVec2(mx + 10, vp_pos.y + 8), IM_COL32(45, 55, 72, 255), "SIDE (Y+)");
        dl->AddText(ImVec2(vp_pos.x + 10, my + 8), IM_COL32(45, 55, 72, 255), "FRONT (X+)");
        dl->AddText(ImVec2(mx + 10, my + 8), IM_COL32(45, 55, 72, 255), "3D ISO");
    }

    // 3. Top-right ViewCube control strip
    const ImVec2 vc_pos(vp_pos.x + vp_size.x - 166.0f, vp_pos.y + 12.0f);
    dl->AddRectFilled(vc_pos, ImVec2(vc_pos.x + 154.0f, vc_pos.y + 30.0f), IM_COL32(255, 255, 255, 232), 5.0f);
    dl->AddRect(vc_pos, ImVec2(vc_pos.x + 154.0f, vc_pos.y + 30.0f), IM_COL32(192, 203, 218, 255), 5.0f);

    const char *labels[4] = {"Top", "Front", "Side", "Iso"};
    const float yaws[4] = {0.0f, 0.0f, 90.0f, 42.0f};
    const float pitches[4] = {84.0f, 2.0f, 2.0f, 28.0f};
    for (int i = 0; i < 4; ++i) {
        const ImVec2 b0(vc_pos.x + 5.0f + i * 37.0f, vc_pos.y + 4.0f);
        const ImVec2 b1(b0.x + 33.0f, b0.y + 22.0f);
        const ImVec2 mp = ImGui::GetIO().MousePos;
        const bool hovered = mp.x >= b0.x && mp.x <= b1.x && mp.y >= b0.y && mp.y <= b1.y;
        dl->AddRectFilled(b0, b1, hovered ? IM_COL32(219, 234, 254, 255) : IM_COL32(241, 245, 249, 255), 3.0f);
        dl->AddText(ImVec2(b0.x + 4.0f, b0.y + 4.0f), IM_COL32(30, 41, 59, 255), labels[i]);
        if (hovered && ImGui::IsMouseClicked(ImGuiMouseButton_Left)) {
            cam.yaw_deg = yaws[i];
            cam.pitch_deg = pitches[i];
        }
    }
}

} // namespace

void AppWorkbench::draw_menu_bar() {
    if (!ImGui::BeginMenuBar()) return;

    if (ImGui::BeginMenu("File")) {
        if (ImGui::MenuItem("New Multirotor")) switch_family(VehicleFamily::Multirotor);
        if (ImGui::MenuItem("New Fixed-Wing Airplane")) switch_family(VehicleFamily::FixedWing);
        if (ImGui::MenuItem("New Helicopter")) switch_family(VehicleFamily::Helicopter);
        if (ImGui::MenuItem("New VTOL Tiltrotor")) switch_family(VehicleFamily::VTOL);
        if (ImGui::MenuItem("New Twin-Float Seaplane")) switch_family(VehicleFamily::Seaplane);
        if (ImGui::MenuItem("New Swept Jet Aircraft")) switch_family(VehicleFamily::Jet);
        if (ImGui::MenuItem("New Insect Micro-Flapper MAV")) switch_family(VehicleFamily::InsectFlapper);
        if (ImGui::MenuItem("New Morphing-Wing Flyer (PigeonBot)")) switch_family(VehicleFamily::MorphingWing);
        if (ImGui::MenuItem("New Cargo Slung-Load Hex (Carrier)")) switch_family(VehicleFamily::CargoUAV);
        if (ImGui::MenuItem("New VTOL Tailsitter (dRehmFlight)")) switch_family(VehicleFamily::Tailsitter);
        if (ImGui::MenuItem("New Swept Flying Wing (Project-Air)")) switch_family(VehicleFamily::FlyingWing);
        if (ImGui::MenuItem("New 2-Stage Rocket / Hypersonic (Phase 4)")) switch_family(VehicleFamily::RocketSpacecraft);
        if (ImGui::MenuItem("New Transonic Airliner (NASA CRM)")) switch_family(VehicleFamily::Airliner);
        if (ImGui::MenuItem("New Custom Part Sketch")) switch_family(VehicleFamily::CustomPart);
        ImGui::Separator();
        if (ImGui::MenuItem("Open Project (.json)...")) {
            const auto path = native_open_file_dialog("Aerodynamics Lab Project", "json");
            if (!path.empty()) {
                std::ifstream ifs(path);
                std::string text((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
                if (!text.empty()) {
                    push_undo_snapshot();
                    if (WorkerIPC::load_project_payload_json(text, params)) {
                        rebuild_geometry();
                        export_banner = "Opened: " + path;
                    } else {
                        export_banner = "Open failed (unsupported JSON): " + path;
                    }
                }
            }
        }
        if (ImGui::MenuItem("Save Project Copy...")) {
            const auto path = native_save_file_dialog("project.json", "JSON Project", "json");
            if (!path.empty()) {
                std::ofstream ofs(path);
                ofs << ipc_->build_project_payload_json(params);
                export_banner = "Saved project snapshot to " + path;
            }
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Build Exact Part STEP/STL/DXF (OCCT Worker)")) {
            ipc_->launch_python_command("build-custom-part",
                                        ipc_->build_part_payload_json(params, repo_root_ / ".local" / "tmp" / "native_exports"));
            show_part_export_modal = true;
        }
        if (ImGui::MenuItem("Export 2D Wing Drawing (SVG / DXF)")) {
            ipc_->launch_python_command("export-drawing",
                                        ipc_->build_drawing_payload_json(params, repo_root_ / ".local" / "tmp" / "native_exports"));
        }
        ImGui::Separator();
        if (ImGui::MenuItem("Exit")) {
            std::exit(0);
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Edit")) {
        if (ImGui::MenuItem("Undo", "Ctrl+Z", false, !undo_stack_.empty())) undo();
        if (ImGui::MenuItem("Redo", "Ctrl+Y", false, !redo_stack_.empty())) redo();
        ImGui::Separator();
        if (ImGui::MenuItem("Reset Camera View")) {
            camera = CameraOrbitState{};
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("View")) {
        if (ImGui::MenuItem("Single 3D Perspective", nullptr, viewport_layout == ViewportLayout::Single3D))
            viewport_layout = ViewportLayout::Single3D;
        if (ImGui::MenuItem("4-Quadrant Engineering View (Top/Side/Front/Iso)", nullptr, viewport_layout == ViewportLayout::Ortho4View))
            viewport_layout = ViewportLayout::Ortho4View;
        ImGui::Separator();
        if (ImGui::MenuItem("Shaded + CAD Edges", nullptr, shading_mode == ShadingMode::ShadedEdges))
            shading_mode = ShadingMode::ShadedEdges;
        if (ImGui::MenuItem("Shaded Smooth", nullptr, shading_mode == ShadingMode::ShadedOnly))
            shading_mode = ShadingMode::ShadedOnly;
        if (ImGui::MenuItem("Wireframe", nullptr, shading_mode == ShadingMode::Wireframe))
            shading_mode = ShadingMode::Wireframe;
        if (ImGui::MenuItem("Aerodynamic Cp Contour", nullptr, shading_mode == ShadingMode::SurfaceCp))
            shading_mode = ShadingMode::SurfaceCp;
        if (ImGui::MenuItem("Structural Von Mises Stress Heatmap", nullptr, shading_mode == ShadingMode::StressVonMises))
            shading_mode = ShadingMode::StressVonMises;
        ImGui::Separator();
        ImGui::MenuItem("Show Vortex & 3D CFD Streamlines", nullptr, &params.show_streamlines);
        ImGui::MenuItem("Show Vortex Wake Lines", nullptr, &show_wake);
        ImGui::MenuItem("Show CoG Datum", nullptr, &show_cog);
        ImGui::MenuItem("Dark Viewport Canvas", nullptr, &dark_canvas);
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Sketch")) {
        if (ImGui::MenuItem("Open Freeform Constraint Sketcher & OCCT Studio", nullptr, freeform_ui.open_window)) {
            freeform_ui.open_window = !freeform_ui.open_window;
            init_default_freeform_sketch(params.active_part);
        }
        if (ImGui::MenuItem("Pick 3D Face as Sketch Plane", "Ctrl+Click", freeform_ui.pick_face_mode)) {
            freeform_ui.pick_face_mode = !freeform_ui.pick_face_mode;
        }
        if (ImGui::MenuItem("New Freeform OCCT Solid Part")) {
            push_undo_snapshot();
            params.active_part.freeform_mode = true;
            params.active_part.sketch_kind = SketchShapeKind::FreeformBrep;
            init_default_freeform_sketch(params.active_part);
            freeform_ui.open_window = true;
            switch_family(VehicleFamily::CustomPart);
            trigger_freeform_occt_build();
        }
        ImGui::Separator();
        if (ImGui::MenuItem("New Rounded Plate / Arm Sketch")) {
            push_undo_snapshot();
            params.active_part.sketch_kind = SketchShapeKind::RoundedPlate;
            params.active_part.revolve_360 = false;
            switch_family(VehicleFamily::CustomPart);
        }
        if (ImGui::MenuItem("New Ducted Shroud / Ring Sketch")) {
            push_undo_snapshot();
            params.active_part.sketch_kind = SketchShapeKind::RingDuct;
            params.active_part.revolve_360 = false;
            switch_family(VehicleFamily::CustomPart);
        }
        if (ImGui::MenuItem("New NACA Airfoil Rib Sketch")) {
            push_undo_snapshot();
            params.active_part.sketch_kind = SketchShapeKind::AirfoilSection;
            params.active_part.revolve_360 = false;
            switch_family(VehicleFamily::CustomPart);
        }
        ImGui::Separator();
        if (ImGui::MenuItem("New Custom Propeller Blade")) {
            push_undo_snapshot();
            params.active_part.sketch_kind = SketchShapeKind::CustomPropeller;
            params.active_part.revolve_360 = false;
            switch_family(VehicleFamily::CustomPart);
        }
        if (ImGui::MenuItem("New Custom Body Shell")) {
            push_undo_snapshot();
            params.active_part.sketch_kind = SketchShapeKind::CustomBodyShell;
            params.active_part.revolve_360 = false;
            switch_family(VehicleFamily::CustomPart);
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Model")) {
        if (ImGui::MenuItem("Attach / Swap Custom Part on Current Aircraft", nullptr, params.attach_custom_part)) {
            push_undo_snapshot();
            params.attach_custom_part = !params.attach_custom_part;
            rebuild_geometry();
        }
        if (ImGui::MenuItem("Toggle 360 deg Revolve Feature", nullptr, params.active_part.revolve_360)) {
            push_undo_snapshot();
            params.active_part.revolve_360 = !params.active_part.revolve_360;
            rebuild_geometry();
        }
        if (ImGui::MenuItem("Quad Circular Pattern (4x)")) {
            push_undo_snapshot();
            params.active_part.circular_pattern_count = 4;
            rebuild_geometry();
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Aero")) {
        if (ImGui::MenuItem("Enable Cp Pressure Surface View")) {
            shading_mode = ShadingMode::SurfaceCp;
        }
        if (ImGui::MenuItem("Run Lifting-Line / Fixed-Wing Solver (Python)")) {
            ipc_->launch_python_command("fixed-wing-sim", ipc_->build_project_payload_json(params));
        }
        if (ImGui::MenuItem("Evaluate Assembly Layout & BOM")) {
            ipc_->launch_python_command("layout-bom", ipc_->build_project_payload_json(params));
        }
        if (ImGui::MenuItem("Export OpenFOAM + CalculiX CFD/FEA Deck")) {
            ipc_->launch_python_command("cfd-fea-export", ipc_->build_project_payload_json(params));
        }
        if (ImGui::MenuItem("Run Multiphysics Audit (Acoustics / VRS / Cav / RCS)")) {
            ipc_->launch_python_command("multiphysics-audit", ipc_->build_project_payload_json(params));
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Flight")) {
        if (ImGui::MenuItem("Run 6-DoF RK4 Flight Simulation (C++20)")) {
            ipc_->run_cpp_rk4_multirotor(params, evidence);
            if (viewport_) viewport_->upload_trajectory_path(evidence.traj_pos_m);
        }
        if (ImGui::MenuItem("Run 6-DoF Fixed-Wing Mission (Python Worker)")) {
            ipc_->launch_python_command("6dof-fixed-wing", ipc_->build_project_payload_json(params));
        }
        if (ImGui::MenuItem("Run VTOL Transition Corridor")) {
            ipc_->launch_python_command("vtol-transition", ipc_->build_project_payload_json(params));
        }
        if (ImGui::MenuItem("Run Helicopter Autorotation Sim")) {
            ipc_->launch_python_command("autorotation-sim", ipc_->build_project_payload_json(params));
        }
        if (ImGui::MenuItem("Run Adverse Weather / Icing Check")) {
            ipc_->launch_python_command("adverse-weather", ipc_->build_project_payload_json(params));
        }
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Verification")) {
        if (ImGui::MenuItem("Open Verification & Benchmark Scorecard")) show_verification_modal = true;
        if (ImGui::MenuItem("Open Failure Atlas (10 Curated Crash Cases)")) show_failure_atlas_modal = true;
        if (ImGui::MenuItem("Run Twin % Source Comparison")) {
            ipc_->launch_python_command("compare-source", ipc_->build_compare_payload_json(params, evidence));
        }
        if (ImGui::MenuItem("Run Bounded Parameter Sweep")) {
            ipc_->launch_python_command("bounded-sweep", ipc_->build_project_payload_json(params));
        }
        if (ImGui::MenuItem("Equations & Physical Limits Reference")) show_equations_modal = true;
        ImGui::EndMenu();
    }

    if (ImGui::BeginMenu("Help")) {
        if (ImGui::MenuItem("About Aerodynamics Lab")) show_about_modal = true;
        ImGui::EndMenu();
    }

    ImGui::EndMenuBar();
}

void AppWorkbench::draw_quick_toolstrip() {
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(6.0f, 4.0f));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(4.0f, 4.0f));
    if (ImGui::Button("Multirotor")) switch_family(VehicleFamily::Multirotor);
    ImGui::SameLine();
    if (ImGui::Button("Fixed-Wing")) switch_family(VehicleFamily::FixedWing);
    ImGui::SameLine();
    if (ImGui::Button("Helicopter")) switch_family(VehicleFamily::Helicopter);
    ImGui::SameLine();
    if (ImGui::Button("VTOL")) switch_family(VehicleFamily::VTOL);
    ImGui::SameLine();
    if (ImGui::Button("Seaplane")) switch_family(VehicleFamily::Seaplane);
    ImGui::SameLine();
    if (ImGui::Button("Jet")) switch_family(VehicleFamily::Jet);
    ImGui::SameLine();
    if (ImGui::Button("Insect MAV")) switch_family(VehicleFamily::InsectFlapper);
    ImGui::SameLine();
    if (ImGui::Button("Morph Wing")) switch_family(VehicleFamily::MorphingWing);
    ImGui::SameLine();
    if (ImGui::Button("Cargo")) switch_family(VehicleFamily::CargoUAV);
    ImGui::SameLine();
    if (ImGui::Button("Tailsitter")) switch_family(VehicleFamily::Tailsitter);
    ImGui::SameLine();
    if (ImGui::Button("FlyWing")) switch_family(VehicleFamily::FlyingWing);
    ImGui::SameLine();
    if (ImGui::Button("Rocket")) switch_family(VehicleFamily::RocketSpacecraft);
    ImGui::SameLine();
    if (ImGui::Button("Airliner")) switch_family(VehicleFamily::Airliner);
    ImGui::SameLine();
    if (ImGui::Button("Part Designer")) switch_family(VehicleFamily::CustomPart);

    // Row 2: CAD Assembly, Motion, Multiphysics & Solver Tools
    if (ImGui::Button(freeform_ui.open_window ? "Sketcher: ON" : "Sketch 2D/OCCT")) {
        freeform_ui.open_window = !freeform_ui.open_window;
        init_default_freeform_sketch(params.active_part);
    }
    ImGui::SameLine();
    if (ImGui::Button(freeform_ui.pick_face_mode ? "Pick Face: ON" : "Pick Face")) {
        freeform_ui.pick_face_mode = !freeform_ui.pick_face_mode;
    }
    ImGui::SameLine();
    if (ImGui::Button(params.explode_factor > 0.1f ? "Assemble" : "Explode")) {
        params.explode_factor = (params.explode_factor > 0.1f) ? 0.0f : 1.0f;
        rebuild_geometry();
    }
    ImGui::SameLine();
    if (ImGui::Button(params.motion_study_active ? "Motion: ON" : "Motion")) {
        params.motion_study_active = !params.motion_study_active;
    }
    ImGui::SameLine();
    if (ImGui::Button("Failure Atlas")) show_failure_atlas_modal = true;
    ImGui::SameLine();
    if (ImGui::Button(params.show_rc_hud ? "RC HUD: ON" : "RC Stick")) {
        params.show_rc_hud = !params.show_rc_hud;
    }
    ImGui::SameLine();
    if (ImGui::Button(viewport_layout == ViewportLayout::Single3D ? "4-View" : "Single 3D")) {
        viewport_layout = (viewport_layout == ViewportLayout::Single3D) ? ViewportLayout::Ortho4View : ViewportLayout::Single3D;
    }
    ImGui::SameLine();
    const char *shade_lbl = (shading_mode == ShadingMode::SurfaceCp) ? "Stress FEA" : (shading_mode == ShadingMode::StressVonMises ? "CAD Edges" : "Cp Map");
    if (ImGui::Button(shade_lbl)) {
        shading_mode = (shading_mode == ShadingMode::SurfaceCp) ? ShadingMode::StressVonMises
                                                                 : (shading_mode == ShadingMode::StressVonMises ? ShadingMode::ShadedEdges : ShadingMode::SurfaceCp);
    }
    ImGui::SameLine();
    if (ImGui::Button("Export CFD/FEA")) {
        ipc_->launch_python_command("cfd-fea-export", ipc_->build_project_payload_json(params));
    }
    ImGui::SameLine();
    if (ImGui::Button("Run 6-DoF")) {
        ipc_->run_cpp_rk4_multirotor(params, evidence);
        if (viewport_) viewport_->upload_trajectory_path(evidence.traj_pos_m);
    }
    ImGui::SameLine();
    if (ImGui::Button("Reset")) {
        camera = CameraOrbitState{};
    }
    ImGui::PopStyleVar(2);
    ImGui::Separator();
}

void AppWorkbench::draw_left_feature_tree() {
    ImGui::Begin("Model & Feature Tree");
    ImGui::Text("Project: %s", params.project_name.c_str());
    ImGui::Separator();

    if (ImGui::CollapsingHeader("Feature History", ImGuiTreeNodeFlags_DefaultOpen)) {
        for (std::size_t i = 0; i < feature_tree.size(); ++i) {
            auto &node = feature_tree[i];
            ImGui::PushID(static_cast<int>(i));
            ImGui::BulletText("[%s] %s", node.kind.c_str(), node.label.c_str());
            ImGui::PopID();
        }
        if (ImGui::Button("Undo", ImVec2(64, 0))) undo();
        ImGui::SameLine();
        if (ImGui::Button("Redo", ImVec2(64, 0))) redo();
    }

    ImGui::Spacing();
    if (ImGui::CollapsingHeader("Assembly Components", ImGuiTreeNodeFlags_DefaultOpen)) {
        for (int i = 0; i < static_cast<int>(scene.assembly_parts.size()); ++i) {
            const auto &part = scene.assembly_parts[i];
            char label[160];
            std::snprintf(label, sizeof(label), "%s  (%.3f kg)", part.name.c_str(), part.mass_kg);
            if (ImGui::Selectable(label, selected_part_idx == i)) {
                selected_part_idx = (selected_part_idx == i) ? -1 : i;
                rebuild_geometry();
            }
        }
    }

    ImGui::Spacing();
    if (ImGui::CollapsingHeader("Worker Status", ImGuiTreeNodeFlags_DefaultOpen)) {
        const auto st = ipc_->snapshot_status();
        ImGui::TextColored(st.last_ok ? ImVec4(0.10f, 0.42f, 0.25f, 1.0f) : ImVec4(0.80f, 0.16f, 0.16f, 1.0f),
                           "%s", st.last_ok ? "Worker Ready / OK" : "Worker Warning / Error");
        ImGui::TextWrapped("%s", st.summary_line.c_str());
        if (!export_banner.empty()) {
            ImGui::Separator();
            ImGui::TextWrapped("%s", export_banner.c_str());
        }
    }
    ImGui::End();
}

void AppWorkbench::draw_center_viewport(float dt_s) {
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
    ImGui::Begin("3D CAD Viewport");

    std::array<double, 3> v_pos{0.0, 0.0, 0.0};
    std::array<double, 4> v_quat{1.0, 0.0, 0.0, 0.0};
    if (evidence.has_trajectory && !evidence.traj_pos_m.empty()) {
        if (evidence.playing) {
            evidence.playback_time_s += dt_s;
            if (evidence.playback_time_s > evidence.duration_s) evidence.playback_time_s = 0.0f;
        }
        const float u = evidence.duration_s > 0.0f ? (evidence.playback_time_s / evidence.duration_s) : 0.0f;
        const std::size_t idx = std::min(evidence.traj_pos_m.size() - 1,
                                         static_cast<std::size_t>(u * static_cast<float>(evidence.traj_pos_m.size() - 1)));
        v_pos = evidence.traj_pos_m[idx];
        v_quat = evidence.traj_quat_wxyz[idx];
    }

    const ImVec2 avail = ImGui::GetContentRegionAvail();
    const float bar_h = evidence.has_trajectory ? 34.0f : 0.0f;
    last_vp_w_ = std::max(64, static_cast<int>(avail.x));
    last_vp_h_ = std::max(64, static_cast<int>(avail.y - bar_h));

    viewport_->render(last_vp_w_, last_vp_h_, camera, viewport_layout, shading_mode, dark_canvas,
                      show_wake, show_cog, evidence.center_of_mass_m, v_pos, v_quat);

    const ImVec2 vp_pos = ImGui::GetCursorScreenPos();
    const ImVec2 vp_size(static_cast<float>(last_vp_w_), static_cast<float>(last_vp_h_));
    ImGui::Image(static_cast<ImTextureID>(viewport_->texture_id()), vp_size, ImVec2(0, 1), ImVec2(1, 0));

    if (ImGui::IsItemHovered()) {
        const ImGuiIO &io = ImGui::GetIO();
        if ((freeform_ui.pick_face_mode || io.KeyCtrl) && ImGui::IsMouseClicked(ImGuiMouseButton_Left)) {
            const auto hit = pick_face_under_cursor(
                scene, brep_cache, camera, viewport_layout, last_vp_w_, last_vp_h_,
                io.MousePos.x - vp_pos.x, io.MousePos.y - vp_pos.y);
            if (hit.hit) {
                push_undo_snapshot();
                params.active_part.picked_face_id = hit.face_id;
                params.active_part.active_workplane = hit.workplane;
                params.active_part.freeform_sketch.workplane = hit.workplane;
                freeform_ui.open_window = true;
                freeform_ui.pick_face_mode = false;
                export_banner = "Picked 3D Face #" + std::to_string(hit.face_id) + " as active sketch plane";
                rebuild_geometry();
            }
        }
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Right) || ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
            if (!io.KeyShift) {
                camera.yaw_deg -= io.MouseDelta.x * 0.45f;
                camera.pitch_deg = std::clamp(camera.pitch_deg + io.MouseDelta.y * 0.40f, -82.0f, 82.0f);
            } else {
                camera.target_m[2] += io.MouseDelta.y * 0.002f;
            }
        }
        if (io.MouseWheel != 0.0f) {
            camera.distance_m = std::clamp(camera.distance_m * std::pow(0.90f, io.MouseWheel), 0.35f, 14.0f);
        }
    }

    draw_view_cube_and_triad(ImGui::GetWindowDrawList(), vp_pos, vp_size, camera, viewport_layout);

    if (evidence.has_trajectory) {
        ImGui::SetCursorPos(ImVec2(8.0f, vp_size.y + 6.0f));
        if (ImGui::Button(evidence.playing ? "Pause" : "Play")) {
            evidence.playing = !evidence.playing;
        }
        ImGui::SameLine();
        ImGui::SetNextItemWidth(std::max(120.0f, vp_size.x - 210.0f));
        ImGui::SliderFloat("t (s)", &evidence.playback_time_s, 0.0f, std::max(0.1f, evidence.duration_s), "%.2f s");
        ImGui::SameLine();
        if (ImGui::Button("Clear Replay")) {
            evidence.has_trajectory = false;
            evidence.playing = false;
        }
    }

    ImGui::End();
    ImGui::PopStyleVar();
}

void AppWorkbench::draw_right_inspector() {
    ImGui::Begin("Parameters & Evidence");

    bool changed = false;
    ImGui::PushItemWidth(ImGui::GetContentRegionAvail().x * 0.48f);
    if (ImGui::CollapsingHeader("Live Design Parameters", ImGuiTreeNodeFlags_DefaultOpen)) {
        if (params.family == VehicleFamily::Multirotor) {
            changed |= ImGui::SliderInt("Rotors", &params.rotor_count, 3, 8);
            changed |= ImGui::SliderFloat("Arm Length (m)", &params.arm_length_m, 0.14f, 0.65f, "%.3f");
            changed |= ImGui::SliderFloat("Prop Diameter (m)", &params.prop_diameter_m, 0.15f, 0.65f, "%.3f");
            changed |= ImGui::SliderFloat("Blade Pitch (deg)", &params.prop_pitch_deg, 6.0f, 28.0f, "%.1f");
            changed |= ImGui::SliderInt("Prop Blades", &params.prop_blades, 2, 5);
        } else if (params.family == VehicleFamily::CargoUAV) {
            changed |= ImGui::SliderFloat("Arm Length (m)", &params.arm_length_m, 0.22f, 0.70f, "%.3f");
            changed |= ImGui::SliderFloat("Cargo Mass (kg)", &params.cargo_mass_kg, 0.0f, 12.0f, "%.2f");
            changed |= ImGui::SliderFloat("Cable Length (m)", &params.cable_length_m, 0.25f, 2.50f, "%.2f");
            changed |= ImGui::Checkbox("Release Slung Parcel", &params.payload_released);
        } else if (params.family == VehicleFamily::Tailsitter) {
            changed |= ImGui::SliderFloat("Wingspan (m)", &params.wingspan_m, 0.55f, 2.40f, "%.2f");
            changed |= ImGui::SliderFloat("Transition Pitch (deg)", &params.transition_pitch_deg, 0.0f, 90.0f, "%.0f");
            changed |= ImGui::SliderFloat("Duct Area Ratio", &params.duct_area_ratio, 1.0f, 1.50f, "%.2f");
            changed |= ImGui::SliderFloat("Prop Diameter (m)", &params.prop_diameter_m, 0.16f, 0.50f, "%.3f");
        } else if (params.family == VehicleFamily::FixedWing || params.family == VehicleFamily::VTOL ||
                   params.family == VehicleFamily::Seaplane || params.family == VehicleFamily::Jet ||
                   params.family == VehicleFamily::FlyingWing || params.family == VehicleFamily::Airliner) {
            changed |= ImGui::SliderFloat("Wingspan (m)", &params.wingspan_m, 0.5f, 3.8f, "%.2f");
            changed |= ImGui::SliderFloat("Root Chord (m)", &params.root_chord_m, 0.10f, 0.60f, "%.3f");
            changed |= ImGui::SliderFloat("Tip Chord (m)", &params.tip_chord_m, 0.05f, 0.45f, "%.3f");
            changed |= ImGui::SliderFloat("Sweep (deg)", &params.sweep_deg, -10.0f, 45.0f, "%.1f");
            changed |= ImGui::SliderFloat("Dihedral (deg)", &params.dihedral_deg, -5.0f, 12.0f, "%.1f");
            changed |= ImGui::SliderFloat("Washout Twist (deg)", &params.twist_tip_deg, -6.0f, 4.0f, "%.1f");
            if (params.family == VehicleFamily::VTOL) {
                changed |= ImGui::SliderFloat("Rotor Tilt (deg)", &params.vtol_tilt_deg, 0.0f, 90.0f, "%.0f");
            }
            if (params.family == VehicleFamily::Seaplane) {
                changed |= ImGui::SliderFloat("Float Beam (m)", &params.float_beam_m, 0.06f, 0.30f, "%.3f");
                changed |= ImGui::SliderFloat("Deadrise (deg)", &params.float_deadrise_deg, 8.0f, 30.0f, "%.0f");
                changed |= ImGui::SliderFloat("Water Chop (m)", &params.water_chop_m, 0.0f, 0.20f, "%.3f");
            }
            if (params.family == VehicleFamily::Jet) {
                changed |= ImGui::SliderFloat("Jet Throt (%)", &params.jet_throttle_pct, 20.0f, 105.0f, "%.0f");
                changed |= ImGui::Checkbox("Afterburner (1.55x Wet)", &params.jet_afterburner);
                changed |= ImGui::Checkbox("Ramjet / Scramjet M2-6", &params.jet_ramjet);
                changed |= ImGui::SliderFloat("Wing t/c", &params.wing_tc_ratio, 0.04f, 0.16f, "%.3f");
                changed |= ImGui::SliderFloat("Intake Area (m2)", &params.intake_area_m2, 0.0010f, 0.0100f, "%.4f");
                changed |= ImGui::SliderFloat("Nozzle Ae/At", &params.nozzle_area_ratio, 0.75f, 2.00f, "%.2f");
                changed |= ImGui::SliderFloat("Fuel Mass (kg)", &params.fuel_mass_kg, 0.10f, 4.00f, "%.2f");
            } else if (params.family == VehicleFamily::Airliner) {
                changed |= ImGui::SliderFloat("Cruise Throt (%)", &params.jet_throttle_pct, 20.0f, 105.0f, "%.0f");
                changed |= ImGui::SliderFloat("Wing t/c", &params.wing_tc_ratio, 0.07f, 0.14f, "%.3f");
            }
            const char *airfoils[] = {"2412", "0012", "4412", "23012", "6412"};
            for (int a = 0; a < 5; ++a) {
                if (a > 0) ImGui::SameLine();
                if (ImGui::SmallButton(airfoils[a])) {
                    params.airfoil_code = airfoils[a];
                    changed = true;
                }
            }
        } else if (params.family == VehicleFamily::InsectFlapper) {
            changed |= ImGui::SliderFloat("Span (m)", &params.wingspan_m, 0.08f, 0.45f, "%.3f");
            changed |= ImGui::SliderFloat("Flap Freq (Hz)", &params.flap_freq_hz, 8.0f, 160.0f, "%.0f");
            changed |= ImGui::SliderFloat("Stroke Amp (deg)", &params.stroke_amp_deg, 25.0f, 90.0f, "%.0f");
            changed |= ImGui::SliderFloat("Morph Tuck (%)", &params.morph_tuck_pct, 0.0f, 80.0f, "%.0f");
            changed |= ImGui::Checkbox("Animate Wingbeat", &params.animate_flapping);
        } else if (params.family == VehicleFamily::MorphingWing) {
            changed |= ImGui::SliderFloat("Wingspan (m)", &params.wingspan_m, 0.60f, 2.40f, "%.2f");
            changed |= ImGui::SliderFloat("Morph Tuck (%)", &params.morph_tuck_pct, 0.0f, 80.0f, "%.0f");
            changed |= ImGui::SliderFloat("Wing Asym Roll", &params.wing_asymmetry_diff, -0.45f, 0.45f, "%.2f");
            changed |= ImGui::SliderFloat("Tail Spread (%)", &params.tail_spread_pct, 0.0f, 100.0f, "%.0f");
            changed |= ImGui::SliderFloat("Tail Tilt (deg)", &params.tail_tilt_deg, -25.0f, 25.0f, "%.1f");
        } else if (params.family == VehicleFamily::Helicopter) {
            changed |= ImGui::SliderFloat("Main Rotor Dia (m)", &params.main_rotor_diameter_m, 0.8f, 2.8f, "%.2f");
            changed |= ImGui::SliderFloat("Tail Boom (m)", &params.tail_boom_length_m, 0.45f, 1.5f, "%.2f");
            changed |= ImGui::SliderInt("Main Blades", &params.prop_blades, 2, 5);
        }

        if (params.family == VehicleFamily::CustomPart || params.attach_custom_part) {
            ImGui::Separator();
            changed |= draw_interactive_2d_sketch_canvas(params.active_part);
            ImGui::Text("Custom Part Sketch & Solid Feature:");
            const char *kinds[] = {"Rounded Arm/Plate", "Ring Duct", "NACA Airfoil Rib",
                                   "Hex Mount",         "Custom Propeller", "Custom Body Shell", "Freeform OCCT B-Rep"};
            int k = static_cast<int>(params.active_part.sketch_kind);
            if (ImGui::Combo("Sketch Profile", &k, kinds, 7)) {
                params.active_part.sketch_kind = static_cast<SketchShapeKind>(k);
                params.active_part.freeform_mode = (params.active_part.sketch_kind == SketchShapeKind::FreeformBrep);
                if (params.active_part.freeform_mode) init_default_freeform_sketch(params.active_part);
                changed = true;
            }
            if (ImGui::Button("Open Freeform Constraint Sketcher")) {
                freeform_ui.open_window = true;
                init_default_freeform_sketch(params.active_part);
            }
            if (ImGui::Button("Build OCCT Solid (STEP/STL/B-Rep)")) {
                params.active_part.freeform_mode = true;
                params.active_part.sketch_kind = SketchShapeKind::FreeformBrep;
                trigger_freeform_occt_build();
            }
            changed |= ImGui::SliderFloat("Part Length (m)", &params.active_part.length_m, 0.04f, 0.60f, "%.3f");
            changed |= ImGui::SliderFloat("Part Width (m)", &params.active_part.width_m, 0.015f, 0.25f, "%.3f");
            changed |= ImGui::SliderFloat("Thickness (m)", &params.active_part.thickness_m, 0.004f, 0.08f, "%.3f");
            changed |= ImGui::SliderFloat("Cut Hole R (m)", &params.active_part.hole_radius_m, 0.0f, 0.06f, "%.3f");
            changed |= ImGui::Checkbox("360 deg Revolve", &params.active_part.revolve_360);
            changed |= ImGui::SliderInt("Circular Pattern", &params.active_part.circular_pattern_count, 1, 8);
            if (params.family == VehicleFamily::CustomPart && ImGui::Button("Test Part in Multirotor Sim")) {
                push_undo_snapshot();
                params.attach_custom_part = true;
                switch_family(VehicleFamily::Multirotor);
            }
        }

        if (params.family != VehicleFamily::RocketSpacecraft) {
            ImGui::Separator();
            ImGui::TextDisabled("Preloaded Hardware (Select Only):");
            const char *hw_items[] = {"MN3508 + 6S 10Ah", "ECOII 2807 + 4S", "70mm 12B EDF 6S",
                                      "Micro Coreless 1S", "KingTech K-45G4 45N", "JetCat P100-RX 100N"};
            if (ImGui::Combo("Catalog Power", &params.hardware_catalog_idx, hw_items, 6)) {
                push_undo_snapshot();
                if (params.hardware_catalog_idx == 0) {
                    params.battery_cells_s = 6; params.battery_capacity_ah = 10.0f; params.battery_r0_ohm = 0.025f; params.battery_mass_kg = 1.55f;
                } else if (params.hardware_catalog_idx == 1) {
                    params.battery_cells_s = 4; params.battery_capacity_ah = 4.5f; params.battery_r0_ohm = 0.018f; params.battery_mass_kg = 0.55f;
                } else if (params.hardware_catalog_idx == 2) {
                    params.battery_cells_s = 6; params.battery_capacity_ah = 5.0f; params.battery_r0_ohm = 0.015f; params.battery_mass_kg = 0.78f;
                } else if (params.hardware_catalog_idx == 3) {
                    params.battery_cells_s = 1; params.battery_capacity_ah = 0.5f; params.battery_r0_ohm = 0.065f; params.battery_mass_kg = 0.012f;
                } else if (params.hardware_catalog_idx == 4) {
                    params.battery_cells_s = 2; params.battery_capacity_ah = 2.2f; params.battery_r0_ohm = 0.020f; params.battery_mass_kg = 0.90f;
                } else {
                    params.battery_cells_s = 3; params.battery_capacity_ah = 3.0f; params.battery_r0_ohm = 0.020f; params.battery_mass_kg = 1.45f;
                }
                changed = true;
            }
            changed |= ImGui::SliderFloat("Battery Mass (kg)", &params.battery_mass_kg, 0.01f, 4.5f, "%.2f");
            changed |= ImGui::SliderFloat("Payload Mass (kg)", &params.payload_mass_kg, 0.0f, 15.0f, "%.2f");
            changed |= ImGui::SliderFloat("Alpha (deg)", &params.alpha_deg, -4.0f, 16.0f, "%.1f");
            const float max_spd = (params.family == VehicleFamily::Jet)
                                      ? (params.jet_ramjet ? 2200.0f : 560.0f)
                                      : (params.family == VehicleFamily::Airliner ? 340.0f : 45.0f);
            changed |= ImGui::SliderFloat("Airspeed (m/s)", &params.airspeed_m_s, 1.0f, max_spd, "%.1f");
            ImGui::Separator();
            ImGui::TextDisabled("Standards Fasteners & Harness BOM:");
            const char *screw_sizes[] = {"M2 (ISO 4762)", "M2.5 (ISO 4762)", "M3 (ISO 4762)", "M4 (ISO 4762)", "M5 (ISO 4762)", "M6 (ISO 4762)"};
            changed |= ImGui::Combo("Joint Screw", &params.screw_size_idx, screw_sizes, 6);
            changed |= ImGui::Checkbox("Ti-6Al-4V Fasteners", &params.titanium_screws);
            changed |= ImGui::SliderInt("Power Wire (AWG)", &params.wire_awg, 10, 22);
            changed |= ImGui::SliderFloat("Exploded View", &params.explode_factor, 0.0f, 1.5f, "%.2f");
            changed |= ImGui::SliderFloat("RF Range (km)", &params.rf_distance_km, 0.2f, 25.0f, "%.1f");
            changed |= ImGui::Checkbox("Stealth RCS Shaping", &params.stealth_shaping);
        }
        if (params.family == VehicleFamily::Helicopter) {
            changed |= ImGui::SliderFloat("Descent Rate (m/s)", &params.heli_descent_m_s, -10.0f, 5.0f, "%.1f");
        } else if (params.family == VehicleFamily::RocketSpacecraft) {
            changed |= ImGui::Checkbox("Saturn V 3-Stage AS-506", &params.rocket_saturn_v_preset);
            changed |= ImGui::SliderFloat("Payload Mass (kg)", &params.payload_mass_kg, 50.0f, 50000.0f, "%.0f");
            changed |= ImGui::SliderFloat("Stage 1 Prop (kg)", &params.rocket_stage1_prop_kg, 2000.0f, 35000.0f, "%.0f");
            changed |= ImGui::SliderFloat("Thrust (kN)", &params.rocket_thrust_kn, 150.0f, 750.0f, "%.0f");
            changed |= ImGui::SliderFloat("Nose Heatshield R (m)", &params.rocket_nose_radius_m, 0.15f, 1.60f, "%.2f");
            changed |= ImGui::SliderFloat("Re-entry (km/s)", &params.reentry_speed_km_s, 2.0f, 11.2f, "%.2f");
            changed |= ImGui::SliderFloat("Exploded View", &params.explode_factor, 0.0f, 1.5f, "%.2f");
        }
    }

    ImGui::Spacing();
    if (ImGui::CollapsingHeader("C++20 Physics & Electronics", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::Text("Mass: %.3f kg | T/W: %.2fx", evidence.total_mass_kg, evidence.thrust_to_weight);
        ImGui::Text("Throt: %.0f%% | Hover: %.0f min", evidence.hover_throttle_pct, evidence.est_endurance_min);
        ImGui::Text("Pack: %.1f V | %.1f A | %.0f C", evidence.loaded_bus_voltage_v, evidence.hover_or_cruise_current_a, evidence.motor_temp_c);
        ImGui::Text("Wind: %.1f m/s | Rho: %.3f | FoS: %.2fx", evidence.wind_speed_m_s, evidence.air_density_kg_m3, evidence.structural_fos);
        ImGui::Text("Bolt: %.1fx | Wire: %.2fV [<=%.0fA]", evidence.bolt_shear_fos, evidence.wire_drop_v, evidence.wire_ampacity_a);
        if (params.family == VehicleFamily::RocketSpacecraft) {
            ImGui::Text("Delta-V: %.0f m/s | Orbit: %s", evidence.rocket_dv_m_s, evidence.rocket_orbit_ok ? "LEO OK" : "Suborbital");
            ImGui::Text("TPS: %.0f C | Kn: %.4f", evidence.rocket_tps_c, evidence.rocket_kn);
        } else {
            ImGui::Text("SPL: %.1f dBA | RF: %.1f dB | RCS: %.1f dBsm", evidence.spl_dba, evidence.rf_margin_db, evidence.rcs_dbsm);
        }
        if (params.family == VehicleFamily::Helicopter) {
            ImGui::Text("mu: %.2f | Gyro: %.1f Nm | VRS: %s", evidence.heli_mu, evidence.heli_gyro_nm, evidence.heli_vrs ? "FAIL" : "OK");
        } else if (params.family == VehicleFamily::Jet) {
            ImGui::Text("M: %.2f | MDD: %.2f | eta_r: %.3f | T_aw: %.0fC", evidence.mach, evidence.m_dd, evidence.inlet_recovery_eta, evidence.skin_temp_c);
        } else if (params.family == VehicleFamily::Airliner) {
            ImGui::Text("M: %.2f | Cabin dP: %.1fkPa | Hoop FoS: %.2fx", evidence.mach, evidence.cabin_delta_p_kpa, evidence.hoop_fos);
        } else if (params.family == VehicleFamily::CargoUAV) {
            ImGui::Text("Trail: %.1f deg | Pendulum: %.2f Hz | Clr: %.0fmm", evidence.trail_angle_deg, evidence.pendulum_hz, evidence.min_tip_clearance_m * 1000.0);
        } else if (params.family == VehicleFamily::Tailsitter) {
            ImGui::Text("Propwash Slip: %.1f m/s", evidence.propwash_slip_m_s);
        } else if (params.family == VehicleFamily::Seaplane) {
            ImGui::Text("Water Hump Drag: %.2f N", evidence.hump_resistance_n);
        } else if (params.family == VehicleFamily::InsectFlapper || params.family == VehicleFamily::MorphingWing) {
            ImGui::Text("C(k): %.2f | Phi: %.2f | St: %.2f", evidence.theodorsen_ck, evidence.wagner_phi, evidence.strouhal);
            ImGui::Text("Tip: %.1fmm | f1: %.0fHz | qD: %.0fx",
                        evidence.flex_tip_deflection_mm, evidence.first_bending_mode_hz, evidence.divergence_margin);
            if (params.family == VehicleFamily::MorphingWing) {
                ImGui::Text("Roll: %.2f Nm | Yaw Cn: %.3f", evidence.roll_moment_nm, evidence.yaw_damping_cn);
            }
        } else if (params.family != VehicleFamily::RocketSpacecraft) {
            ImGui::Text("Clearance: %.0f mm (%s)", evidence.min_tip_clearance_m * 1000.0,
                        evidence.clearance_ok ? "OK" : "FAIL");
        }
        if (params.family != VehicleFamily::RocketSpacecraft) {
            ImGui::Text("CL: %.2f | CD: %.3f | L/D: %.1f", evidence.cl, evidence.cd, evidence.lift_to_drag);
        }
        draw_polar_plot(evidence);
    }

    ImGui::Spacing();
    if (ImGui::CollapsingHeader("Virtual vs Real Evidence", ImGuiTreeNodeFlags_DefaultOpen)) {
        const ImVec4 badge_col = (evidence.validation_status == "FAIL")
                                     ? ImVec4(0.82f, 0.16f, 0.16f, 1.0f)
                                     : (evidence.validation_status == "UNVALIDATED_CUSTOM"
                                            ? ImVec4(0.75f, 0.45f, 0.08f, 1.0f)
                                            : ImVec4(0.10f, 0.42f, 0.80f, 1.0f));
        ImGui::TextColored(badge_col, "Status: %s", evidence.validation_status.c_str());

        char ready_buf[48];
        std::snprintf(ready_buf, sizeof(ready_buf), "Readiness: %.1f%%", evidence.predicted_readiness_pct);
        ImGui::PushStyleColor(ImGuiCol_PlotHistogram,
                              evidence.predicted_readiness_pct >= 75.0
                                  ? ImVec4(0.13f, 0.62f, 0.32f, 1.0f)
                                  : (evidence.predicted_readiness_pct > 0.0 ? ImVec4(0.85f, 0.55f, 0.10f, 1.0f) : ImVec4(0.82f, 0.16f, 0.16f, 1.0f)));
        ImGui::ProgressBar(static_cast<float>(evidence.predicted_readiness_pct / 100.0), ImVec2(-1.0f, 18.0f), ready_buf);
        ImGui::PopStyleColor();

        if (evidence.benchmark_match_pct >= 0.0) {
            char bench_buf[48];
            std::snprintf(bench_buf, sizeof(bench_buf), "Benchmark Match: %.1f%%", evidence.benchmark_match_pct);
            ImGui::PushStyleColor(ImGuiCol_PlotHistogram, ImVec4(0.15f, 0.39f, 0.92f, 1.0f));
            ImGui::ProgressBar(static_cast<float>(evidence.benchmark_match_pct / 100.0), ImVec2(-1.0f, 18.0f), bench_buf);
            ImGui::PopStyleColor();
        } else {
            ImGui::TextColored(ImVec4(0.75f, 0.45f, 0.08f, 1.0f), "Benchmark Match: N/A (%s)", evidence.benchmark_source_tag.c_str());
        }
        ImGui::TextWrapped("%s", evidence.status_detail.c_str());
    }

    ImGui::Spacing();
    if (ImGui::CollapsingHeader("What-If Stress & Overload")) {
        if (ImGui::SmallButton("Nominal")) {
            push_undo_snapshot();
            switch_family(params.family);
            params.rain_mm_h = 0.0f;
            params.oat_c = 25.0f;
            params.wind_x_m_s = 0.0f;
            params.wind_y_m_s = 0.0f;
            params.turbulence_pct = 10.0f;
            params.mfg_tolerance_pct = 5.0f;
            params.altitude_asl_m = 0.0f;
            params.motor_cooling_grade = 1;
            changed = true;
        }
        ImGui::SameLine();
        if (ImGui::SmallButton("Overload")) {
            push_undo_snapshot();
            params.payload_mass_kg = (params.family == VehicleFamily::InsectFlapper) ? 0.06f : 9.5f;
            changed = true;
        }
        ImGui::SameLine();
        if (ImGui::SmallButton("Overspeed")) {
            push_undo_snapshot();
            if (params.family == VehicleFamily::InsectFlapper) {
                params.flap_freq_hz = 160.0f;
            } else if (params.family == VehicleFamily::Jet) {
                params.airspeed_m_s = 325.0f;
                params.jet_throttle_pct = 105.0f;
            } else if (params.family == VehicleFamily::FixedWing || params.family == VehicleFamily::Seaplane ||
                       params.family == VehicleFamily::MorphingWing) {
                params.airspeed_m_s = 68.0f;
                params.rotor_rpm = 13500.0f;
            } else {
                params.rotor_rpm = 13500.0f;
            }
            changed = true;
        }
        if (ImGui::SmallButton("Weak Pack")) {
            push_undo_snapshot();
            params.battery_r0_ohm = 0.24f;
            changed = true;
        }
        ImGui::SameLine();
        if (ImGui::SmallButton("Storm Wind")) {
            push_undo_snapshot();
            params.wind_x_m_s = 14.0f;
            params.wind_y_m_s = 6.0f;
            params.turbulence_pct = 35.0f;
            params.rain_mm_h = 25.0f;
            changed = true;
        }
        ImGui::SameLine();
        if (ImGui::SmallButton("Bad Tolerance")) {
            push_undo_snapshot();
            params.mfg_tolerance_pct = 20.0f;
            params.motor_cooling_grade = 0;
            changed = true;
        }
        changed |= ImGui::SliderFloat("Wind X (m/s)", &params.wind_x_m_s, -25.0f, 25.0f, "%.1f");
        changed |= ImGui::SliderFloat("Wind Y (m/s)", &params.wind_y_m_s, -25.0f, 25.0f, "%.1f");
        changed |= ImGui::SliderFloat("Gust/Turb (%)", &params.turbulence_pct, 0.0f, 50.0f, "%.0f");
        changed |= ImGui::SliderFloat("Mfg Tol (%)", &params.mfg_tolerance_pct, 0.0f, 25.0f, "%.0f");
        const float max_alt = (params.family == VehicleFamily::Jet || params.family == VehicleFamily::Airliner ||
                               params.family == VehicleFamily::RocketSpacecraft)
                                  ? 35000.0f
                                  : 4000.0f;
        changed |= ImGui::SliderFloat("Alt ASL (m)", &params.altitude_asl_m, 0.0f, max_alt, "%.0f");
        const char *cooling_grades[] = {"Poor", "Medium", "Good"};
        changed |= ImGui::Combo("Motor Cooling", &params.motor_cooling_grade, cooling_grades, 3);
        changed |= ImGui::SliderFloat("Rotor RPM", &params.rotor_rpm, 800.0f, 16000.0f, "%.0f");
        changed |= ImGui::SliderInt("Cells (S)", &params.battery_cells_s, 1, 12);
        changed |= ImGui::SliderFloat("Cap (Ah)", &params.battery_capacity_ah, 0.2f, 30.0f, "%.2f");
        changed |= ImGui::SliderFloat("R0 (Ohm)", &params.battery_r0_ohm, 0.008f, 0.300f, "%.3f");
        changed |= ImGui::SliderFloat("Rain mm/h", &params.rain_mm_h, 0.0f, 80.0f, "%.0f");
        changed |= ImGui::SliderFloat("Temp (C)", &params.oat_c, -20.0f, 45.0f, "%.0f");
    }
    ImGui::PopItemWidth();

    if (changed) {
        rebuild_geometry();
    }

    ImGui::End();
}

void AppWorkbench::draw_modals() {
    if (show_verification_modal) {
        ImGui::OpenPopup("Verification & Benchmark Scorecard");
        show_verification_modal = false;
    }
    if (ImGui::BeginPopupModal("Verification & Benchmark Scorecard", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::Text("Authoritative Local Verification (Zero HTTP Server / Zero Game Engine)");
        ImGui::Separator();
        ImGui::BulletText("C++20 lab_core: mass/CoG, tip clearance, and 6-DoF RK4 run natively.");
        ImGui::BulletText("Pinned Campaigns: SIT battery, UIUC propeller, QDrone, Fixed-Wing, Rotorcraft -> DEVELOPMENT.");
        ImGui::BulletText("Physical validation remains explicit until real matched test logs pass held-out criteria.");
        if (ImGui::Button("Run Twin % Source Comparison")) {
            ipc_->launch_python_command("compare-source", ipc_->build_compare_payload_json(params, evidence));
        }
        ImGui::SameLine();
        if (ImGui::Button("Run Bounded Parameter Sweep")) {
            ipc_->launch_python_command("bounded-sweep", ipc_->build_project_payload_json(params));
        }
        ImGui::SameLine();
        if (ImGui::Button("Close")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (show_part_export_modal) {
        ImGui::OpenPopup("CAD Part Build Worker");
        show_part_export_modal = false;
    }
    if (ImGui::BeginPopupModal("CAD Part Build Worker", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        const auto st = ipc_->snapshot_status();
        ImGui::TextWrapped("%s", st.summary_line.c_str());
        if (ImGui::Button("Close")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (show_equations_modal) {
        ImGui::OpenPopup("Aerospace Equations & Assumptions");
        show_equations_modal = false;
    }
    if (ImGui::BeginPopupModal("Aerospace Equations & Assumptions", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::Text("1. Coordinates: Right-handed SI (+X fwd, +Y left, +Z up), active Hamilton wxyz quaternions.");
        ImGui::Text("2. Aero: Prandtl lifting-line (M <= 0.30) & annular BEMT + Prandtl tip-loss (M_tip <= 0.70).");
        ImGui::Text("3. Electronics: 2-RC Thevenin bus sag V_load = V_oc - I*R0 - V1 - V2, thermal cutoff > 95 C.");
        ImGui::Text("4. Structures & Clearance: Euler-Bernoulli root moment FoS >= 1.25x, rotor spacing >= 20 mm.");
        ImGui::Text("5. Phase 1 Unsteady & Hydro: Theodorsen C(k), Wagner Phi(tau), Polhamus LEV, Savitsky 1964.");
        if (ImGui::Button("Close")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (show_about_modal) {
        ImGui::OpenPopup("About Aerodynamics Lab");
        show_about_modal = false;
    }
    if (ImGui::BeginPopupModal("About Aerodynamics Lab", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::Text("Aerodynamics Lab — Standalone Zero-Engine Engineering Workbench");
        ImGui::Text("Stack: C++20 + OpenGL 3.3 Core + Dear ImGui Docking + lab_core + Open CASCADE / Python");
        if (ImGui::Button("Close")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    if (show_failure_atlas_modal) {
        ImGui::OpenPopup("Failure Atlas — 10 Curated Real Failure Scenarios");
        show_failure_atlas_modal = false;
    }
    if (ImGui::BeginPopupModal("Failure Atlas — 10 Curated Real Failure Scenarios", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::Text("Click any failure scenario to load it directly into the live 3D physics workbench:");
        ImGui::Separator();
        if (ImGui::Button("1. Jet Choked Intake + EGT Melt")) {
            switch_family(VehicleFamily::Jet);
            params.intake_area_m2 = 0.0012f;
            params.jet_throttle_pct = 104.0f;
            params.motor_cooling_grade = 0;
            params.oat_c = 42.0f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("2. Jet Supersonic Wave Drag & Mach Cone (M~1.42)")) {
            switch_family(VehicleFamily::Jet);
            params.hardware_catalog_idx = 5;
            params.airspeed_m_s = 485.0f;
            params.jet_throttle_pct = 100.0f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("3. Cargo Slung-Load Over-Blowback & Overload")) {
            switch_family(VehicleFamily::CargoUAV);
            params.cargo_mass_kg = 7.5f;
            params.airspeed_m_s = 25.0f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("4. Flying Wing Low-Sweep Pitch Tumble")) {
            switch_family(VehicleFamily::FlyingWing);
            params.sweep_deg = 6.0f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("5. Tailsitter Transition Stall")) {
            switch_family(VehicleFamily::Tailsitter);
            params.rotor_rpm = 1900.0f;
            params.airspeed_m_s = 2.0f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("6. Multirotor Tip Clash + M2 Bolt Shear + 22AWG Burn")) {
            switch_family(VehicleFamily::Multirotor);
            params.arm_length_m = 0.14f;
            params.prop_diameter_m = 0.50f;
            params.screw_size_idx = 0;
            params.wire_awg = 22;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("7. Seaplane Choppy-Water Hump Lock")) {
            switch_family(VehicleFamily::Seaplane);
            params.rotor_rpm = 1800.0f;
            params.water_chop_m = 0.18f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("8. Helicopter Vortex Ring State (VRS Descent)")) {
            switch_family(VehicleFamily::Helicopter);
            params.rotor_rpm = 1450.0f;
            params.airspeed_m_s = 1.2f;
            params.heli_descent_m_s = -2.1f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("9. X-15A-2 Mach 6.7 Skin Thermal Burn (>1100C)")) {
            switch_family(VehicleFamily::Jet);
            params.hardware_catalog_idx = 5;
            params.jet_afterburner = true;
            params.jet_ramjet = true;
            params.altitude_asl_m = 31120.0f;
            params.airspeed_m_s = 2020.0f;
            params.jet_throttle_pct = 100.0f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("10. Rocket Launch Pad Underweight / Wind-Shear Abort")) {
            switch_family(VehicleFamily::RocketSpacecraft);
            params.rocket_thrust_kn = 180.0f;
            params.wind_x_m_s = 22.0f;
            params.turbulence_pct = 45.0f;
            rebuild_geometry();
            ImGui::CloseCurrentPopup();
        }
        if (ImGui::Button("Close")) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }
}

void AppWorkbench::draw_rc_hud() {
    const ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + vp->WorkSize.x * 0.24f, vp->WorkPos.y + vp->WorkSize.y - 252.0f), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(360.0f, 235.0f), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Virtual Dual-Stick & USB RC Transmitter", &params.show_rc_hud)) {
        ImGui::End();
        return;
    }
    const ImVec2 pad_sz(110.0f, 110.0f);
    ImDrawList *dl = ImGui::GetWindowDrawList();
    auto draw_gimbal = [&](const char *id, const char *lbl, float &ax_x, float &ax_y, bool y_unipolar) -> bool {
        bool mod = false;
        ImGui::BeginGroup();
        ImGui::TextDisabled("%s", lbl);
        const ImVec2 p0 = ImGui::GetCursorScreenPos();
        const ImVec2 p1(p0.x + pad_sz.x, p0.y + pad_sz.y);
        dl->AddRectFilled(p0, p1, IM_COL32(244, 247, 252, 255), 6.0f);
        dl->AddRect(p0, p1, IM_COL32(175, 190, 210, 255), 6.0f);
        const ImVec2 ctr(0.5f * (p0.x + p1.x), 0.5f * (p0.y + p1.y));
        dl->AddLine(ImVec2(p0.x + 6, ctr.y), ImVec2(p1.x - 6, ctr.y), IM_COL32(215, 224, 236, 255));
        dl->AddLine(ImVec2(ctr.x, p0.y + 6), ImVec2(ctr.x, p1.y - 6), IM_COL32(215, 224, 236, 255));
        const float ny = y_unipolar ? (1.0f - 2.0f * std::clamp(ax_y, 0.0f, 1.0f)) : (-std::clamp(ax_y, -1.0f, 1.0f));
        const ImVec2 knob(ctr.x + std::clamp(ax_x, -1.0f, 1.0f) * (pad_sz.x * 0.42f), ctr.y + ny * (pad_sz.y * 0.42f));
        dl->AddCircleFilled(knob, 9.0f, IM_COL32(37, 99, 235, 255));
        ImGui::InvisibleButton(id, pad_sz);
        if (ImGui::IsItemActive() && ImGui::IsMouseDragging(ImGuiMouseButton_Left)) {
            const ImVec2 mp = ImGui::GetIO().MousePos;
            ax_x = std::clamp((mp.x - ctr.x) / (pad_sz.x * 0.42f), -1.0f, 1.0f);
            const float dy = std::clamp((mp.y - ctr.y) / (pad_sz.y * 0.42f), -1.0f, 1.0f);
            ax_y = y_unipolar ? std::clamp(0.5f * (1.0f - dy), 0.0f, 1.0f) : (-dy);
            mod = true;
        }
        ImGui::EndGroup();
        return mod;
    };

    bool rc_changed = draw_gimbal("##rc_left", "THR / YAW (L)", params.rc_yaw, params.rc_throttle, true);
    ImGui::SameLine(0.0f, 22.0f);
    rc_changed |= draw_gimbal("##rc_right", "PITCH / ROLL (R)", params.rc_roll, params.rc_pitch, false);
    if (rc_changed) {
        params.rotor_rpm = 1800.0f + params.rc_throttle * 11200.0f;
        params.jet_throttle_pct = 20.0f + params.rc_throttle * 85.0f;
        rebuild_geometry();
    }
    ImGui::Checkbox("USB HID Joystick", &params.use_usb_joystick);
    ImGui::SameLine();
    if (ImGui::SmallButton("Center Sticks")) {
        params.rc_yaw = 0.0f; params.rc_pitch = 0.0f; params.rc_roll = 0.0f;
        rebuild_geometry();
    }
    if (params.family == VehicleFamily::CargoUAV) {
        ImGui::SameLine();
        if (ImGui::SmallButton(params.payload_released ? "Re-Hook Cargo" : "Drop Cargo")) {
            params.payload_released = !params.payload_released;
            rebuild_geometry();
        }
    }
    ImGui::Text("PWM us: THR %d | YAW %d | PIT %d | ROL %d",
                1000 + static_cast<int>(params.rc_throttle * 1000.0f),
                1500 + static_cast<int>(params.rc_yaw * 500.0f),
                1500 + static_cast<int>(params.rc_pitch * 500.0f),
                1500 + static_cast<int>(params.rc_roll * 500.0f));
    ImGui::End();
}

} // namespace aerolab
