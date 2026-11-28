#pragma once

#include "cad_types.hpp"
#include "gl_core_33.hpp"

#include <array>
#include <cstdint>
#include <vector>

namespace aerolab {

struct Mat4 {
    float m[16]{}; // column-major
};

class ViewportGL {
public:
    ViewportGL() = default;
    ~ViewportGL();

    ViewportGL(const ViewportGL &) = delete;
    ViewportGL &operator=(const ViewportGL &) = delete;

    bool init(gl33::Dispatch *gl);
    void shutdown();

    void upload_scene(const GeneratedCADScene &scene);
    void upload_trajectory_path(const std::vector<std::array<double, 3>> &traj_pos_m);
    void upload_grid_and_bounds(float extent_m = 2.0f, float step_m = 0.25f);

    void render(int width, int height, const CameraOrbitState &cam, ViewportLayout layout, ShadingMode shading,
                bool dark_canvas, bool show_wake, bool show_cog, const std::array<double, 3> &cog_m,
                const std::array<double, 3> &vehicle_pos_m, const std::array<double, 4> &vehicle_quat_wxyz,
                bool has_solved_stress = false);

    std::uint64_t texture_id() const { return static_cast<std::uint64_t>(color_tex_); }
    bool read_fbo_rgba(int width, int height, std::vector<std::uint8_t> &out_rgba);

private:
    void ensure_fbo(int width, int height);
    void render_single_camera(const Mat4 &vp, const std::array<float, 3> &eye, const Mat4 &model,
                              ShadingMode shading, bool dark_canvas, bool show_wake, bool show_cog,
                              const std::array<double, 3> &cog_m, bool has_solved_stress = false);

    gl33::Dispatch *gl_ = nullptr;
    gl33::GLuint fbo_ = 0;
    gl33::GLuint color_tex_ = 0;
    gl33::GLuint depth_rb_ = 0;
    int fbo_w_ = 0;
    int fbo_h_ = 0;

    gl33::GLuint prog_mesh_ = 0;
    gl33::GLuint prog_line_ = 0;
    gl33::GLuint prog_sky_ = 0;

    gl33::GLuint vao_mesh_ = 0, vbo_mesh_ = 0, ebo_mesh_ = 0;
    gl33::GLsizei mesh_index_count_ = 0;

    gl33::GLuint vao_edges_ = 0, vbo_edges_ = 0;
    gl33::GLsizei edge_vert_count_ = 0;

    gl33::GLuint vao_wake_ = 0, vbo_wake_ = 0;
    gl33::GLsizei wake_vert_count_ = 0;

    gl33::GLuint vao_grid_ = 0, vbo_grid_ = 0;
    gl33::GLsizei grid_vert_count_ = 0;

    gl33::GLuint vao_path_ = 0, vbo_path_ = 0;
    gl33::GLsizei path_vert_count_ = 0;

    gl33::GLuint vao_sky_ = 0, vbo_sky_ = 0;
    gl33::GLuint vao_gizmo_ = 0, vbo_gizmo_ = 0;
};

Mat4 mat4_perspective(float fov_y_rad, float aspect, float z_near, float z_far);
Mat4 mat4_ortho(float half_w, float half_h, float z_near, float z_far);
Mat4 mat4_look_at(std::array<float, 3> eye, std::array<float, 3> target, std::array<float, 3> up);
Mat4 mat4_from_pos_quat(std::array<double, 3> pos, std::array<double, 4> quat_wxyz);
Mat4 mat4_mul(const Mat4 &a, const Mat4 &b);

} // namespace aerolab
