#include "viewport_gl.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace aerolab {
namespace {

constexpr float kPi = std::numbers::pi_v<float>;

const char *kSkyVert = R"GLSL(
#version 330 core
layout (location = 0) in vec2 aPos;
out vec2 vUv;
void main() {
    vUv = aPos * 0.5 + 0.5;
    gl_Position = vec4(aPos, 0.999, 1.0);
}
)GLSL";

const char *kSkyFrag = R"GLSL(
#version 330 core
in vec2 vUv;
out vec4 FragColor;
uniform vec3 uTopColor;
uniform vec3 uBotColor;
void main() {
    FragColor = vec4(mix(uBotColor, uTopColor, smoothstep(0.0, 1.0, vUv.y)), 1.0);
}
)GLSL";

const char *kMeshVert = R"GLSL(
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;
layout (location = 2) in vec3 aColor;
layout (location = 3) in float aCp;
uniform mat4 uModel;
uniform mat4 uVP;
out vec3 vWorldPos;
out vec3 vNormal;
out vec3 vColor;
out float vCp;
void main() {
    vec4 wp = uModel * vec4(aPos, 1.0);
    vWorldPos = wp.xyz;
    vNormal = normalize(mat3(uModel) * aNormal);
    vColor = aColor;
    vCp = aCp;
    gl_Position = uVP * wp;
}
)GLSL";

const char *kMeshFrag = R"GLSL(
#version 330 core
in vec3 vWorldPos;
in vec3 vNormal;
in vec3 vColor;
in float vCp;
uniform vec3 uEyePos;
uniform int uShowCp;
uniform int uHasSolvedStress;
out vec4 FragColor;

vec3 cp_colormap(float cp) {
    float t = clamp((cp + 1.4) / 2.2, 0.0, 1.0);
    vec3 blue = vec3(0.08, 0.30, 0.85);
    vec3 cyan = vec3(0.10, 0.78, 0.75);
    vec3 yellow = vec3(0.95, 0.85, 0.16);
    vec3 red = vec3(0.90, 0.20, 0.15);
    if (t < 0.33) return mix(blue, cyan, t / 0.33);
    if (t < 0.66) return mix(cyan, yellow, (t - 0.33) / 0.33);
    return mix(yellow, red, (t - 0.66) / 0.34);
}

void main() {
    vec3 n = normalize(vNormal);
    vec3 l1 = normalize(vec3(0.55, 0.40, 0.75));
    vec3 l2 = normalize(vec3(-0.65, -0.35, 0.45));
    vec3 v = normalize(uEyePos - vWorldPos);
    float diff1 = max(dot(n, l1), 0.0);
    float diff2 = max(dot(n, l2), 0.0) * 0.35;
    float hemi = 0.5 + 0.5 * n.z;
    vec3 h = normalize(l1 + v);
    float spec = pow(max(dot(n, h), 0.0), 42.0) * 0.22;
    float r_root = length(vWorldPos.xy);
    float stress_scalar = 0.95 * exp(-r_root * 2.1) - 1.1;
    vec3 base = (uShowCp == 1 || (uShowCp == 2 && uHasSolvedStress == 1))
                    ? cp_colormap(vCp)
                    : ((uShowCp == 2) ? cp_colormap(stress_scalar) : vColor);
    vec3 lit = base * (0.34 + 0.18 * hemi + 0.56 * diff1 + diff2) + vec3(spec);
    FragColor = vec4(clamp(lit, 0.0, 1.0), 1.0);
}
)GLSL";

const char *kLineVert = R"GLSL(
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aColor;
uniform mat4 uModel;
uniform mat4 uVP;
out vec3 vColor;
void main() {
    vColor = aColor;
    gl_Position = uVP * uModel * vec4(aPos, 1.0);
}
)GLSL";

const char *kLineFrag = R"GLSL(
#version 330 core
in vec3 vColor;
out vec4 FragColor;
void main() {
    FragColor = vec4(vColor, 1.0);
}
)GLSL";

gl33::GLuint compile_program(gl33::Dispatch *gl, const char *vs_src, const char *fs_src) {
    auto compile = [&](gl33::GLenum type, const char *src) -> gl33::GLuint {
        gl33::GLuint s = gl->CreateShader(type);
        gl->ShaderSource(s, 1, &src, nullptr);
        gl->CompileShader(s);
        gl33::GLint ok = 0;
        gl->GetShaderiv(s, gl33::GL_COMPILE_STATUS_V, &ok);
        if (!ok) {
            gl->DeleteShader(s);
            return 0;
        }
        return s;
    };
    const gl33::GLuint vs = compile(gl33::GL_VERTEX_SHADER_V, vs_src);
    const gl33::GLuint fs = compile(gl33::GL_FRAGMENT_SHADER_V, fs_src);
    if (!vs || !fs) return 0;
    const gl33::GLuint p = gl->CreateProgram();
    gl->AttachShader(p, vs);
    gl->AttachShader(p, fs);
    gl->LinkProgram(p);
    gl->DeleteShader(vs);
    gl->DeleteShader(fs);
    gl33::GLint ok = 0;
    gl->GetProgramiv(p, gl33::GL_LINK_STATUS_V, &ok);
    if (!ok) {
        gl->DeleteProgram(p);
        return 0;
    }
    return p;
}

} // namespace

Mat4 mat4_identity() {
    Mat4 r{};
    r.m[0] = r.m[5] = r.m[10] = r.m[15] = 1.0f;
    return r;
}

Mat4 mat4_mul(const Mat4 &a, const Mat4 &b) {
    Mat4 r{};
    for (int col = 0; col < 4; ++col) {
        for (int row = 0; row < 4; ++row) {
            float sum = 0.0f;
            for (int k = 0; k < 4; ++k) {
                sum += a.m[k * 4 + row] * b.m[col * 4 + k];
            }
            r.m[col * 4 + row] = sum;
        }
    }
    return r;
}

Mat4 mat4_perspective(float fov_y_rad, float aspect, float z_near, float z_far) {
    Mat4 r{};
    const float f = 1.0f / std::tan(fov_y_rad * 0.5f);
    r.m[0] = f / std::max(0.01f, aspect);
    r.m[5] = f;
    r.m[10] = -(z_far + z_near) / (z_far - z_near);
    r.m[11] = -1.0f;
    r.m[14] = -(2.0f * z_far * z_near) / (z_far - z_near);
    return r;
}

Mat4 mat4_ortho(float half_w, float half_h, float z_near, float z_far) {
    Mat4 r{};
    r.m[0] = 1.0f / std::max(0.01f, half_w);
    r.m[5] = 1.0f / std::max(0.01f, half_h);
    r.m[10] = -2.0f / (z_far - z_near);
    r.m[14] = -(z_far + z_near) / (z_far - z_near);
    r.m[15] = 1.0f;
    return r;
}

Mat4 mat4_look_at(std::array<float, 3> eye, std::array<float, 3> target, std::array<float, 3> up) {
    auto norm = [](std::array<float, 3> v) -> std::array<float, 3> {
        const float l = std::sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
        return l > 1e-6f ? std::array<float, 3>{v[0] / l, v[1] / l, v[2] / l} : std::array<float, 3>{0, 0, 1};
    };
    auto cross = [](std::array<float, 3> a, std::array<float, 3> b) -> std::array<float, 3> {
        return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]};
    };
    const auto f = norm({target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]});
    const auto s = norm(cross(f, up));
    const auto u = cross(s, f);
    Mat4 r = mat4_identity();
    r.m[0] = s[0];  r.m[4] = s[1];  r.m[8]  = s[2];
    r.m[1] = u[0];  r.m[5] = u[1];  r.m[9]  = u[2];
    r.m[2] = -f[0]; r.m[6] = -f[1]; r.m[10] = -f[2];
    r.m[12] = -(s[0] * eye[0] + s[1] * eye[1] + s[2] * eye[2]);
    r.m[13] = -(u[0] * eye[0] + u[1] * eye[1] + u[2] * eye[2]);
    r.m[14] = (f[0] * eye[0] + f[1] * eye[1] + f[2] * eye[2]);
    return r;
}

Mat4 mat4_from_pos_quat(std::array<double, 3> pos, std::array<double, 4> quat_wxyz) {
    const double w = quat_wxyz[0], x = quat_wxyz[1], y = quat_wxyz[2], z = quat_wxyz[3];
    Mat4 r = mat4_identity();
    r.m[0] = static_cast<float>(1.0 - 2.0 * (y * y + z * z));
    r.m[1] = static_cast<float>(2.0 * (x * y + w * z));
    r.m[2] = static_cast<float>(2.0 * (x * z - w * y));

    r.m[4] = static_cast<float>(2.0 * (x * y - w * z));
    r.m[5] = static_cast<float>(1.0 - 2.0 * (x * x + z * z));
    r.m[6] = static_cast<float>(2.0 * (y * z + w * x));

    r.m[8] = static_cast<float>(2.0 * (x * z + w * y));
    r.m[9] = static_cast<float>(2.0 * (y * z - w * x));
    r.m[10] = static_cast<float>(1.0 - 2.0 * (x * x + y * y));

    r.m[12] = static_cast<float>(pos[0]);
    r.m[13] = static_cast<float>(pos[1]);
    r.m[14] = static_cast<float>(pos[2]);
    return r;
}

ViewportGL::~ViewportGL() { shutdown(); }

bool ViewportGL::init(gl33::Dispatch *gl) {
    gl_ = gl;
    prog_sky_ = compile_program(gl_, kSkyVert, kSkyFrag);
    prog_mesh_ = compile_program(gl_, kMeshVert, kMeshFrag);
    prog_line_ = compile_program(gl_, kLineVert, kLineFrag);
    if (!prog_sky_ || !prog_mesh_ || !prog_line_) return false;

    const float sky_verts[] = {-1.f, -1.f, 1.f, -1.f, 1.f, 1.f, -1.f, -1.f, 1.f, 1.f, -1.f, 1.f};
    gl_->GenVertexArrays(1, &vao_sky_);
    gl_->GenBuffers(1, &vbo_sky_);
    gl_->BindVertexArray(vao_sky_);
    gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_sky_);
    gl_->BufferData(gl33::GL_ARRAY_BUFFER_V, sizeof(sky_verts), sky_verts, gl33::GL_DYNAMIC_DRAW_V);
    gl_->VertexAttribPointer(0, 2, gl33::GL_FLOAT_V, gl33::GL_FALSE_V, 2 * sizeof(float), nullptr);
    gl_->EnableVertexAttribArray(0);

    gl_->GenVertexArrays(1, &vao_mesh_);
    gl_->GenBuffers(1, &vbo_mesh_);
    gl_->GenBuffers(1, &ebo_mesh_);
    gl_->BindVertexArray(vao_mesh_);
    gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_mesh_);
    gl_->BindBuffer(gl33::GL_ELEMENT_ARRAY_BUFFER_V, ebo_mesh_);
    gl_->VertexAttribPointer(0, 3, gl33::GL_FLOAT_V, gl33::GL_FALSE_V, sizeof(MeshVertex), reinterpret_cast<void *>(0));
    gl_->EnableVertexAttribArray(0);
    gl_->VertexAttribPointer(1, 3, gl33::GL_FLOAT_V, gl33::GL_FALSE_V, sizeof(MeshVertex), reinterpret_cast<void *>(3 * sizeof(float)));
    gl_->EnableVertexAttribArray(1);
    gl_->VertexAttribPointer(2, 3, gl33::GL_FLOAT_V, gl33::GL_FALSE_V, sizeof(MeshVertex), reinterpret_cast<void *>(6 * sizeof(float)));
    gl_->EnableVertexAttribArray(2);
    gl_->VertexAttribPointer(3, 1, gl33::GL_FLOAT_V, gl33::GL_FALSE_V, sizeof(MeshVertex), reinterpret_cast<void *>(9 * sizeof(float)));
    gl_->EnableVertexAttribArray(3);

    auto init_line_vao = [&](gl33::GLuint &vao, gl33::GLuint &vbo) {
        gl_->GenVertexArrays(1, &vao);
        gl_->GenBuffers(1, &vbo);
        gl_->BindVertexArray(vao);
        gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo);
        gl_->VertexAttribPointer(0, 3, gl33::GL_FLOAT_V, gl33::GL_FALSE_V, sizeof(EdgeVertex), reinterpret_cast<void *>(0));
        gl_->EnableVertexAttribArray(0);
        gl_->VertexAttribPointer(1, 3, gl33::GL_FLOAT_V, gl33::GL_FALSE_V, sizeof(EdgeVertex), reinterpret_cast<void *>(3 * sizeof(float)));
        gl_->EnableVertexAttribArray(1);
    };
    init_line_vao(vao_edges_, vbo_edges_);
    init_line_vao(vao_wake_, vbo_wake_);
    init_line_vao(vao_grid_, vbo_grid_);
    init_line_vao(vao_path_, vbo_path_);
    init_line_vao(vao_gizmo_, vbo_gizmo_);

    upload_grid_and_bounds(2.5f, 0.25f);
    return true;
}

void ViewportGL::shutdown() {
    if (!gl_) return;
    if (fbo_) gl_->DeleteFramebuffers(1, &fbo_);
    if (color_tex_) gl_->DeleteTextures(1, &color_tex_);
    if (depth_rb_) gl_->DeleteRenderbuffers(1, &depth_rb_);
    if (prog_sky_) gl_->DeleteProgram(prog_sky_);
    if (prog_mesh_) gl_->DeleteProgram(prog_mesh_);
    if (prog_line_) gl_->DeleteProgram(prog_line_);
    fbo_ = color_tex_ = depth_rb_ = prog_sky_ = prog_mesh_ = prog_line_ = 0;
    gl_ = nullptr;
}

void ViewportGL::ensure_fbo(int width, int height) {
    if (width == fbo_w_ && height == fbo_h_ && fbo_ != 0) return;
    if (fbo_) gl_->DeleteFramebuffers(1, &fbo_);
    if (color_tex_) gl_->DeleteTextures(1, &color_tex_);
    if (depth_rb_) gl_->DeleteRenderbuffers(1, &depth_rb_);
    fbo_w_ = std::max(1, width);
    fbo_h_ = std::max(1, height);

    gl_->GenFramebuffers(1, &fbo_);
    gl_->BindFramebuffer(gl33::GL_FRAMEBUFFER_V, fbo_);

    gl_->GenTextures(1, &color_tex_);
    gl_->BindTexture(gl33::GL_TEXTURE_2D_V, color_tex_);
    gl_->TexImage2D(gl33::GL_TEXTURE_2D_V, 0, gl33::GL_RGBA8_V, fbo_w_, fbo_h_, 0, gl33::GL_RGBA_V, gl33::GL_UNSIGNED_BYTE_V, nullptr);
    gl_->TexParameteri(gl33::GL_TEXTURE_2D_V, gl33::GL_TEXTURE_MIN_FILTER_V, gl33::GL_LINEAR_V);
    gl_->TexParameteri(gl33::GL_TEXTURE_2D_V, gl33::GL_TEXTURE_MAG_FILTER_V, gl33::GL_LINEAR_V);
    gl_->TexParameteri(gl33::GL_TEXTURE_2D_V, gl33::GL_TEXTURE_WRAP_S_V, gl33::GL_CLAMP_TO_EDGE_V);
    gl_->TexParameteri(gl33::GL_TEXTURE_2D_V, gl33::GL_TEXTURE_WRAP_T_V, gl33::GL_CLAMP_TO_EDGE_V);
    gl_->FramebufferTexture2D(gl33::GL_FRAMEBUFFER_V, gl33::GL_COLOR_ATTACHMENT0_V, gl33::GL_TEXTURE_2D_V, color_tex_, 0);

    gl_->GenRenderbuffers(1, &depth_rb_);
    gl_->BindRenderbuffer(gl33::GL_RENDERBUFFER_V, depth_rb_);
    gl_->RenderbufferStorage(gl33::GL_RENDERBUFFER_V, gl33::GL_DEPTH_COMPONENT24_V, fbo_w_, fbo_h_);
    gl_->FramebufferRenderbuffer(gl33::GL_FRAMEBUFFER_V, gl33::GL_DEPTH_ATTACHMENT_V, gl33::GL_RENDERBUFFER_V, depth_rb_);

    gl_->BindFramebuffer(gl33::GL_FRAMEBUFFER_V, 0);
}

void ViewportGL::upload_scene(const GeneratedCADScene &scene) {
    if (!gl_) return;
    gl_->BindVertexArray(vao_mesh_);
    gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_mesh_);
    gl_->BufferData(gl33::GL_ARRAY_BUFFER_V, static_cast<gl33::GLsizeiptr>(scene.vertices.size() * sizeof(MeshVertex)),
                    scene.vertices.empty() ? nullptr : scene.vertices.data(), gl33::GL_DYNAMIC_DRAW_V);
    gl_->BindBuffer(gl33::GL_ELEMENT_ARRAY_BUFFER_V, ebo_mesh_);
    gl_->BufferData(gl33::GL_ELEMENT_ARRAY_BUFFER_V, static_cast<gl33::GLsizeiptr>(scene.indices.size() * sizeof(std::uint32_t)),
                    scene.indices.empty() ? nullptr : scene.indices.data(), gl33::GL_DYNAMIC_DRAW_V);
    mesh_index_count_ = static_cast<gl33::GLsizei>(scene.indices.size());

    gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_edges_);
    gl_->BufferData(gl33::GL_ARRAY_BUFFER_V, static_cast<gl33::GLsizeiptr>(scene.cad_edges.size() * sizeof(EdgeVertex)),
                    scene.cad_edges.empty() ? nullptr : scene.cad_edges.data(), gl33::GL_DYNAMIC_DRAW_V);
    edge_vert_count_ = static_cast<gl33::GLsizei>(scene.cad_edges.size());

    gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_wake_);
    gl_->BufferData(gl33::GL_ARRAY_BUFFER_V, static_cast<gl33::GLsizeiptr>(scene.wake_lines.size() * sizeof(EdgeVertex)),
                    scene.wake_lines.empty() ? nullptr : scene.wake_lines.data(), gl33::GL_DYNAMIC_DRAW_V);
    wake_vert_count_ = static_cast<gl33::GLsizei>(scene.wake_lines.size());
}

void ViewportGL::upload_trajectory_path(const std::vector<std::array<double, 3>> &traj_pos_m) {
    if (!gl_) return;
    std::vector<EdgeVertex> path_verts;
    path_verts.reserve(traj_pos_m.size());
    for (const auto &pt : traj_pos_m) {
        path_verts.push_back({static_cast<float>(pt[0]), static_cast<float>(pt[1]), static_cast<float>(pt[2]),
                              0.10f, 0.36f, 0.88f});
    }
    gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_path_);
    gl_->BufferData(gl33::GL_ARRAY_BUFFER_V, static_cast<gl33::GLsizeiptr>(path_verts.size() * sizeof(EdgeVertex)),
                    path_verts.empty() ? nullptr : path_verts.data(), gl33::GL_DYNAMIC_DRAW_V);
    path_vert_count_ = static_cast<gl33::GLsizei>(path_verts.size());
}

void ViewportGL::upload_grid_and_bounds(float extent_m, float step_m) {
    std::vector<EdgeVertex> lines;
    const int n = static_cast<int>(std::round(extent_m / step_m));
    for (int i = -n; i <= n; ++i) {
        const float p = static_cast<float>(i) * step_m;
        const bool major = (i % 4 == 0);
        const float c = major ? 0.72f : 0.85f;
        if (i == 0) {
            lines.push_back({-extent_m, 0.0f, -0.002f, 0.82f, 0.25f, 0.25f});
            lines.push_back({extent_m, 0.0f, -0.002f, 0.82f, 0.25f, 0.25f});
            lines.push_back({0.0f, -extent_m, -0.002f, 0.22f, 0.65f, 0.28f});
            lines.push_back({0.0f, extent_m, -0.002f, 0.22f, 0.65f, 0.28f});
        } else {
            lines.push_back({-extent_m, p, -0.002f, c, c + 0.02f, c + 0.04f});
            lines.push_back({extent_m, p, -0.002f, c, c + 0.02f, c + 0.04f});
            lines.push_back({p, -extent_m, -0.002f, c, c + 0.02f, c + 0.04f});
            lines.push_back({p, extent_m, -0.002f, c, c + 0.02f, c + 0.04f});
        }
    }
    gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_grid_);
    gl_->BufferData(gl33::GL_ARRAY_BUFFER_V, static_cast<gl33::GLsizeiptr>(lines.size() * sizeof(EdgeVertex)),
                    lines.data(), gl33::GL_DYNAMIC_DRAW_V);
    grid_vert_count_ = static_cast<gl33::GLsizei>(lines.size());
}

void ViewportGL::render_single_camera(const Mat4 &vp, const std::array<float, 3> &eye, const Mat4 &model,
                                      ShadingMode shading, bool dark_canvas, bool show_wake, bool show_cog,
                                      const std::array<double, 3> &cog_m, bool has_solved_stress) {
    // 1. Gradient studio sky background
    gl_->Disable(gl33::GL_DEPTH_TEST_V);
    gl_->DepthMask(gl33::GL_FALSE_V);
    gl_->UseProgram(prog_sky_);
    const float top_c[3] = {dark_canvas ? 0.13f : 0.96f, dark_canvas ? 0.15f : 0.97f, dark_canvas ? 0.19f : 0.99f};
    const float bot_c[3] = {dark_canvas ? 0.08f : 0.86f, dark_canvas ? 0.09f : 0.90f, dark_canvas ? 0.12f : 0.94f};
    gl_->Uniform3fv(gl_->GetUniformLocation(prog_sky_, "uTopColor"), 1, top_c);
    gl_->Uniform3fv(gl_->GetUniformLocation(prog_sky_, "uBotColor"), 1, bot_c);
    gl_->BindVertexArray(vao_sky_);
    gl_->DrawArrays(gl33::GL_TRIANGLES_V, 0, 6);

    gl_->DepthMask(gl33::GL_TRUE_V);
    gl_->Enable(gl33::GL_DEPTH_TEST_V);
    gl_->DepthFunc(gl33::GL_LEQUAL_V);

    // 2. Ground engineering grid (world identity)
    const Mat4 id = mat4_identity();
    gl_->UseProgram(prog_line_);
    gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uModel"), 1, gl33::GL_FALSE_V, id.m);
    gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uVP"), 1, gl33::GL_FALSE_V, vp.m);
    gl_->BindVertexArray(vao_grid_);
    gl_->DrawArrays(gl33::GL_LINES_V, 0, grid_vert_count_);

    // 3. Solid CAD geometry (with polygon offset so edges remain crisp)
    if (mesh_index_count_ > 0 && shading != ShadingMode::Wireframe) {
        gl_->Enable(gl33::GL_POLYGON_OFFSET_FILL_V);
        gl_->PolygonOffset(1.0f, 1.0f);
        gl_->UseProgram(prog_mesh_);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_mesh_, "uModel"), 1, gl33::GL_FALSE_V, model.m);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_mesh_, "uVP"), 1, gl33::GL_FALSE_V, vp.m);
        gl_->Uniform3fv(gl_->GetUniformLocation(prog_mesh_, "uEyePos"), 1, eye.data());
        const int mode_i = (shading == ShadingMode::SurfaceCp) ? 1 : (shading == ShadingMode::StressVonMises ? 2 : 0);
        gl_->Uniform1i(gl_->GetUniformLocation(prog_mesh_, "uShowCp"), mode_i);
        gl_->Uniform1i(gl_->GetUniformLocation(prog_mesh_, "uHasSolvedStress"), has_solved_stress ? 1 : 0);
        gl_->BindVertexArray(vao_mesh_);
        gl_->DrawElements(gl33::GL_TRIANGLES_V, mesh_index_count_, gl33::GL_UNSIGNED_INT_V, nullptr);
        gl_->Disable(gl33::GL_POLYGON_OFFSET_FILL_V);
    }

    // 4. Crisp CAD crease & silhouette edges
    if (edge_vert_count_ > 0 && shading != ShadingMode::ShadedOnly) {
        gl_->UseProgram(prog_line_);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uModel"), 1, gl33::GL_FALSE_V, model.m);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uVP"), 1, gl33::GL_FALSE_V, vp.m);
        gl_->BindVertexArray(vao_edges_);
        gl_->DrawArrays(gl33::GL_LINES_V, 0, edge_vert_count_);
    }

    // 5. Trailing aerodynamic vortex wake filaments
    if (show_wake && wake_vert_count_ > 0) {
        gl_->UseProgram(prog_line_);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uModel"), 1, gl33::GL_FALSE_V, model.m);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uVP"), 1, gl33::GL_FALSE_V, vp.m);
        gl_->BindVertexArray(vao_wake_);
        gl_->DrawArrays(gl33::GL_LINES_V, 0, wake_vert_count_);
    }

    // 5b. 6-DoF simulated trajectory ribbon in world frame
    if (path_vert_count_ > 1) {
        gl_->UseProgram(prog_line_);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uModel"), 1, gl33::GL_FALSE_V, id.m);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uVP"), 1, gl33::GL_FALSE_V, vp.m);
        gl_->BindVertexArray(vao_path_);
        gl_->DrawArrays(gl33::GL_LINE_STRIP_V, 0, path_vert_count_);
    }

    // 6. CoG datum crosshair
    if (show_cog) {
        const float cx = static_cast<float>(cog_m[0]);
        const float cy = static_cast<float>(cog_m[1]);
        const float cz = static_cast<float>(cog_m[2]);
        const float s = 0.08f;
        const EdgeVertex cog_cross[] = {
            {cx - s, cy, cz, 0.90f, 0.15f, 0.15f}, {cx + s, cy, cz, 0.90f, 0.15f, 0.15f},
            {cx, cy - s, cz, 0.15f, 0.72f, 0.25f}, {cx, cy + s, cz, 0.15f, 0.72f, 0.25f},
            {cx, cy, cz - s, 0.15f, 0.42f, 0.92f}, {cx, cy, cz + s, 0.15f, 0.42f, 0.92f},
        };
        gl_->BindBuffer(gl33::GL_ARRAY_BUFFER_V, vbo_gizmo_);
        gl_->BufferData(gl33::GL_ARRAY_BUFFER_V, sizeof(cog_cross), cog_cross, gl33::GL_DYNAMIC_DRAW_V);
        gl_->UseProgram(prog_line_);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uModel"), 1, gl33::GL_FALSE_V, model.m);
        gl_->UniformMatrix4fv(gl_->GetUniformLocation(prog_line_, "uVP"), 1, gl33::GL_FALSE_V, vp.m);
        gl_->BindVertexArray(vao_gizmo_);
        gl_->DrawArrays(gl33::GL_LINES_V, 0, 6);
    }
}

void ViewportGL::render(int width, int height, const CameraOrbitState &cam, ViewportLayout layout, ShadingMode shading,
                        bool dark_canvas, bool show_wake, bool show_cog, const std::array<double, 3> &cog_m,
                        const std::array<double, 3> &vehicle_pos_m, const std::array<double, 4> &vehicle_quat_wxyz,
                        bool has_solved_stress) {
    if (!gl_ || width <= 0 || height <= 0) return;
    ensure_fbo(width, height);
    gl_->BindFramebuffer(gl33::GL_FRAMEBUFFER_V, fbo_);
    gl_->Enable(gl33::GL_SCISSOR_TEST_V);
    gl_->Viewport(0, 0, fbo_w_, fbo_h_);
    gl_->Scissor(0, 0, fbo_w_, fbo_h_);
    gl_->ClearColor(0.92f, 0.94f, 0.97f, 1.0f);
    gl_->Clear(gl33::GL_COLOR_BUFFER_BIT_V | gl33::GL_DEPTH_BUFFER_BIT_V);

    const Mat4 model = mat4_from_pos_quat(vehicle_pos_m, vehicle_quat_wxyz);
    const float yaw = cam.yaw_deg * kPi / 180.0f;
    const float pitch = std::clamp(cam.pitch_deg, -85.0f, 85.0f) * kPi / 180.0f;
    const std::array<float, 3> iso_eye{
        cam.target_m[0] + cam.distance_m * std::cos(pitch) * std::cos(yaw),
        cam.target_m[1] + cam.distance_m * std::cos(pitch) * std::sin(yaw),
        cam.target_m[2] + cam.distance_m * std::sin(pitch),
    };

    if (layout == ViewportLayout::Single3D) {
        const float aspect = static_cast<float>(fbo_w_) / static_cast<float>(fbo_h_);
        const Mat4 proj = mat4_perspective(42.0f * kPi / 180.0f, aspect, 0.04f, 80.0f);
        const Mat4 view = mat4_look_at(iso_eye, cam.target_m, {0.0f, 0.0f, 1.0f});
        render_single_camera(mat4_mul(proj, view), iso_eye, model, shading, dark_canvas, show_wake, show_cog, cog_m,
                             has_solved_stress);
    } else {
        const int hw = std::max(1, fbo_w_ / 2);
        const int hh = std::max(1, fbo_h_ / 2);
        const float q_aspect = static_cast<float>(hw) / static_cast<float>(hh);
        const float half_span = std::max(0.35f, cam.distance_m * 0.58f);
        const Mat4 ortho_p = mat4_ortho(half_span * q_aspect, half_span, 0.05f, 50.0f);

        // Top-Left: TOP Ortho (+Z looking down, nose +X pointing up)
        gl_->Viewport(0, hh, hw - 1, hh);
        gl_->Scissor(0, hh, hw - 1, hh);
        const std::array<float, 3> top_eye{cam.target_m[0], cam.target_m[1], cam.target_m[2] + 6.0f};
        render_single_camera(mat4_mul(ortho_p, mat4_look_at(top_eye, cam.target_m, {1.0f, 0.0f, 0.0f})),
                             top_eye, model, shading, dark_canvas, show_wake, show_cog, cog_m, has_solved_stress);

        // Top-Right: SIDE Ortho (+Y looking towards aircraft)
        gl_->Viewport(hw + 1, hh, fbo_w_ - hw - 1, hh);
        gl_->Scissor(hw + 1, hh, fbo_w_ - hw - 1, hh);
        const std::array<float, 3> side_eye{cam.target_m[0], cam.target_m[1] + 6.0f, cam.target_m[2]};
        render_single_camera(mat4_mul(ortho_p, mat4_look_at(side_eye, cam.target_m, {0.0f, 0.0f, 1.0f})),
                             side_eye, model, shading, dark_canvas, show_wake, show_cog, cog_m, has_solved_stress);

        // Bottom-Left: FRONT Ortho (+X looking aft)
        gl_->Viewport(0, 0, hw - 1, hh - 1);
        gl_->Scissor(0, 0, hw - 1, hh - 1);
        const std::array<float, 3> front_eye{cam.target_m[0] + 6.0f, cam.target_m[1], cam.target_m[2]};
        render_single_camera(mat4_mul(ortho_p, mat4_look_at(front_eye, cam.target_m, {0.0f, 0.0f, 1.0f})),
                             front_eye, model, shading, dark_canvas, show_wake, show_cog, cog_m, has_solved_stress);

        // Bottom-Right: 3D ISO Perspective
        gl_->Viewport(hw + 1, 0, fbo_w_ - hw - 1, hh - 1);
        gl_->Scissor(hw + 1, 0, fbo_w_ - hw - 1, hh - 1);
        const Mat4 proj = mat4_perspective(42.0f * kPi / 180.0f, q_aspect, 0.04f, 80.0f);
        render_single_camera(mat4_mul(proj, mat4_look_at(iso_eye, cam.target_m, {0.0f, 0.0f, 1.0f})),
                             iso_eye, model, shading, dark_canvas, show_wake, show_cog, cog_m, has_solved_stress);
    }

    gl_->Disable(gl33::GL_SCISSOR_TEST_V);
    gl_->BindFramebuffer(gl33::GL_FRAMEBUFFER_V, 0);
}

bool ViewportGL::read_fbo_rgba(int width, int height, std::vector<std::uint8_t> &out_rgba) {
    if (!gl_ || !fbo_ || width <= 0 || height <= 0) return false;
    gl_->BindFramebuffer(gl33::GL_FRAMEBUFFER_V, fbo_);
    out_rgba.resize(static_cast<std::size_t>(width) * height * 4);
    gl_->ReadPixels(0, 0, width, height, gl33::GL_RGBA_V, gl33::GL_UNSIGNED_BYTE_V, out_rgba.data());
    gl_->BindFramebuffer(gl33::GL_FRAMEBUFFER_V, 0);
    return true;
}

} // namespace aerolab
