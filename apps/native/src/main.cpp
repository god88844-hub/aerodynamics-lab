#include "app_workbench.hpp"
#include "gl_core_33.hpp"

#include "imgui.h"
#include "imgui_impl_glfw.h"
#include "imgui_impl_opengl3.h"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

int main(int argc, char **argv) {
    bool smoke_test = false;
    std::string screenshot_path;
    bool four_view = false;
    bool cp_view = false;
    std::string preset_name;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--smoke-test") == 0) smoke_test = true;
        else if (std::strcmp(argv[i], "--4view") == 0) four_view = true;
        else if (std::strcmp(argv[i], "--cp") == 0) cp_view = true;
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
    glfwWindowHint(GLFW_SAMPLES, 4);
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
    glfwSwapInterval(smoke_test ? 0 : 1);

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
    if (preset_name == "fixed-wing") app.switch_family(aerolab::VehicleFamily::FixedWing);
    else if (preset_name == "helicopter") app.switch_family(aerolab::VehicleFamily::Helicopter);
    else if (preset_name == "vtol") app.switch_family(aerolab::VehicleFamily::VTOL);
    else if (preset_name == "part") app.switch_family(aerolab::VehicleFamily::CustomPart);
    if (four_view) {
        app.viewport_layout = aerolab::ViewportLayout::Ortho4View;
    }
    if (cp_view) {
        app.shading_mode = aerolab::ShadingMode::SurfaceCp;
    }

    auto last_t = std::chrono::steady_clock::now();
    int frames = 0;
    bool exit_ok = true;

    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        const auto now = std::chrono::steady_clock::now();
        const float dt = std::chrono::duration<float>(now - last_t).count();
        last_t = now;

        int fb_w = 1360, fb_h = 840;
        glfwGetFramebufferSize(window, &fb_w, &fb_h);
        if (fb_w <= 0 || fb_h <= 0) {
            fb_w = 1360;
            fb_h = 840;
        }

        ImGui_ImplOpenGL3_NewFrame();
        ImGui_ImplGlfw_NewFrame();
        ImGui::NewFrame();

        app.render_ui_and_scene(dt, fb_w, fb_h);

        ImGui::Render();
        gl.Viewport(0, 0, fb_w, fb_h);
        gl.ClearColor(0.95f, 0.96f, 0.98f, 1.0f);
        gl.Clear(gl33::GL_COLOR_BUFFER_BIT_V | gl33::GL_DEPTH_BUFFER_BIT_V);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        glfwSwapBuffers(window);

        ++frames;
        if (smoke_test && frames == 3 && !screenshot_path.empty()) {
            const std::filesystem::path sp(screenshot_path);
            if (sp.has_parent_path()) {
                std::error_code ec;
                std::filesystem::create_directories(sp.parent_path(), ec);
            }
            // Capture full rendered workbench window (menus + panels + OpenGL viewport)
            std::vector<std::uint8_t> win_rgba(static_cast<std::size_t>(fb_w) * fb_h * 4);
            gl.ReadPixels(0, 0, fb_w, fb_h, gl33::GL_RGBA_V, gl33::GL_UNSIGNED_BYTE_V, win_rgba.data());
            if (!aerolab::write_png_rgba(screenshot_path, fb_w, fb_h, win_rgba)) {
                exit_ok = false;
            }
        }
        if (smoke_test && frames >= 4) {
            break;
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
