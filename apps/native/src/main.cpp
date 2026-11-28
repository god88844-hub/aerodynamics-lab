#include "app_workbench.hpp"
#include "gl_core_33.hpp"

#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <numeric>
#include <string>
#include <thread>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <dwmapi.h>
#include <psapi.h>
#endif

static void pace_compositor_frame(std::chrono::steady_clock::time_point frame_start) {
#ifdef _WIN32
    if (SUCCEEDED(DwmFlush())) {
        return;
    }
#endif
    const auto target = frame_start + std::chrono::microseconds(16667);
    if (std::chrono::steady_clock::now() < target) {
        std::this_thread::sleep_until(target);
    }
}

int main(int argc, char **argv) {
    bool smoke_test = false;
    bool benchmark_200 = false;
    int benchmark_frames = 600;
    std::string benchmark_out;
    std::string screenshot_path;
    bool four_view = false;
    bool cp_view = false;
    bool open_rc_hud = false;
    bool stress_view = false;
    bool motion_study = false;
    float override_airspeed = -1.0f;
    float override_explode = -1.0f;
    std::string preset_name;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--smoke-test") == 0) smoke_test = true;
        else if (std::strcmp(argv[i], "--benchmark-200") == 0) benchmark_200 = true;
        else if (std::strcmp(argv[i], "--frames") == 0 && i + 1 < argc) benchmark_frames = std::max(30, std::atoi(argv[++i]));
        else if (std::strcmp(argv[i], "--output") == 0 && i + 1 < argc) benchmark_out = argv[++i];
        else if (std::strcmp(argv[i], "--4view") == 0 || std::strcmp(argv[i], "--four-view") == 0) four_view = true;
        else if (std::strcmp(argv[i], "--cp") == 0 || std::strcmp(argv[i], "--cp-view") == 0) cp_view = true;
        else if (std::strcmp(argv[i], "--stress") == 0) stress_view = true;
        else if (std::strcmp(argv[i], "--motion") == 0) motion_study = true;
        else if (std::strcmp(argv[i], "--explode") == 0 && i + 1 < argc) override_explode = static_cast<float>(std::atof(argv[++i]));
        else if (std::strcmp(argv[i], "--rc-hud") == 0) open_rc_hud = true;
        else if (std::strcmp(argv[i], "--airspeed") == 0 && i + 1 < argc) override_airspeed = static_cast<float>(std::atof(argv[++i]));
        else if (std::strcmp(argv[i], "--preset") == 0 && i + 1 < argc) preset_name = argv[++i];
        else if (std::strcmp(argv[i], "--screenshot") == 0 && i + 1 < argc) screenshot_path = argv[++i];
    }

    if (!glfwInit()) {
        std::fprintf(stderr, "Failed to initialize GLFW\n");
        return 1;
    }

    glfwWindowHint(GLFW_CONTEXT_VERSION_MAJOR, 3);
    glfwWindowHint(GLFW_CONTEXT_VERSION_MINOR, 3);
    glfwWindowHint(GLFW_OPENGL_PROFILE, GLFW_OPENGL_CORE_PROFILE);
    glfwWindowHint(GLFW_SAMPLES, 0);
    if (smoke_test) {
        glfwWindowHint(GLFW_VISIBLE, GLFW_FALSE);
    }

    GLFWwindow *window = glfwCreateWindow(1360, 840, "Aerodynamics Lab — Engineering CAD & Flight Workbench", nullptr, nullptr);
    if (!window) {
        std::fprintf(stderr, "Failed to create OpenGL 3.3 Core window\n");
        glfwTerminate();
        return 2;
    }
    glfwMakeContextCurrent(window);
    glfwSwapInterval(0);

    gl33::Dispatch gl;
    if (!gl.load()) {
        std::fprintf(stderr, "Failed to load OpenGL 3.3 procedures\n");
        glfwDestroyWindow(window);
        glfwTerminate();
        return 3;
    }

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_DockingEnable;
    io.IniFilename = nullptr; // deterministic docked CAD layout on launch

    ImGui_ImplGlfw_InitForOpenGL(window, true);
    ImGui_ImplOpenGL3_Init("#version 330");

    aerolab::AppWorkbench app;
    if (!app.init(&gl, aerolab::detect_repo_root())) {
        std::fprintf(stderr, "Failed to initialize Aerodynamics Lab OpenGL workbench\n");
        ImGui_ImplOpenGL3_Shutdown();
        ImGui_ImplGlfw_Shutdown();
        ImGui::DestroyContext();
        glfwDestroyWindow(window);
        glfwTerminate();
        return 4;
    }

    auto render_one_frame = [&](float dt_s) -> int {
        int fb_w = 1360, fb_h = 840;
        glfwGetFramebufferSize(window, &fb_w, &fb_h);
        if (fb_w <= 0 || fb_h <= 0) {
            fb_w = 1360;
            fb_h = 840;
        }
        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();
        app.render_ui_and_scene(dt_s, fb_w, fb_h);
        ImGui::Render();
        gl.Viewport(0, 0, fb_w, fb_h);
        gl.ClearColor(0.95f, 0.96f, 0.98f, 1.0f);
        gl.Clear(gl33::GL_COLOR_BUFFER_BIT_V | gl33::GL_DEPTH_BUFFER_BIT_V);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glfwSwapBuffers(window);
        return fb_w * 100000 + fb_h;
    };

    if (benchmark_200) {
        app.params.project_name = "200-Part Assembly Benchmark";
        app.params.family = aerolab::VehicleFamily::Benchmark200;
        app.camera.distance_m = 2.1f;
        app.rebuild_geometry();

        for (int w = 0; w < 90; ++w) {
            const auto t0 = std::chrono::steady_clock::now();
            glfwPollEvents();
            render_one_frame(0.016f);
            pace_compositor_frame(t0);
        }

        std::vector<double> dt_ms;
        dt_ms.reserve(benchmark_frames);
        auto prev = std::chrono::steady_clock::now();
        for (int f = 0; f < benchmark_frames; ++f) {
            glfwPollEvents();
            app.camera.yaw_deg += 0.40f;
            if (f % 30 == 0 && !app.scene.assembly_parts.empty()) {
                app.selected_part_idx = (f / 30) % static_cast<int>(app.scene.assembly_parts.size());
                app.rebuild_geometry();
            }
            const auto now = std::chrono::steady_clock::now();
            const float dt = std::chrono::duration<float>(now - prev).count();
            render_one_frame(dt);
            pace_compositor_frame(prev);
            const auto after = std::chrono::steady_clock::now();
            dt_ms.push_back(std::chrono::duration<double, std::milli>(after - prev).count());
            prev = after;
        }
        std::sort(dt_ms.begin(), dt_ms.end());
        const double total_ms = std::accumulate(dt_ms.begin(), dt_ms.end(), 0.0);
        const double mean_fps = (total_ms > 0.0) ? (1000.0 * benchmark_frames / total_ms) : 0.0;
        const double p50 = dt_ms[dt_ms.size() * 50 / 100];
        const double p95 = dt_ms[dt_ms.size() * 95 / 100];
        const double p99 = dt_ms[dt_ms.size() * 99 / 100];
        const double mx = dt_ms.back();
        std::size_t peak_ws_bytes = 0, private_bytes = 0;
#ifdef _WIN32
        PROCESS_MEMORY_COUNTERS_EX pmc{};
        if (GetProcessMemoryInfo(GetCurrentProcess(), reinterpret_cast<PROCESS_MEMORY_COUNTERS *>(&pmc), sizeof(pmc))) {
            peak_ws_bytes = pmc.PeakWorkingSetSize;
            private_bytes = pmc.PrivateUsage;
        }
#endif
        if (!benchmark_out.empty()) {
            const std::filesystem::path bp(benchmark_out);
            if (bp.has_parent_path()) {
                std::error_code ec;
                std::filesystem::create_directories(bp.parent_path(), ec);
            }
            std::ofstream ofs(bp);
            ofs << "{\n"
                << "  \"window_mode\": \"visible_native_opengl_imgui_dwmflush\",\n"
                << "  \"parts\": " << app.scene.assembly_parts.size() << ",\n"
                << "  \"triangles\": " << (app.scene.indices.size() / 3) << ",\n"
                << "  \"edge_segments\": " << (app.scene.cad_edges.size() / 2) << ",\n"
                << "  \"frames\": " << benchmark_frames << ",\n"
                << "  \"mean_fps\": " << mean_fps << ",\n"
                << "  \"p50_ms\": " << p50 << ",\n"
                << "  \"p95_ms\": " << p95 << ",\n"
                << "  \"p99_ms\": " << p99 << ",\n"
                << "  \"max_ms\": " << mx << ",\n"
                << "  \"peak_working_set_bytes\": " << peak_ws_bytes << ",\n"
                << "  \"private_bytes\": " << private_bytes << "\n"
                << "}\n";
        }
        app.shutdown();
        ImGui_ImplOpenGL3_Shutdown();
        ImGui_ImplGlfw_Shutdown();
        ImGui::DestroyContext();
        glfwDestroyWindow(window);
        glfwTerminate();
        return 0;
    }

    if (preset_name == "fixed-wing") app.switch_family(aerolab::VehicleFamily::FixedWing);
    else if (preset_name == "helicopter") app.switch_family(aerolab::VehicleFamily::Helicopter);
    else if (preset_name == "vtol") app.switch_family(aerolab::VehicleFamily::VTOL);
    else if (preset_name == "seaplane") app.switch_family(aerolab::VehicleFamily::Seaplane);
    else if (preset_name == "jet") app.switch_family(aerolab::VehicleFamily::Jet);
    else if (preset_name == "insect") app.switch_family(aerolab::VehicleFamily::InsectFlapper);
    else if (preset_name == "morphing") app.switch_family(aerolab::VehicleFamily::MorphingWing);
    else if (preset_name == "cargo") app.switch_family(aerolab::VehicleFamily::CargoUAV);
    else if (preset_name == "tailsitter") app.switch_family(aerolab::VehicleFamily::Tailsitter);
    else if (preset_name == "flying-wing") app.switch_family(aerolab::VehicleFamily::FlyingWing);
    else if (preset_name == "rocket") app.switch_family(aerolab::VehicleFamily::RocketSpacecraft);
    else if (preset_name == "airliner") app.switch_family(aerolab::VehicleFamily::Airliner);
    else if (preset_name == "part") app.switch_family(aerolab::VehicleFamily::CustomPart);
    if (override_airspeed > 0.5f) {
        app.params.airspeed_m_s = override_airspeed;
        if (app.params.family == aerolab::VehicleFamily::Jet && override_airspeed > 330.0f) {
            app.params.hardware_catalog_idx = 5;
            app.params.jet_throttle_pct = 100.0f;
            app.params.jet_afterburner = true;
            if (override_airspeed > 600.0f) {
                app.params.jet_ramjet = true;
                app.params.altitude_asl_m = 31120.0f;
            }
        }
        app.rebuild_geometry();
    }
    if (override_explode >= 0.0f) {
        app.params.explode_factor = override_explode;
        app.rebuild_geometry();
    }
    if (motion_study) {
        app.params.motion_study_active = true;
    }
    if (open_rc_hud) {
        app.params.show_rc_hud = true;
    }
    if (four_view) {
        app.viewport_layout = aerolab::ViewportLayout::Ortho4View;
    }
    if (stress_view) {
        app.shading_mode = aerolab::ShadingMode::StressVonMises;
    } else if (cp_view) {
        app.shading_mode = aerolab::ShadingMode::SurfaceCp;
    }

    auto last_t = std::chrono::steady_clock::now();
    int frames = 0;
    bool exit_ok = true;

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        if (app.params.use_usb_joystick && glfwJoystickPresent(GLFW_JOYSTICK_1)) {
            int count = 0;
            const float *axes = glfwGetJoystickAxes(GLFW_JOYSTICK_1, &count);
            if (axes && count >= 4) {
                app.params.rc_roll = std::clamp(axes[0], -1.0f, 1.0f);
                app.params.rc_pitch = std::clamp(axes[1], -1.0f, 1.0f);
                app.params.rc_throttle = std::clamp(0.5f * (-axes[2] + 1.0f), 0.0f, 1.0f);
                app.params.rc_yaw = std::clamp(axes[3], -1.0f, 1.0f);
            }
        }
        const auto now = std::chrono::steady_clock::now();
        const float dt = std::chrono::duration<float>(now - last_t).count();
        last_t = now;

        const int packed = render_one_frame(dt);
        const int fb_w = packed / 100000;
        const int fb_h = packed % 100000;

        ++frames;
        if (smoke_test && frames == 3 && !screenshot_path.empty()) {
            const std::filesystem::path sp(screenshot_path);
            if (sp.has_parent_path()) {
                std::error_code ec;
                std::filesystem::create_directories(sp.parent_path(), ec);
            }
            std::vector<std::uint8_t> win_rgba(static_cast<std::size_t>(fb_w) * fb_h * 4);
            gl.ReadPixels(0, 0, fb_w, fb_h, gl33::GL_RGBA_V, gl33::GL_UNSIGNED_BYTE_V, win_rgba.data());
            if (!aerolab::write_png_rgba(screenshot_path, fb_w, fb_h, win_rgba)) {
                exit_ok = false;
            }
        }
        if (smoke_test && frames >= 4) {
            break;
        }
        if (!smoke_test) {
            pace_compositor_frame(now);
        }
    }

    app.shutdown();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui_ImplGlfw_Shutdown();
    ImGui::DestroyContext();
    glfwDestroyWindow(window);
    glfwTerminate();
    return exit_ok ? 0 : 5;
}
