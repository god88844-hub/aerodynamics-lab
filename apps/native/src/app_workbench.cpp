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
        params.hardware_catalog_idx = 0;
        params.frame_mass_kg = 1.20f;
        params.battery_mass_kg = 1.55f;
        params.payload_mass_kg = 0.35f;
        params.motor_mass_kg = 0.103f;
        params.battery_cells_s = 6;
        params.battery_capacity_ah = 10.0f;
        params.battery_r0_ohm = 0.025f;
        params.rotor_rpm = 4800.0f;
        params.airspeed_m_s = 18.0f;
        camera.distance_m = 1.65f;
    } else if (family == VehicleFamily::FixedWing) {
        params.project_name = "Fixed-Wing Trainer";
        params.hardware_catalog_idx = 1;
        params.frame_mass_kg = 1.20f;
        params.battery_mass_kg = 0.55f;
        params.payload_mass_kg = 0.35f;
        params.battery_cells_s = 4;
        params.battery_capacity_ah = 4.5f;
        params.battery_r0_ohm = 0.018f;
        params.wingspan_m = 1.65f;
        params.sweep_deg = 12.0f;
        params.airspeed_m_s = 18.0f;
        params.rotor_rpm = 6200.0f;
        camera.distance_m = 2.40f;
    } else if (family == VehicleFamily::Helicopter) {
        params.project_name = "Helicopter Rotorcraft";
        params.hardware_catalog_idx = 0;
        params.frame_mass_kg = 1.20f;
        params.battery_mass_kg = 1.55f;
        params.payload_mass_kg = 0.35f;
        params.rotor_rpm = 1450.0f;
        params.airspeed_m_s = 18.0f;
        camera.distance_m = 2.25f;
    } else if (family == VehicleFamily::VTOL) {
        params.project_name = "VTOL Tiltrotor";
        params.hardware_catalog_idx = 0;
        params.frame_mass_kg = 1.20f;
        params.battery_mass_kg = 1.55f;
        params.payload_mass_kg = 0.35f;
        params.wingspan_m = 1.65f;
        params.rotor_rpm = 4200.0f;
        params.airspeed_m_s = 20.0f;
        camera.distance_m = 2.45f;
    } else if (family == VehicleFamily::Seaplane) {
        params.project_name = "Twin-Float Seaplane";
        params.hardware_catalog_idx = 1;
        params.frame_mass_kg = 1.45f;
        params.battery_mass_kg = 0.55f;
        params.payload_mass_kg = 0.35f;
        params.battery_cells_s = 4;
        params.battery_capacity_ah = 4.5f;
        params.battery_r0_ohm = 0.018f;
        params.wingspan_m = 1.75f;
        params.root_chord_m = 0.28f;
        params.tip_chord_m = 0.18f;
        params.sweep_deg = 4.0f;
        params.alpha_deg = 4.5f;
        params.airspeed_m_s = 22.0f;
        params.rotor_rpm = 7200.0f;
        params.float_beam_m = 0.14f;
        params.float_deadrise_deg = 18.0f;
        params.water_chop_m = 0.04f;
        camera.distance_m = 2.55f;
    } else if (family == VehicleFamily::Jet) {
        params.project_name = "Swept Micro-Turbojet UAV";
        params.hardware_catalog_idx = 4; // KingTech K-45G4 45 N
        params.frame_mass_kg = 2.80f;
        params.battery_mass_kg = 0.90f; // Jet-A1 + ECU pack
        params.payload_mass_kg = 0.60f;
        params.battery_cells_s = 2;
        params.battery_capacity_ah = 2.2f;
        params.battery_r0_ohm = 0.020f;
        params.wingspan_m = 1.35f;
        params.root_chord_m = 0.38f;
        params.tip_chord_m = 0.14f;
        params.sweep_deg = 26.0f;
        params.dihedral_deg = 2.0f;
        params.alpha_deg = 2.2f;
        params.airspeed_m_s = 92.0f;
        params.jet_throttle_pct = 85.0f;
        params.wing_tc_ratio = 0.09f;
        params.intake_area_m2 = 0.0032f;
        params.nozzle_area_ratio = 1.15f;
        params.fuel_mass_kg = 0.85f;
        camera.distance_m = 2.25f;
    } else if (family == VehicleFamily::InsectFlapper) {
        params.project_name = "Insect Micro-Flapper MAV";
        params.hardware_catalog_idx = 3; // Coreless 7x20mm + 1S
        params.frame_mass_kg = 0.014f;
        params.battery_mass_kg = 0.010f;
        params.payload_mass_kg = 0.004f;
        params.motor_mass_kg = 0.004f;
        params.battery_cells_s = 1;
        params.battery_capacity_ah = 0.50f;
        params.battery_r0_ohm = 0.065f;
        params.wingspan_m = 0.16f;
        params.root_chord_m = 0.028f;
        params.tip_chord_m = 0.016f;
        params.flap_freq_hz = 40.0f;
        params.stroke_amp_deg = 78.0f;
        params.morph_tuck_pct = 0.0f;
        params.airspeed_m_s = 2.2f;
        params.alpha_deg = 8.0f;
        params.animate_flapping = false;
        camera.distance_m = 0.55f;
    } else if (family == VehicleFamily::MorphingWing) {
        params.project_name = "Morphing-Wing Glider (PigeonBot)";
        params.hardware_catalog_idx = 1; // ECOII 2807 + 4S
        params.frame_mass_kg = 0.65f;
        params.battery_mass_kg = 0.35f;
        params.payload_mass_kg = 0.12f;
        params.motor_mass_kg = 0.055f;
        params.battery_cells_s = 4;
        params.battery_capacity_ah = 4.5f;
        params.battery_r0_ohm = 0.018f;
        params.wingspan_m = 1.15f;
        params.root_chord_m = 0.22f;
        params.tip_chord_m = 0.14f;
        params.sweep_deg = 16.0f;
        params.dihedral_deg = 4.0f;
        params.morph_tuck_pct = 25.0f;
        params.wing_asymmetry_diff = 0.10f;
        params.tail_spread_pct = 75.0f;
        params.tail_tilt_deg = 8.0f;
        params.rotor_rpm = 6500.0f;
        params.airspeed_m_s = 16.0f;
        params.alpha_deg = 5.5f;
        camera.distance_m = 1.75f;
    } else if (family == VehicleFamily::CargoUAV) {
        params.project_name = "Cargo Hex Slung-Load Carrier";
        params.hardware_catalog_idx = 0; // MN3508 + 6S
        params.rotor_count = 6;
        params.arm_length_m = 0.48f;
        params.prop_diameter_m = 0.38f;
        params.prop_pitch_deg = 15.0f;
        params.frame_mass_kg = 1.85f;
        params.battery_mass_kg = 1.55f;
        params.payload_mass_kg = 0.25f;
        params.cargo_mass_kg = 1.80f;
        params.cable_length_m = 1.20f;
        params.payload_released = false;
        params.motor_mass_kg = 0.103f;
        params.battery_cells_s = 6;
        params.battery_capacity_ah = 10.0f;
        params.battery_r0_ohm = 0.020f;
        params.rotor_rpm = 5400.0f;
        params.airspeed_m_s = 12.0f;
        params.screw_size_idx = 3; // M4 ISO 4762
        params.wire_awg = 12;
        camera.distance_m = 2.45f;
    } else if (family == VehicleFamily::Tailsitter) {
        params.project_name = "VTOL Tailsitter (dRehmFlight)";
        params.hardware_catalog_idx = 1; // ECOII 2807 + 4S
        params.frame_mass_kg = 0.92f;
        params.battery_mass_kg = 0.48f;
        params.payload_mass_kg = 0.16f;
        params.motor_mass_kg = 0.068f;
        params.battery_cells_s = 4;
        params.battery_capacity_ah = 4.5f;
        params.battery_r0_ohm = 0.018f;
        params.wingspan_m = 1.05f;
        params.root_chord_m = 0.28f;
        params.tip_chord_m = 0.18f;
        params.sweep_deg = 12.0f;
        params.dihedral_deg = 2.0f;
        params.transition_pitch_deg = 70.0f;
        params.duct_area_ratio = 1.08f;
        params.prop_diameter_m = 0.28f;
        params.rotor_rpm = 7200.0f;
        params.airspeed_m_s = 14.0f;
        params.screw_size_idx = 2; // M3 ISO 4762
        params.wire_awg = 14;
        camera.distance_m = 1.85f;
    } else if (family == VehicleFamily::FlyingWing) {
        params.project_name = "Swept Reflex Flying Wing";
        params.hardware_catalog_idx = 1; // ECOII 2807 + 4S
        params.frame_mass_kg = 0.72f;
        params.battery_mass_kg = 0.46f;
        params.payload_mass_kg = 0.14f;
        params.motor_mass_kg = 0.065f;
        params.battery_cells_s = 4;
        params.battery_capacity_ah = 4.5f;
        params.battery_r0_ohm = 0.018f;
        params.wingspan_m = 1.25f;
        params.root_chord_m = 0.30f;
        params.tip_chord_m = 0.14f;
        params.sweep_deg = 26.0f;
        params.dihedral_deg = 1.5f;
        params.twist_tip_deg = -3.5f;
        params.airfoil_code = "23012";
        params.rotor_rpm = 7600.0f;
        params.airspeed_m_s = 22.0f;
        params.alpha_deg = 4.0f;
        params.screw_size_idx = 2;
        params.wire_awg = 14;
        camera.distance_m = 1.85f;
    } else if (family == VehicleFamily::RocketSpacecraft) {
        params.project_name = "2-Stage Orbital & Hypersonic Vehicle";
        params.frame_mass_kg = 2680.0f;
        params.payload_mass_kg = 250.0f;
        params.rocket_stage1_prop_kg = 18500.0f;
        params.rocket_stage2_prop_kg = 4200.0f;
        params.rocket_isp1_s = 295.0f;
        params.rocket_thrust_kn = 340.0f;
        params.rocket_nose_radius_m = 0.85f;
        params.reentry_speed_km_s = 7.65f;
        params.reentry_alt_km = 68.0f;
        params.fuselage_length_m = 2.40f;
        params.fuselage_radius_m = 0.14f;
        params.screw_size_idx = 5;
        params.wire_awg = 10;
        camera.distance_m = 3.20f;
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
    } else if (params.family == VehicleFamily::Seaplane) {
        feature_tree.push_back({"sea_fuse", "Hull Pod & Twin Floats", "Fuselage"});
        feature_tree.push_back({"sea_wing", "High Wing + Empennage", "WingLoft"});
    } else if (params.family == VehicleFamily::Jet) {
        feature_tree.push_back({"jet_fuse", "Area-Ruled Fuse + Nozzle", "Fuselage"});
        feature_tree.push_back({"jet_wing", "Swept Transonic Wing", "WingLoft"});
    } else if (params.family == VehicleFamily::InsectFlapper) {
        feature_tree.push_back({"bio_thorax", "Micro Thorax & Frame", "Fuselage"});
        feature_tree.push_back({"bio_wings", "Flapping Membrane Wing", "WingLoft"});
    } else if (params.family == VehicleFamily::MorphingWing) {
        feature_tree.push_back({"morph_body", "Morph Body & Wrist Servo", "Fuselage"});
        feature_tree.push_back({"morph_wing", "Shoulder-Wrist Feathers", "WingLoft"});
        feature_tree.push_back({"morph_tail", "Fan Tail Spread / Tilt", "WingLoft"});
    } else if (params.family == VehicleFamily::CargoUAV) {
        feature_tree.push_back({"cargo_hex", "Heavy Hex Frame & Gimbal Hook", "RotorArray"});
        feature_tree.push_back({"cargo_sling", params.payload_released ? "Slung Parcel (Released)" : "Slung Parcel + Tether", "Solid"});
    } else if (params.family == VehicleFamily::Tailsitter) {
        feature_tree.push_back({"tail_wing", "Pitchable Transition Wing", "WingLoft"});
        feature_tree.push_back({"tail_props", "Twin Propwash Nacelles", "RotorArray"});
    } else if (params.family == VehicleFamily::FlyingWing) {
        feature_tree.push_back({"fwing_body", "Reflex Swept Plank + Pod", "WingLoft"});
        feature_tree.push_back({"fwing_elevons", "Coupled Elevons + Pusher", "RotorArray"});
    } else if (params.family == VehicleFamily::RocketSpacecraft) {
        feature_tree.push_back({"rkt_s1", "Stage 1 Booster + Grid/Stabilizer Fins", "Fuselage"});
        feature_tree.push_back({"rkt_s2", "Stage 2 Upper + Payload Heatshield", "Fuselage"});
    }
    const char *m_names[] = {"M2", "M2.5", "M3", "M4", "M5", "M6"};
    const int sidx = (params.screw_size_idx < 0) ? 0 : (params.screw_size_idx > 5 ? 5 : params.screw_size_idx);
    feature_tree.push_back({"bom_std",
                            std::string("ISO 4762 ") + m_names[sidx] + (params.titanium_screws ? " Ti" : " 12.9") +
                                " / " + std::to_string(params.wire_awg) + "AWG",
                            "Standards"});
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
    const bool live_spin = evidence.playing || params.animate_flapping || params.show_rc_hud || params.motion_study_active;
    if (live_spin) {
        params.flap_anim_phase_rad += dt_s * 11.5f; // Slow-motion visual wingbeat cycle
        if (params.flap_anim_phase_rad > 62.8318f) params.flap_anim_phase_rad = 0.0f;
        const float spin_rate = 18.0f * (0.4f + 0.9f * (params.rotor_rpm / 6000.0f));
        params.spin_phase_rad += dt_s * spin_rate;
        if (params.spin_phase_rad > 62.8318f) params.spin_phase_rad -= 62.8318f;
        if (params.motion_study_active) {
            params.motion_study_time_s += dt_s;
            const float s_wave = 0.5f - 0.5f * std::cos(params.motion_study_time_s * 1.8f);
            if (params.family == VehicleFamily::VTOL) params.vtol_tilt_deg = 90.0f * s_wave;
            else if (params.family == VehicleFamily::Tailsitter) params.transition_pitch_deg = 85.0f * s_wave;
            else if (params.family == VehicleFamily::MorphingWing) params.morph_tuck_pct = 65.0f * s_wave;
            else {
                params.rc_roll = std::sin(params.motion_study_time_s * 2.6f);
                params.rc_pitch = std::cos(params.motion_study_time_s * 1.9f) * 0.6f;
            }
        }
        scene = build_cad_scene(params, selected_part_idx);
        if (viewport_) {
            viewport_->upload_scene(scene);
        }
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
    if (params.show_rc_hud) {
        draw_rc_hud();
    }
    draw_modals();
}

bool AppWorkbench::export_viewport_png(const std::string &path) {
    std::vector<std::uint8_t> rgba;
    if (!viewport_ || !viewport_->read_fbo_rgba(last_vp_w_, last_vp_h_, rgba)) return false;
    return write_png_rgba(path, last_vp_w_, last_vp_h_, rgba);
}

} // namespace aerolab
