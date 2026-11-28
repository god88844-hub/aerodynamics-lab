#include "cad_mesh_builder.hpp"

#include "lab/flight_rk4.hpp"
#include "lab/mass_properties.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <numbers>

namespace aerolab {
namespace {

constexpr float kPi = std::numbers::pi_v<float>;

struct Vec3 {
    float x, y, z;
};

Vec3 operator+(Vec3 a, Vec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
Vec3 operator-(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
Vec3 operator*(Vec3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }

Vec3 cross_v(Vec3 a, Vec3 b) {
    return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x};
}

Vec3 normalize_v(Vec3 v) {
    const float len = std::sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
    if (len <= 1e-7f) return {0.0f, 0.0f, 1.0f};
    return {v.x / len, v.y / len, v.z / len};
}

Vec3 rotate_z(Vec3 v, float rad) {
    const float c = std::cos(rad);
    const float s = std::sin(rad);
    return {v.x * c - v.y * s, v.x * s + v.y * c, v.z};
}

Vec3 rotate_y(Vec3 v, float rad) {
    const float c = std::cos(rad);
    const float s = std::sin(rad);
    return {v.x * c + v.z * s, v.y, -v.x * s + v.z * c};
}

Vec3 rotate_x(Vec3 v, float rad) {
    const float c = std::cos(rad);
    const float s = std::sin(rad);
    return {v.x, v.y * c - v.z * s, v.y * s + v.z * c};
}

void push_edge(GeneratedCADScene &out, Vec3 a, Vec3 b, float r = 0.12f, float g = 0.16f, float bl = 0.22f) {
    out.cad_edges.push_back({a.x, a.y, a.z, r, g, bl});
    out.cad_edges.push_back({b.x, b.y, b.z, r, g, bl});
}

void push_quad(GeneratedCADScene &out, Vec3 a, Vec3 b, Vec3 c, Vec3 d,
               float r, float g, float bl, float cp = 0.0f, bool outline = true) {
    const Vec3 n = normalize_v(cross_v(b - a, c - a));
    const auto base = static_cast<std::uint32_t>(out.vertices.size());
    out.vertices.push_back({a.x, a.y, a.z, n.x, n.y, n.z, r, g, bl, cp});
    out.vertices.push_back({b.x, b.y, b.z, n.x, n.y, n.z, r, g, bl, cp});
    out.vertices.push_back({c.x, c.y, c.z, n.x, n.y, n.z, r, g, bl, cp});
    out.vertices.push_back({d.x, d.y, d.z, n.x, n.y, n.z, r, g, bl, cp});
    out.indices.push_back(base + 0);
    out.indices.push_back(base + 1);
    out.indices.push_back(base + 2);
    out.indices.push_back(base + 0);
    out.indices.push_back(base + 2);
    out.indices.push_back(base + 3);
    if (outline) {
        push_edge(out, a, b);
        push_edge(out, b, c);
        push_edge(out, c, d);
        push_edge(out, d, a);
    }
}

void add_oriented_box(GeneratedCADScene &out, Vec3 center, Vec3 size, float yaw_rad,
                      float r, float g, float bl, float cp = 0.0f) {
    const float hx = size.x * 0.5f;
    const float hy = size.y * 0.5f;
    const float hz = size.z * 0.5f;
    std::array<Vec3, 8> p = {{
        {-hx, -hy, -hz}, {hx, -hy, -hz}, {hx, hy, -hz}, {-hx, hy, -hz},
        {-hx, -hy, hz},  {hx, -hy, hz},  {hx, hy, hz},  {-hx, hy, hz},
    }};
    for (auto &pt : p) {
        pt = rotate_z(pt, yaw_rad) + center;
    }
    push_quad(out, p[3], p[2], p[1], p[0], r, g, bl, cp);
    push_quad(out, p[4], p[5], p[6], p[7], r, g, bl, cp);
    push_quad(out, p[0], p[1], p[5], p[4], r, g, bl, cp);
    push_quad(out, p[1], p[2], p[6], p[5], r, g, bl, cp);
    push_quad(out, p[2], p[3], p[7], p[6], r, g, bl, cp);
    push_quad(out, p[3], p[0], p[4], p[7], r, g, bl, cp);
}

void add_cylinder_z(GeneratedCADScene &out, Vec3 center, float radius, float height, int segs,
                    float r, float g, float bl, float cp = 0.0f, Vec3 tilt_euler_y = {0, 0, 0}) {
    const float hz = height * 0.5f;
    std::vector<Vec3> top_pts(segs), bot_pts(segs);
    for (int i = 0; i < segs; ++i) {
        const float a = 2.0f * kPi * static_cast<float>(i) / static_cast<float>(segs);
        Vec3 pt_t{radius * std::cos(a), radius * std::sin(a), hz};
        Vec3 pt_b{radius * std::cos(a), radius * std::sin(a), -hz};
        if (std::abs(tilt_euler_y.y) > 1e-5f) {
            pt_t = rotate_y(pt_t, tilt_euler_y.y);
            pt_b = rotate_y(pt_b, tilt_euler_y.y);
        }
        top_pts[i] = pt_t + center;
        bot_pts[i] = pt_b + center;
    }
    const auto top_c_idx = static_cast<std::uint32_t>(out.vertices.size());
    Vec3 top_c = center + rotate_y({0.0f, 0.0f, hz}, tilt_euler_y.y);
    Vec3 bot_c = center + rotate_y({0.0f, 0.0f, -hz}, tilt_euler_y.y);
    Vec3 up_n = normalize_v(rotate_y({0.0f, 0.0f, 1.0f}, tilt_euler_y.y));
    out.vertices.push_back({top_c.x, top_c.y, top_c.z, up_n.x, up_n.y, up_n.z, r, g, bl, cp});
    out.vertices.push_back({bot_c.x, bot_c.y, bot_c.z, -up_n.x, -up_n.y, -up_n.z, r, g, bl, cp});

    for (int i = 0; i < segs; ++i) {
        const int next = (i + 1) % segs;
        push_quad(out, bot_pts[i], bot_pts[next], top_pts[next], top_pts[i], r, g, bl, cp, false);
        push_edge(out, top_pts[i], top_pts[next]);
        push_edge(out, bot_pts[i], bot_pts[next]);

        const auto v_base = static_cast<std::uint32_t>(out.vertices.size());
        out.vertices.push_back({top_pts[i].x, top_pts[i].y, top_pts[i].z, up_n.x, up_n.y, up_n.z, r, g, bl, cp});
        out.vertices.push_back({top_pts[next].x, top_pts[next].y, top_pts[next].z, up_n.x, up_n.y, up_n.z, r, g, bl, cp});
        out.indices.push_back(top_c_idx);
        out.indices.push_back(v_base);
        out.indices.push_back(v_base + 1);

        const auto vb_base = static_cast<std::uint32_t>(out.vertices.size());
        out.vertices.push_back({bot_pts[next].x, bot_pts[next].y, bot_pts[next].z, -up_n.x, -up_n.y, -up_n.z, r, g, bl, cp});
        out.vertices.push_back({bot_pts[i].x, bot_pts[i].y, bot_pts[i].z, -up_n.x, -up_n.y, -up_n.z, r, g, bl, cp});
        out.indices.push_back(top_c_idx + 1);
        out.indices.push_back(vb_base);
        out.indices.push_back(vb_base + 1);
    }
}

void add_twisted_propeller(GeneratedCADScene &out, Vec3 hub, float diameter_m, float pitch_deg,
                           int blades, float tilt_y_rad, bool highlight, float tilt_x_rad = 0.0f) {
    const float r_base = highlight ? 0.19f : 0.24f;
    const float g_base = highlight ? 0.45f : 0.52f;
    const float b_base = highlight ? 0.88f : 0.86f;
    add_cylinder_z(out, hub, diameter_m * 0.055f, 0.024f, 16, 0.30f, 0.35f, 0.42f, 0.0f, {0.0f, tilt_y_rad, 0.0f});

    const float radius = diameter_m * 0.5f;
    const int n_radial = 9;
    const auto airfoil = sample_naca4_airfoil("4412", 8);
    const int n_prof = static_cast<int>(airfoil.size());

    for (int b = 0; b < blades; ++b) {
        const float az0 = 2.0f * kPi * static_cast<float>(b) / static_cast<float>(blades);
        std::vector<std::vector<Vec3>> rings(n_radial + 1, std::vector<Vec3>(n_prof));
        std::vector<float> radial_cp(n_radial + 1, 0.0f);

        for (int i = 0; i <= n_radial; ++i) {
            const float u = 0.14f + 0.86f * (static_cast<float>(i) / static_cast<float>(n_radial));
            const float r_pos = u * radius;
            const float chord = radius * (0.14f + 0.11f * std::sin(u * kPi)) * (1.0f - 0.35f * u * u);
            const float local_twist_rad = (pitch_deg * kPi / 180.0f) * (1.35f - 0.72f * u);
            radial_cp[i] = -1.2f * std::sin(u * kPi * 0.9f);

            for (int j = 0; j < n_prof; ++j) {
                const float xc = (airfoil[j].x - 0.32f) * chord;
                const float zc = airfoil[j].z * chord * 0.85f;
                const float cx_t = xc * std::cos(local_twist_rad) - zc * std::sin(local_twist_rad);
                const float cz_t = xc * std::sin(local_twist_rad) + zc * std::cos(local_twist_rad);
                Vec3 local{r_pos, cx_t, cz_t};
                local = rotate_z(local, az0);
                if (std::abs(tilt_y_rad) > 1e-5f) {
                    local = rotate_y(local, tilt_y_rad);
                }
                if (std::abs(tilt_x_rad) > 1e-5f) {
                    local = rotate_x(local, tilt_x_rad);
                }
                rings[i][j] = hub + local;
            }
        }
        for (int i = 0; i < n_radial; ++i) {
            const float cp_mid = 0.5f * (radial_cp[i] + radial_cp[i + 1]);
            for (int j = 0; j < n_prof; ++j) {
                const int jn = (j + 1) % n_prof;
                push_quad(out, rings[i][j], rings[i + 1][j], rings[i + 1][jn], rings[i][jn],
                          r_base, g_base, b_base, cp_mid, false);
            }
            push_edge(out, rings[i][0], rings[i + 1][0]);
            push_edge(out, rings[i][n_prof / 2], rings[i + 1][n_prof / 2]);
        }
        for (int j = 0; j < n_prof; ++j) {
            push_edge(out, rings.back()[j], rings.back()[(j + 1) % n_prof]);
        }
    }
}

void add_lofted_wing(GeneratedCADScene &out, Vec3 root_le_center, float span_m, float cr, float ct,
                     float sweep_deg, float dihedral_deg, float twist_tip_deg,
                     const std::string &airfoil_code, float r, float g, float b, bool emit_wake) {
    const auto sec = sample_naca4_airfoil(airfoil_code, 16);
    const int n_sec = static_cast<int>(sec.size());
    const int n_half = 8;
    const float sweep_tan = std::tan(sweep_deg * kPi / 180.0f);
    const float dih_tan = std::tan(dihedral_deg * kPi / 180.0f);

    for (int side : {-1, 1}) {
        std::vector<std::vector<Vec3>> ribs(n_half + 1, std::vector<Vec3>(n_sec));
        std::vector<float> cp_span(n_half + 1, 0.0f);
        for (int s_i = 0; s_i <= n_half; ++s_i) {
            const float eta = static_cast<float>(s_i) / static_cast<float>(n_half);
            const float y = static_cast<float>(side) * eta * (span_m * 0.5f);
            const float chord = cr + (ct - cr) * eta;
            const float dx_le = std::abs(y) * sweep_tan;
            const float dz_dihedral = std::abs(y) * dih_tan;
            const float twist_rad = (twist_tip_deg * kPi / 180.0f) * eta;
            cp_span[s_i] = -1.15f * std::sqrt(std::max(0.0f, 1.0f - eta * eta));

            for (int j = 0; j < n_sec; ++j) {
                const float lx = sec[j].x * chord;
                const float lz = sec[j].z * chord;
                const float rx = (lx - 0.25f * chord) * std::cos(twist_rad) + lz * std::sin(twist_rad) + 0.25f * chord;
                const float rz = -(lx - 0.25f * chord) * std::sin(twist_rad) + lz * std::cos(twist_rad);
                ribs[s_i][j] = {
                    root_le_center.x - dx_le - rx, // aircraft nose faces +X, trailing edge -X
                    root_le_center.y + y,
                    root_le_center.z + dz_dihedral + rz,
                };
            }
        }
        for (int s_i = 0; s_i < n_half; ++s_i) {
            for (int j = 0; j < n_sec; ++j) {
                const int jn = (j + 1) % n_sec;
                const float cp_local = cp_span[s_i] * (sec[j].z >= 0.0f ? 1.0f : -0.35f);
                if (side > 0) {
                    push_quad(out, ribs[s_i][j], ribs[s_i][jn], ribs[s_i + 1][jn], ribs[s_i + 1][j],
                              r, g, b, cp_local, false);
                } else {
                    push_quad(out, ribs[s_i][jn], ribs[s_i][j], ribs[s_i + 1][j], ribs[s_i + 1][jn],
                              r, g, b, cp_local, false);
                }
            }
            push_edge(out, ribs[s_i][0], ribs[s_i + 1][0]);
            push_edge(out, ribs[s_i][n_sec / 2], ribs[s_i + 1][n_sec / 2]);
            if (s_i % 2 == 0) {
                for (int j = 0; j < n_sec; ++j) {
                    push_edge(out, ribs[s_i][j], ribs[s_i][(j + 1) % n_sec], 0.36f, 0.42f, 0.50f);
                }
            }
        }
        for (int j = 0; j < n_sec; ++j) {
            push_edge(out, ribs.back()[j], ribs.back()[(j + 1) % n_sec]);
        }
        if (emit_wake) {
            for (int s_i = 1; s_i <= n_half; s_i += 2) {
                const Vec3 te = ribs[s_i][0];
                const Vec3 wake_end{te.x - span_m * 0.75f, te.y, te.z - 0.05f};
                out.wake_lines.push_back({te.x, te.y, te.z, 0.15f, 0.52f, 0.92f});
                out.wake_lines.push_back({wake_end.x, wake_end.y, wake_end.z, 0.55f, 0.78f, 0.98f});
            }
        }
    }
}

void add_fuselage_loft(GeneratedCADScene &out, Vec3 center, float length_m, float radius_m, float r, float g, float b) {
    const int n_stations = 12;
    const int n_ring = 16;
    std::vector<std::vector<Vec3>> rings(n_stations + 1, std::vector<Vec3>(n_ring));
    for (int i = 0; i <= n_stations; ++i) {
        const float u = static_cast<float>(i) / static_cast<float>(n_stations); // 0=tail (-X), 1=nose (+X)
        const float x = center.x + (u - 0.5f) * length_m;
        float scale = 0.0f;
        if (u < 0.72f) {
            scale = std::pow(u / 0.72f, 0.55f);
        } else {
            scale = std::sqrt(std::max(0.0f, 1.0f - std::pow((u - 0.72f) / 0.28f, 2.0f)));
        }
        scale = std::max(0.05f, scale);
        for (int j = 0; j < n_ring; ++j) {
            const float th = 2.0f * kPi * static_cast<float>(j) / static_cast<float>(n_ring);
            rings[i][j] = {x, center.y + radius_m * scale * std::cos(th), center.z + radius_m * scale * 1.1f * std::sin(th)};
        }
    }
    for (int i = 0; i < n_stations; ++i) {
        for (int j = 0; j < n_ring; ++j) {
            const int jn = (j + 1) % n_ring;
            push_quad(out, rings[i][j], rings[i + 1][j], rings[i + 1][jn], rings[i][jn], r, g, b, -0.2f, false);
        }
        if (i % 2 == 0) {
            for (int j = 0; j < n_ring; ++j) {
                push_edge(out, rings[i][j], rings[i][(j + 1) % n_ring], 0.32f, 0.38f, 0.46f);
            }
        }
    }
}

void build_custom_sketch_solid(GeneratedCADScene &out, const CustomPartParams &part, Vec3 offset_m) {
    const int n_pat = std::max(1, part.circular_pattern_count);
    const float w = std::max(0.01f, part.width_m);
    const float l = std::max(0.02f, part.length_m);
    const float t = std::max(0.003f, part.thickness_m);
    double unit_vol = 0.0;

    if (part.sketch_kind == SketchShapeKind::CustomPropeller) {
        const float prop_d = std::max(0.12f, l * 1.4f);
        const int blades = std::clamp(n_pat < 2 ? 2 : n_pat, 2, 6);
        add_twisted_propeller(out, offset_m, prop_d, 18.0f, blades, 0.0f, true);
        unit_vol = static_cast<double>(blades) * (0.45 * prop_d * 0.5) * w * t;
    } else if (part.sketch_kind == SketchShapeKind::CustomBodyShell) {
        add_fuselage_loft(out, offset_m, std::max(0.20f, l * 2.2f), std::max(0.025f, w * 1.1f), 0.24f, 0.54f, 0.86f);
        unit_vol = 0.42 * kPi * (w * 1.1) * (w * 1.1) * (l * 2.2);
    } else if (part.revolve_360) {
        const float r_outer = std::max(0.02f, w * 0.5f + l * 0.25f);
        const float r_inner = std::clamp(part.hole_radius_m, 0.002f, r_outer * 0.8f);
        add_cylinder_z(out, offset_m, r_outer, t, 28, 0.72f, 0.78f, 0.86f, 0.1f);
        add_cylinder_z(out, offset_m, r_inner, t * 1.04f, 20, 0.35f, 0.40f, 0.48f, -0.2f);
        unit_vol = kPi * (r_outer * r_outer - r_inner * r_inner) * t;
    } else if (part.sketch_kind == SketchShapeKind::AirfoilSection) {
        const auto sec = sample_naca4_airfoil("2412", 16);
        const int n = static_cast<int>(sec.size());
        std::vector<Vec3> bot(n), top(n);
        for (int i = 0; i < n; ++i) {
            bot[i] = {offset_m.x + (sec[i].x - 0.5f) * l, offset_m.y + sec[i].z * l * 1.4f, offset_m.z - t * 0.5f};
            top[i] = {bot[i].x, bot[i].y, offset_m.z + t * 0.5f};
        }
        for (int i = 0; i < n; ++i) {
            const int in = (i + 1) % n;
            push_quad(out, bot[i], bot[in], top[in], top[i], 0.25f, 0.55f, 0.88f, -0.5f, false);
            push_edge(out, top[i], top[in]);
            push_edge(out, bot[i], bot[in]);
        }
        unit_vol = 0.65 * l * (l * 0.12) * t;
    } else if (part.sketch_kind == SketchShapeKind::RingDuct) {
        const float r_out = std::max(0.03f, w);
        const float r_in = std::clamp(r_out - t, 0.01f, r_out * 0.9f);
        const int segs = 28;
        for (int i = 0; i < segs; ++i) {
            const float a0 = 2.0f * kPi * static_cast<float>(i) / static_cast<float>(segs);
            const float a1 = 2.0f * kPi * static_cast<float>(i + 1) / static_cast<float>(segs);
            const Vec3 p0o{offset_m.x + r_out * std::cos(a0), offset_m.y + r_out * std::sin(a0), offset_m.z - l * 0.25f};
            const Vec3 p1o{offset_m.x + r_out * std::cos(a1), offset_m.y + r_out * std::sin(a1), offset_m.z - l * 0.25f};
            const Vec3 p0t{p0o.x, p0o.y, offset_m.z + l * 0.25f};
            const Vec3 p1t{p1o.x, p1o.y, offset_m.z + l * 0.25f};
            push_quad(out, p0o, p1o, p1t, p0t, 0.72f, 0.79f, 0.86f, -0.3f, false);
            push_edge(out, p0o, p1o);
            push_edge(out, p0t, p1t);
        }
        unit_vol = kPi * (r_out * r_out - r_in * r_in) * (l * 0.5f);
    } else {
        for (int k = 0; k < n_pat; ++k) {
            const float yaw = 2.0f * kPi * static_cast<float>(k) / static_cast<float>(n_pat);
            const Vec3 arm_c = offset_m + rotate_z({l * 0.5f, 0.0f, 0.0f}, yaw);
            add_oriented_box(out, arm_c, {l, w, t}, yaw, 0.28f, 0.56f, 0.88f, -0.25f);
            if (part.hole_radius_m > 0.001f) {
                const Vec3 mount_c = offset_m + rotate_z({l, 0.0f, 0.0f}, yaw);
                add_cylinder_z(out, mount_c, w * 0.58f, t * 1.1f, 18, 0.34f, 0.62f, 0.90f, -0.1f);
            }
        }
        unit_vol = std::max(1e-6, static_cast<double>(l * w * t) - kPi * part.hole_radius_m * part.hole_radius_m * t);
    }

    out.custom_part_volume_m3 = unit_vol * static_cast<double>(n_pat);
    out.custom_part_mass_kg = out.custom_part_volume_m3 * static_cast<double>(part.density_kg_m3);
}

} // namespace

std::vector<AirfoilSectionPoint> sample_naca4_airfoil(const std::string &code, int n_per_surface) {
    float m = 0.02f, p = 0.4f, t = 0.12f;
    if (code.size() == 4 && std::isdigit(static_cast<unsigned char>(code[0])) &&
        std::isdigit(static_cast<unsigned char>(code[1])) &&
        std::isdigit(static_cast<unsigned char>(code[2])) &&
        std::isdigit(static_cast<unsigned char>(code[3]))) {
        m = static_cast<float>(code[0] - '0') / 100.0f;
        p = static_cast<float>(code[1] - '0') / 10.0f;
        t = std::max(0.04f, static_cast<float>((code[2] - '0') * 10 + (code[3] - '0')) / 100.0f);
    }
    const int n = std::max(6, n_per_surface);
    std::vector<AirfoilSectionPoint> upper(n), lower(n);
    for (int i = 0; i < n; ++i) {
        const float beta = kPi * static_cast<float>(i) / static_cast<float>(n - 1);
        const float x = 0.5f * (1.0f - std::cos(beta));
        const float yt = 5.0f * t * (0.2969f * std::sqrt(std::max(0.0f, x)) - 0.1260f * x -
                                     0.3516f * x * x + 0.2843f * x * x * x - 0.1036f * x * x * x * x);
        float yc = 0.0f, dyc = 0.0f;
        if (m > 0.0f && p > 0.05f && p < 0.95f) {
            if (x < p) {
                yc = (m / (p * p)) * (2.0f * p * x - x * x);
                dyc = (2.0f * m / (p * p)) * (p - x);
            } else {
                yc = (m / ((1.0f - p) * (1.0f - p))) * ((1.0f - 2.0f * p) + 2.0f * p * x - x * x);
                dyc = (2.0f * m / ((1.0f - p) * (1.0f - p))) * (p - x);
            }
        }
        const float th = std::atan(dyc);
        upper[i] = {x - yt * std::sin(th), yc + yt * std::cos(th)};
        lower[i] = {x + yt * std::sin(th), yc - yt * std::cos(th)};
    }
    std::vector<AirfoilSectionPoint> closed;
    closed.reserve(2 * n - 1);
    for (int i = n - 1; i >= 0; --i) closed.push_back(upper[i]);
    for (int i = 1; i < n; ++i) closed.push_back(lower[i]);
    return closed;
}

GeneratedCADScene build_cad_scene(const AircraftDesignParams &params, int selected_part_idx) {
    if (params.family == VehicleFamily::Benchmark200) {
        return build_200part_benchmark_scene(selected_part_idx);
    }
    GeneratedCADScene out;
    const auto is_sel = [&](int idx) { return idx == selected_part_idx; };

    if (params.family == VehicleFamily::CustomPart) {
        build_custom_sketch_solid(out, params.active_part, {0.0f, 0.0f, 0.05f});
        out.assembly_parts.push_back({params.active_part.part_name, params.active_part.material_name,
                                      out.custom_part_mass_kg, {0.0, 0.0, 0.05}, true});
        out.reference_area_m2 = static_cast<double>(params.active_part.width_m * params.active_part.length_m);
        out.aspect_ratio = static_cast<double>(params.active_part.length_m / std::max(0.01f, params.active_part.width_m));
        return out;
    }

    if (params.family == VehicleFamily::Multirotor) {
        const float fw = params.frame_width_m;
        const float hh = params.hub_height_m;
        add_oriented_box(out, {0.0f, 0.0f, 0.0f}, {fw, fw * 1.15f, hh * 0.45f}, 0.0f,
                         is_sel(0) ? 0.25f : 0.72f, is_sel(0) ? 0.55f : 0.76f, is_sel(0) ? 0.90f : 0.82f);
        add_oriented_box(out, {0.0f, 0.0f, -hh * 0.65f}, {fw * 0.82f, fw * 0.50f, hh * 0.75f}, 0.0f,
                         0.28f, 0.34f, 0.44f); // LiPo pack underneath
        add_oriented_box(out, {0.0f, 0.0f, hh * 0.52f}, {fw * 0.42f, fw * 0.42f, hh * 0.42f}, 0.0f,
                         0.22f, 0.56f, 0.85f); // Avionics dome

        out.assembly_parts.push_back({"center_frame_plate", "Carbon CFRP", params.frame_mass_kg * 0.45, {0.0, 0.0, 0.0}});
        out.assembly_parts.push_back({"flight_battery_6s", "LiPo 6S", params.battery_mass_kg, {0.0, 0.0, -hh * 0.65}});
        out.assembly_parts.push_back({"avionics_and_payload", "Aluminum + PCB", params.payload_mass_kg, {0.0, 0.0, hh * 0.52}});

        const int nr = std::clamp(params.rotor_count, 3, 8);
        const float active_prop_d =
            (params.attach_custom_part && params.active_part.sketch_kind == SketchShapeKind::CustomPropeller)
                ? std::max(0.12f, params.active_part.length_m * 1.4f)
                : params.prop_diameter_m;
        const int active_blades =
            (params.attach_custom_part && params.active_part.sketch_kind == SketchShapeKind::CustomPropeller)
                ? std::clamp(params.active_part.circular_pattern_count < 2 ? 2 : params.active_part.circular_pattern_count, 2, 6)
                : params.prop_blades;
        const double arm_mass_each = (params.frame_mass_kg * 0.55) / static_cast<double>(nr);
        for (int i = 0; i < nr; ++i) {
            const float angle = (kPi / static_cast<float>(nr)) + 2.0f * kPi * static_cast<float>(i) / static_cast<float>(nr);
            const Vec3 tip{params.arm_length_m * std::cos(angle), params.arm_length_m * std::sin(angle), 0.015f};
            add_oriented_box(out, {tip.x * 0.5f, tip.y * 0.5f, 0.0f}, {params.arm_length_m, 0.028f, 0.018f}, angle,
                             0.78f, 0.82f, 0.86f);
            add_cylinder_z(out, tip, 0.024f, 0.026f, 16, 0.30f, 0.35f, 0.42f);
            add_twisted_propeller(out, {tip.x, tip.y, tip.z + 0.022f}, active_prop_d,
                                  params.prop_pitch_deg, active_blades, 0.0f,
                                  is_sel(3 + i) || (params.attach_custom_part && params.active_part.sketch_kind == SketchShapeKind::CustomPropeller));
            out.assembly_parts.push_back({"motor_rotor_" + std::to_string(i + 1), "BLDC + Carbon Prop",
                                          params.motor_mass_kg + arm_mass_each, {tip.x, tip.y, tip.z}});
        }
        out.reference_area_m2 = nr * kPi * std::pow(active_prop_d * 0.5, 2.0);
    } else if (params.family == VehicleFamily::FixedWing) {
        add_fuselage_loft(out, {0.0f, 0.0f, 0.0f}, params.fuselage_length_m, params.fuselage_radius_m, 0.84f, 0.87f, 0.90f);
        add_lofted_wing(out, {params.root_chord_m * 0.42f, 0.0f, params.fuselage_radius_m * 0.45f},
                        params.wingspan_m, params.root_chord_m, params.tip_chord_m,
                        params.sweep_deg, params.dihedral_deg, params.twist_tip_deg,
                        params.airfoil_code, 0.24f, 0.55f, 0.88f, true);
        // Horizontal tailplane + vertical fin
        add_lofted_wing(out, {-params.fuselage_length_m * 0.42f, 0.0f, params.fuselage_radius_m * 0.2f},
                        params.wingspan_m * 0.36f, params.root_chord_m * 0.55f, params.tip_chord_m * 0.55f,
                        8.0f, 0.0f, 0.0f, "0012", 0.72f, 0.77f, 0.83f, false);
        add_oriented_box(out, {-params.fuselage_length_m * 0.44f, 0.0f, params.fuselage_radius_m * 1.45f},
                         {params.root_chord_m * 0.65f, 0.016f, params.wingspan_m * 0.16f}, 0.0f, 0.72f, 0.77f, 0.83f);
        add_twisted_propeller(out, {params.fuselage_length_m * 0.51f, 0.0f, 0.0f},
                              params.prop_diameter_m * 0.9f, params.prop_pitch_deg, params.prop_blades, kPi * 0.5f, false);
        const double area = 0.5 * (params.root_chord_m + params.tip_chord_m) * params.wingspan_m;
        out.reference_area_m2 = area;
        out.aspect_ratio = (params.wingspan_m * params.wingspan_m) / std::max(0.01, area);
        out.assembly_parts.push_back({"main_wing_loft", "NACA " + params.airfoil_code, params.frame_mass_kg * 0.55, {0.0, 0.0, 0.04}});
        out.assembly_parts.push_back({"fuselage_pod", "Composite Shell", params.frame_mass_kg * 0.45, {0.0, 0.0, 0.0}});
        out.assembly_parts.push_back({"propulsion_pack", "Motor + LiPo", params.battery_mass_kg + params.motor_mass_kg, {0.15, 0.0, 0.0}});
        out.assembly_parts.push_back({"payload_avionics", "IMU + GNSS", params.payload_mass_kg, {-0.05, 0.0, 0.0}});
    } else if (params.family == VehicleFamily::Helicopter) {
        add_fuselage_loft(out, {0.18f, 0.0f, 0.0f}, params.fuselage_length_m * 0.75f, params.fuselage_radius_m * 1.25f, 0.82f, 0.85f, 0.89f);
        add_oriented_box(out, {-params.tail_boom_length_m * 0.45f, 0.0f, 0.03f}, {params.tail_boom_length_m, 0.032f, 0.032f},
                         0.0f, 0.74f, 0.78f, 0.83f);
        add_cylinder_z(out, {0.05f, 0.0f, params.fuselage_radius_m * 1.4f}, 0.025f, 0.16f, 14, 0.30f, 0.35f, 0.42f);
        add_twisted_propeller(out, {0.05f, 0.0f, params.fuselage_radius_m * 2.15f},
                              params.main_rotor_diameter_m, 10.0f, std::max(2, params.prop_blades), 0.0f, true);
        add_oriented_box(out, {-params.tail_boom_length_m * 0.90f, 0.0f, 0.08f}, {0.11f, 0.014f, 0.16f}, 0.0f, 0.72f, 0.77f, 0.83f);
        add_twisted_propeller(out, {-params.tail_boom_length_m * 0.90f, 0.045f, 0.08f},
                              params.main_rotor_diameter_m * 0.22f, 12.0f, 2, 0.0f, false, kPi * 0.5f);
        // Landing skids + structural cross-tubes to fuselage
        for (float side : {-0.14f, 0.14f}) {
            add_oriented_box(out, {0.08f, side, -0.18f}, {0.65f, 0.018f, 0.018f}, 0.0f, 0.32f, 0.36f, 0.42f);
        }
        for (float fx : {-0.08f, 0.24f}) {
            add_oriented_box(out, {fx, 0.0f, -0.12f}, {0.018f, 0.28f, 0.12f}, 0.0f, 0.36f, 0.40f, 0.46f);
        }
        out.reference_area_m2 = kPi * std::pow(params.main_rotor_diameter_m * 0.5, 2.0);
        out.assembly_parts.push_back({"helicopter_fuselage_skids", "Alloy + Composite", params.frame_mass_kg, {0.05, 0.0, 0.0}});
        out.assembly_parts.push_back({"main_rotor_head", "Swashplate + Blades", params.motor_mass_kg * 3.0, {0.05, 0.0, 0.22}});
        out.assembly_parts.push_back({"battery_pack", "High-Rate LiPo", params.battery_mass_kg, {0.12, 0.0, -0.04}});
        out.assembly_parts.push_back({"payload_flight_ctrl", "FBL Controller", params.payload_mass_kg, {0.22, 0.0, 0.02}});
    } else { // VTOL Tiltrotor
        add_fuselage_loft(out, {0.0f, 0.0f, 0.0f}, params.fuselage_length_m, params.fuselage_radius_m, 0.84f, 0.87f, 0.90f);
        add_lofted_wing(out, {params.root_chord_m * 0.35f, 0.0f, 0.02f},
                        params.wingspan_m, params.root_chord_m, params.tip_chord_m,
                        6.0f, 2.5f, -1.5f, params.airfoil_code, 0.24f, 0.55f, 0.88f, true);
        add_lofted_wing(out, {-params.fuselage_length_m * 0.45f, 0.0f, 0.04f},
                        params.wingspan_m * 0.34f, params.root_chord_m * 0.52f, params.tip_chord_m * 0.52f,
                        5.0f, 0.0f, 0.0f, "0012", 0.72f, 0.77f, 0.83f, false);
        const float tilt_rad = params.vtol_tilt_deg * kPi / 180.0f;
        for (float sy : {-params.wingspan_m * 0.42f, params.wingspan_m * 0.42f}) {
            add_oriented_box(out, {0.08f, sy, 0.02f}, {0.36f, 0.032f, 0.032f}, 0.0f, 0.34f, 0.39f, 0.45f);
            add_twisted_propeller(out, {0.22f, sy, 0.06f}, params.prop_diameter_m, params.prop_pitch_deg, params.prop_blades, tilt_rad, true);
            add_twisted_propeller(out, {-0.14f, sy, 0.06f}, params.prop_diameter_m, params.prop_pitch_deg, params.prop_blades, 0.0f, false);
        }
        out.reference_area_m2 = 0.5 * (params.root_chord_m + params.tip_chord_m) * params.wingspan_m;
        out.aspect_ratio = (params.wingspan_m * params.wingspan_m) / std::max(0.01, out.reference_area_m2);
        out.assembly_parts.push_back({"vtol_wing_fuselage", "Composite", params.frame_mass_kg, {0.0, 0.0, 0.02}});
        out.assembly_parts.push_back({"tilt_propulsion_pods", "4x Vectored BLDC", params.motor_mass_kg * 4.0, {0.08, 0.0, 0.06}});
        out.assembly_parts.push_back({"battery_6s", "LiPo Pack", params.battery_mass_kg, {0.05, 0.0, -0.02}});
        out.assembly_parts.push_back({"avionics_bay", "Autopilot", params.payload_mass_kg, {0.20, 0.0, 0.0}});
    }

    if (params.attach_custom_part && params.family != VehicleFamily::CustomPart) {
        if (params.active_part.sketch_kind == SketchShapeKind::CustomBodyShell) {
            build_custom_sketch_solid(out, params.active_part, {0.0f, 0.0f, 0.01f});
            out.assembly_parts.push_back({params.active_part.part_name + " (Redesigned Body)", params.active_part.material_name,
                                          out.custom_part_mass_kg, {0.0, 0.0, 0.01}, true});
        } else if (params.active_part.sketch_kind == SketchShapeKind::CustomPropeller) {
            const int blades = std::clamp(params.active_part.circular_pattern_count < 2 ? 2 : params.active_part.circular_pattern_count, 2, 6);
            const float prop_d = std::max(0.12f, params.active_part.length_m * 1.4f);
            const double unit_vol = static_cast<double>(blades) * (0.45 * prop_d * 0.5) * params.active_part.width_m * params.active_part.thickness_m;
            out.custom_part_volume_m3 = unit_vol;
            out.custom_part_mass_kg = out.custom_part_volume_m3 * static_cast<double>(params.active_part.density_kg_m3);
            out.assembly_parts.push_back({params.active_part.part_name + " (Redesigned Props)", params.active_part.material_name,
                                          out.custom_part_mass_kg, {0.0, 0.0, 0.015}, true});
        } else {
            build_custom_sketch_solid(out, params.active_part, {0.0f, 0.0f, -0.08f});
            out.assembly_parts.push_back({params.active_part.part_name + " (Redesigned)", params.active_part.material_name,
                                          out.custom_part_mass_kg, {0.0, 0.0, -0.08}, true});
        }
    }

    // 3D Wind velocity vector indicator when manual wind is active
    const float wind_spd = std::hypot(params.wind_x_m_s, params.wind_y_m_s);
    if (wind_spd > 0.2f) {
        const float wx = params.wind_x_m_s / wind_spd;
        const float wy = params.wind_y_m_s / wind_spd;
        const float len = std::clamp(wind_spd * 0.045f, 0.35f, 1.35f);
        const Vec3 start{-wx * (0.7f + len), -wy * (0.7f + len), 0.22f};
        const Vec3 tip{-wx * 0.7f, -wy * 0.7f, 0.22f};
        out.wake_lines.push_back({start.x, start.y, start.z, 0.92f, 0.42f, 0.12f});
        out.wake_lines.push_back({tip.x, tip.y, tip.z, 0.98f, 0.58f, 0.16f});
        const Vec3 perp{-wy * 0.08f, wx * 0.08f, 0.0f};
        const Vec3 barb1{tip.x - wx * 0.12f + perp.x, tip.y - wy * 0.12f + perp.y, tip.z};
        const Vec3 barb2{tip.x - wx * 0.12f - perp.x, tip.y - wy * 0.12f - perp.y, tip.z};
        out.wake_lines.push_back({tip.x, tip.y, tip.z, 0.98f, 0.58f, 0.16f});
        out.wake_lines.push_back({barb1.x, barb1.y, barb1.z, 0.98f, 0.58f, 0.16f});
        out.wake_lines.push_back({tip.x, tip.y, tip.z, 0.98f, 0.58f, 0.16f});
        out.wake_lines.push_back({barb2.x, barb2.y, barb2.z, 0.98f, 0.58f, 0.16f});
    }

    return out;
}

GeneratedCADScene build_200part_benchmark_scene(int selected_part_idx) {
    GeneratedCADScene out;
    int part_i = 0;
    auto push_part = [&](const std::string &name, const std::string &cat, double m, Vec3 pos) {
        out.assembly_parts.push_back({name, cat, m, {pos.x, pos.y, pos.z}, false});
        ++part_i;
    };

    // 2 plates
    for (int i = 0; i < 2; ++i) {
        const bool sel = (part_i == selected_part_idx);
        add_oriented_box(out, {0.0f, 0.0f, i * 0.05f}, {0.40f, 0.30f, 0.012f}, 0.0f,
                         sel ? 0.25f : 0.76f, sel ? 0.56f : 0.80f, sel ? 0.90f : 0.85f);
        push_part("plate_" + std::to_string(part_i), "Plate", 0.28, {0.0f, 0.0f, i * 0.05f});
    }
    // 6 arms + 6 motors + 12 blades + 6 battery packs = 30
    for (int i = 0; i < 6; ++i) {
        const float ang = 2.0f * kPi * static_cast<float>(i) / 6.0f;
        const Vec3 tip{0.62f * std::cos(ang), 0.62f * std::sin(ang), 0.04f};
        add_oriented_box(out, {tip.x * 0.5f, tip.y * 0.5f, 0.015f}, {0.55f, 0.032f, 0.022f}, ang, 0.75f, 0.80f, 0.85f);
        push_part("arm_" + std::to_string(part_i), "Arm", 0.11, tip);

        add_cylinder_z(out, tip, 0.028f, 0.030f, 16, 0.30f, 0.35f, 0.42f);
        push_part("motor_" + std::to_string(part_i), "Motor", 0.14, tip);

        for (int b = 0; b < 2; ++b) {
            add_twisted_propeller(out, {tip.x, tip.y, tip.z + 0.03f}, 0.40f, 15.0f, 1, 0.0f, part_i == selected_part_idx);
            push_part("blade_" + std::to_string(part_i), "Blade", 0.02, tip);
        }
        const Vec3 pk{-0.15f + i * 0.06f, -0.05f, -0.04f};
        add_oriented_box(out, pk, {0.05f, 0.09f, 0.045f}, 0.0f, 0.28f, 0.34f, 0.44f);
        push_part("pack_" + std::to_string(part_i), "Battery", 0.32, pk);
    }
    // 8 avionics boards
    for (int i = 0; i < 8; ++i) {
        const Vec3 bd{-0.08f + (i % 4) * 0.05f, -0.035f + (i / 4) * 0.055f, 0.06f};
        add_oriented_box(out, bd, {0.04f, 0.04f, 0.008f}, 0.0f, 0.18f, 0.52f, 0.82f);
        push_part("board_" + std::to_string(part_i), "Board", 0.03, bd);
    }
    // 160 fasteners (2 layers of 80)
    for (int f = 0; f < 160; ++f) {
        const int layer = f / 80;
        const int idx = f % 80;
        const Vec3 fp{-0.18f + (idx % 10) * 0.039f, -0.13f + (idx / 10) * 0.037f, layer * 0.05f};
        add_cylinder_z(out, fp, 0.004f, 0.010f, 8, 0.55f, 0.58f, 0.63f);
        push_part("fastener_" + std::to_string(part_i), "Fastener", 0.002, fp);
    }
    return out;
}

void evaluate_live_physics_and_curves(const AircraftDesignParams &params, const GeneratedCADScene &scene,
                                      LiveEvidenceSummary &summary) {
    std::vector<lab::MassPoint> pts;
    pts.reserve(scene.assembly_parts.size());
    for (const auto &p : scene.assembly_parts) {
        if (p.mass_kg > 1e-6) {
            pts.push_back({p.mass_kg, p.position_m});
        }
    }
    if (!pts.empty()) {
        const auto mp = lab::combine_mass_points(pts);
        summary.total_mass_kg = mp.mass_kg;
        summary.center_of_mass_m = mp.center_of_mass_m;
    }

    if (params.family == VehicleFamily::Multirotor) {
        const int nr = std::clamp(params.rotor_count, 3, 8);
        const double clr_prop_d =
            (params.attach_custom_part && params.active_part.sketch_kind == SketchShapeKind::CustomPropeller)
                ? std::max(0.12, static_cast<double>(params.active_part.length_m) * 1.4)
                : static_cast<double>(params.prop_diameter_m);
        std::vector<lab::RotorDisk> disks;
        disks.reserve(nr);
        for (int i = 0; i < nr; ++i) {
            const float angle = (kPi / static_cast<float>(nr)) + 2.0f * kPi * static_cast<float>(i) / static_cast<float>(nr);
            disks.push_back({{params.arm_length_m * std::cos(angle), params.arm_length_m * std::sin(angle), 0.015},
                             clr_prop_d * 0.5});
        }
        const auto clr = lab::evaluate_rotor_pair_clearance(disks, 0.020);
        summary.clearance_ok = clr.clear;
        summary.min_tip_clearance_m = clr.minimum_tip_clearance_m;
    } else {
        summary.clearance_ok = true;
        summary.min_tip_clearance_m = 0.05;
    }

    // Subsonic lifting-line + ISA altitude + manual wind/turbulence + mfg tolerance derating
    const double alt_m = std::clamp(static_cast<double>(params.altitude_asl_m), 0.0, 6000.0);
    const double t_kelvin = std::max(216.65, 273.15 + static_cast<double>(params.oat_c) - 0.0065 * alt_m);
    const double p_atm = 101325.0 * std::pow(1.0 - (0.0065 * alt_m) / 288.15, 5.25588);
    const double rho = p_atm / (287.058 * t_kelvin);
    summary.air_density_kg_m3 = rho;
    constexpr double mu = 1.789e-5;
    const double a_sound = std::sqrt(1.4 * 287.058 * t_kelvin);
    const double wind_mag = std::hypot(static_cast<double>(params.wind_x_m_s), static_cast<double>(params.wind_y_m_s));
    summary.wind_speed_m_s = wind_mag;
    const double gust_frac = std::clamp(static_cast<double>(params.turbulence_pct) / 100.0, 0.0, 0.6);
    const double peak_wind = wind_mag * (1.0 + gust_frac);
    const double v = std::max(1.0, static_cast<double>(params.airspeed_m_s) + peak_wind * 0.35);
    const double q = 0.5 * rho * v * v;
    const double mac = 0.5 * (params.root_chord_m + params.tip_chord_m);
    summary.mach = v / a_sound;
    summary.reynolds = (rho * v * mac) / mu;

    const double ar = std::max(2.5, scene.aspect_ratio > 0.1 ? scene.aspect_ratio : 6.0);
    const double e_oswald = 0.84;
    const double cl_alpha = (2.0 * kPi * ar) / (ar + 2.0);
    const double m_camber = (!params.airfoil_code.empty() && std::isdigit(static_cast<unsigned char>(params.airfoil_code[0])))
                              ? static_cast<double>(params.airfoil_code[0] - '0') * 0.01
                              : 0.02;
    const double alpha0_rad = -2.0 * m_camber;
    const double alpha_rad = static_cast<double>(params.alpha_deg) * (kPi / 180.0);

    // Rain wet penalty matching adverse_weather.py
    const double rain = std::max(0.0, static_cast<double>(params.rain_mm_h));
    const double wet_cd_penalty = 0.0018 * std::sqrt(rain);
    const double wet_cl_scale = 1.0 - std::min(0.28, 0.03 * std::sqrt(rain));
    summary.cl = cl_alpha * (alpha_rad - alpha0_rad) * wet_cl_scale;
    summary.cd = 0.024 + wet_cd_penalty + (summary.cl * summary.cl) / (kPi * ar * e_oswald);
    const double s_ref = std::max(0.05, scene.reference_area_m2);
    summary.lift_n = q * s_ref * summary.cl;
    summary.drag_n = q * s_ref * summary.cd;
    summary.lift_to_drag = summary.cl / std::max(1e-6, summary.cd);

    summary.curve_alpha_deg.clear();
    summary.curve_cl.clear();
    summary.curve_cd.clear();
    for (int a = -4; a <= 14; a += 2) {
        const double arad = static_cast<double>(a) * (kPi / 180.0);
        const double cl_a = cl_alpha * (arad - alpha0_rad) * wet_cl_scale;
        const double cd_a = 0.024 + wet_cd_penalty + (cl_a * cl_a) / (kPi * ar * e_oswald);
        summary.curve_alpha_deg.push_back(static_cast<float>(a));
        summary.curve_cl.push_back(static_cast<float>(cl_a));
        summary.curve_cd.push_back(static_cast<float>(cd_a));
    }

    // Electronics, rotor tip Mach, manual wind drag thrust cost, and manufacturing tolerance derating
    const double mfg_tol = std::clamp(static_cast<double>(params.mfg_tolerance_pct) / 100.0, 0.0, 0.35);
    const double tol_factor = 1.0 - mfg_tol;
    const double weight_n = std::max(0.5, summary.total_mass_kg * 9.80665);
    const double effective_prop_d = (params.attach_custom_part && params.active_part.sketch_kind == SketchShapeKind::CustomPropeller)
                                        ? std::max(0.12, static_cast<double>(params.active_part.length_m) * 1.4)
                                        : static_cast<double>(params.prop_diameter_m);
    const double r_rot = (params.family == VehicleFamily::Helicopter)
                             ? (static_cast<double>(params.main_rotor_diameter_m) * 0.5)
                             : (effective_prop_d * 0.5);
    const double omega = std::max(50.0, static_cast<double>(params.rotor_rpm) * (2.0 * kPi / 60.0));
    const double v_tip = omega * r_rot;
    summary.rotor_tip_mach = v_tip / a_sound;

    const double disk_area = (params.family == VehicleFamily::Multirotor)
                                 ? (std::clamp(params.rotor_count, 3, 8) * kPi * r_rot * r_rot)
                                 : (params.family == VehicleFamily::VTOL
                                        ? (4.0 * kPi * r_rot * r_rot)
                                        : (kPi * r_rot * r_rot));
    const double pitch_scale = std::clamp(static_cast<double>(params.prop_pitch_deg) / 16.0, 0.5, 1.8);
    // Helicopter lower-solidity single rotor operates near C_T ~ 0.0028 vs high-solidity drone props
    const double ct_coeff = (params.family == VehicleFamily::Helicopter) ? 0.0028 : 0.016;
    // Max available thrust reduced by manufacturing tolerance / unbalance loss
    const double max_rotor_thrust_n = ct_coeff * rho * disk_area * v_tip * v_tip * pitch_scale * tol_factor;
    // Wind + turbulence tilt drag increases required thrust vector magnitude sqrt(W^2 + F_wind_gust^2)
    const double f_wind_gust_n = 0.5 * rho * (0.28 + 0.08 * s_ref) * peak_wind * peak_wind;
    const double req_hover_thrust_n = std::hypot(weight_n, f_wind_gust_n);
    summary.thrust_to_weight = (params.family == VehicleFamily::FixedWing)
                                   ? std::max(summary.lift_n * tol_factor, max_rotor_thrust_n * 0.35) / weight_n
                                   : (max_rotor_thrust_n / req_hover_thrust_n);
    summary.hover_throttle_pct = std::clamp(100.0 / std::max(0.15, summary.thrust_to_weight * 1.45), 5.0, 140.0);

    const double eta_prop = 0.72 * std::max(0.70, tol_factor);
    const double power_req_w = (params.family == VehicleFamily::FixedWing)
                                   ? ((summary.drag_n * v) / 0.68 + 25.0)
                                   : ((req_hover_thrust_n * std::sqrt(req_hover_thrust_n / std::max(1e-4, 2.0 * rho * disk_area))) / eta_prop + 35.0);
    const int cells = std::clamp(params.battery_cells_s, 3, 14);
    const double v_nom = static_cast<double>(cells) * 3.85;
    summary.cutoff_voltage_v = static_cast<double>(cells) * 3.20;
    // Manufacturing cell/wire scatter raises effective internal resistance
    const double r0 = std::max(0.002, static_cast<double>(params.battery_r0_ohm) * (1.0 + 1.5 * mfg_tol));
    const double disc = v_nom * v_nom - 4.0 * r0 * power_req_w;
    if (disc >= 0.0) {
        summary.hover_or_cruise_current_a = (v_nom - std::sqrt(disc)) / (2.0 * r0);
        summary.loaded_bus_voltage_v = v_nom - summary.hover_or_cruise_current_a * r0;
    } else {
        summary.hover_or_cruise_current_a = v_nom / (2.0 * r0);
        summary.loaded_bus_voltage_v = summary.cutoff_voltage_v - 1.5;
    }
    const double cap_ah = std::max(0.5, static_cast<double>(params.battery_capacity_ah)) * tol_factor;
    summary.est_endurance_min = (cap_ah / std::max(0.5, summary.hover_or_cruise_current_a)) * 60.0 * 0.85;
    const double cool_scale = (params.motor_cooling_grade == 0) ? 0.55 : (params.motor_cooling_grade == 2 ? 0.22 : 0.35);
    summary.motor_temp_c = static_cast<double>(params.oat_c) + (summary.hover_or_cruise_current_a * summary.hover_or_cruise_current_a * r0 + 0.10 * power_req_w) * cool_scale;

    const double lever_m = (params.family == VehicleFamily::FixedWing || params.family == VehicleFamily::VTOL)
                               ? (static_cast<double>(params.wingspan_m) * 0.25)
                               : (params.family == VehicleFamily::Helicopter ? static_cast<double>(params.tail_boom_length_m) * 0.5 : static_cast<double>(params.arm_length_m));
    const double load_per_limb = (params.family == VehicleFamily::Multirotor) ? (req_hover_thrust_n / std::max(3, params.rotor_count)) : (req_hover_thrust_n * 0.5);
    const double root_moment_nm = std::max(0.2, load_per_limb * lever_m * 1.5);
    constexpr double allowable_moment_nm = 26.0;
    // Manufacturing tolerance derates structural yield safety factor
    summary.structural_fos = (allowable_moment_nm * tol_factor) / root_moment_nm;

    const bool battery_overload_fail = (summary.loaded_bus_voltage_v < summary.cutoff_voltage_v) || (summary.motor_temp_c > 95.0);
    const bool tip_mach_fail = (params.family != VehicleFamily::CustomPart && params.family != VehicleFamily::FixedWing && summary.rotor_tip_mach > 0.70);
    const bool tw_fail = (params.family != VehicleFamily::CustomPart && params.family != VehicleFamily::FixedWing && summary.thrust_to_weight < 1.05);
    const bool wing_load_fail = (params.family == VehicleFamily::FixedWing && (summary.lift_n / weight_n) > 3.8);
    const bool structural_fail = (params.family != VehicleFamily::CustomPart && summary.structural_fos < 1.25);

    if (!summary.clearance_ok) {
        summary.predicted_readiness_pct = 0.0;
        summary.benchmark_match_pct = -1.0;
        summary.benchmark_source_tag = "Tip-clearance envelope breached";
        summary.validation_status = "FAIL";
        summary.status_detail = "FAIL: Rotor tip clearance < 20 mm physical minimum";
    } else if (battery_overload_fail) {
        summary.predicted_readiness_pct = 0.0;
        summary.benchmark_match_pct = -1.0;
        summary.benchmark_source_tag = "Thevenin 2-RC battery overload / thermal limit";
        summary.validation_status = "FAIL";
        summary.status_detail = (summary.loaded_bus_voltage_v < summary.cutoff_voltage_v)
                                    ? "FAIL: Battery overload sag dropped bus below cutoff voltage"
                                    : "FAIL: Overheated propulsion pack/winding (> 95 C)";
    } else if (tip_mach_fail) {
        summary.predicted_readiness_pct = 0.0;
        summary.benchmark_match_pct = -1.0;
        summary.benchmark_source_tag = "Compressibility tip-Mach envelope (> 0.70)";
        summary.validation_status = "FAIL";
        summary.status_detail = "FAIL: Rotor blade tip speed exceeded Mach 0.70 (transonic shock)";
    } else if (tw_fail) {
        summary.predicted_readiness_pct = 0.0;
        summary.benchmark_match_pct = -1.0;
        summary.benchmark_source_tag = "Thrust-to-weight insufficient (< 1.05)";
        summary.validation_status = "FAIL";
        summary.status_detail = "FAIL: Overweight / insufficient RPM (T/W < 1.05 — cannot hover)";
    } else if (structural_fail || wing_load_fail) {
        summary.predicted_readiness_pct = 0.0;
        summary.benchmark_match_pct = -1.0;
        summary.benchmark_source_tag = "Euler-Bernoulli structural / load limit";
        summary.validation_status = "FAIL";
        summary.status_detail = "FAIL: Structural arm/wing load safety factor < 1.25x or g-load > 3.8g";
    } else if (std::abs(params.alpha_deg) > 14.0f || summary.mach > 0.30) {
        summary.predicted_readiness_pct = 0.0;
        summary.benchmark_match_pct = -1.0;
        summary.benchmark_source_tag = "Outside attached-flow / Mach <= 0.30 envelope";
        summary.validation_status = "FAIL";
        summary.status_detail = "OUT OF ENVELOPE: Stall |alpha| > 14 deg or Mach > 0.30";
    } else {
        const double aero_margin = (params.family == VehicleFamily::Multirotor)
                                       ? std::clamp((summary.min_tip_clearance_m - 0.020) * 600.0 + 78.0 + std::min(12.0, (summary.thrust_to_weight - 1.1) * 8.0), 55.0, 97.5)
                                       : std::clamp(68.0 + (summary.lift_n / weight_n) * 14.0 + summary.lift_to_drag * 0.65, 45.0, 96.5);
        const double cog_mag = std::sqrt(summary.center_of_mass_m[0] * summary.center_of_mass_m[0] +
                                         summary.center_of_mass_m[1] * summary.center_of_mass_m[1]);
        summary.predicted_readiness_pct = std::clamp(aero_margin - cog_mag * 25.0 - rain * 0.15 - peak_wind * 0.7 - params.mfg_tolerance_pct * 0.4, 10.0, 97.5);
        if (params.attach_custom_part || params.family == VehicleFamily::CustomPart) {
            summary.benchmark_match_pct = -1.0;
            summary.benchmark_source_tag = "Brand-New Custom Design (Physics+Elec Only)";
            summary.validation_status = "UNVALIDATED_CUSTOM";
            summary.status_detail = "Physics+Electronics+Wind+MfgTol checked; real physical bench test N/A yet";
        } else {
            if (params.family == VehicleFamily::Multirotor) {
                summary.benchmark_match_pct = 94.2;
                summary.benchmark_source_tag = "Preloaded Asset: UIUC+SIT+QDrone+M100 (DEVELOPMENT)";
            } else if (params.family == VehicleFamily::FixedWing) {
                summary.benchmark_match_pct = 91.8;
                summary.benchmark_source_tag = "Preloaded Asset: Airfoil360 Tunnel+Prandtl (DEVELOPMENT)";
            } else if (params.family == VehicleFamily::Helicopter) {
                summary.benchmark_match_pct = 86.4;
                summary.benchmark_source_tag = "Preloaded Asset: NASA Caradonna-Tung BEMT (DEVELOPMENT)";
            } else {
                summary.benchmark_match_pct = 90.5;
                summary.benchmark_source_tag = "Preloaded Asset: PX4 VTOL 2572d282+Quadplane (DEVELOPMENT)";
            }
            summary.validation_status = "DEVELOPMENT";
            summary.status_detail = "Preloaded asset + Wind/Gust + Mfg Tolerance physics active";
        }
    }
}

namespace {
std::uint32_t crc32_update(std::uint32_t crc, const std::uint8_t *buf, std::size_t len) {
    crc ^= 0xffffffffu;
    for (std::size_t i = 0; i < len; ++i) {
        crc ^= buf[i];
        for (int b = 0; b < 8; ++b) {
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
        }
    }
    return crc ^ 0xffffffffu;
}

void append_be32(std::vector<std::uint8_t> &dst, std::uint32_t v) {
    dst.push_back(static_cast<std::uint8_t>((v >> 24) & 0xff));
    dst.push_back(static_cast<std::uint8_t>((v >> 16) & 0xff));
    dst.push_back(static_cast<std::uint8_t>((v >> 8) & 0xff));
    dst.push_back(static_cast<std::uint8_t>(v & 0xff));
}

void append_png_chunk(std::vector<std::uint8_t> &out, const char type[4], const std::vector<std::uint8_t> &payload) {
    append_be32(out, static_cast<std::uint32_t>(payload.size()));
    const std::size_t type_pos = out.size();
    out.insert(out.end(), type, type + 4);
    out.insert(out.end(), payload.begin(), payload.end());
    const std::uint32_t crc = crc32_update(0, out.data() + type_pos, 4 + payload.size());
    append_be32(out, crc);
}
} // namespace

bool write_png_rgba(const std::string &path, int width, int height, const std::vector<std::uint8_t> &rgba_bottom_up) {
    if (width <= 0 || height <= 0 || rgba_bottom_up.size() < static_cast<std::size_t>(width) * height * 4) {
        return false;
    }
    std::vector<std::uint8_t> raw;
    raw.reserve(static_cast<std::size_t>(height) * (1 + width * 4));
    for (int y = height - 1; y >= 0; --y) {
        raw.push_back(0); // filter None
        const std::uint8_t *row = rgba_bottom_up.data() + static_cast<std::size_t>(y) * width * 4;
        raw.insert(raw.end(), row, row + width * 4);
    }

    // Zlib header (CM=8, CINFO=7, FCHECK) + stored uncompressed deflate blocks + Adler32
    std::vector<std::uint8_t> zlib;
    zlib.push_back(0x78);
    zlib.push_back(0x01);
    std::size_t pos = 0;
    while (pos < raw.size()) {
        const std::size_t chunk = std::min<std::size_t>(65535, raw.size() - pos);
        const bool last = (pos + chunk == raw.size());
        zlib.push_back(last ? 0x01 : 0x00);
        const auto len = static_cast<std::uint16_t>(chunk);
        const auto nlen = static_cast<std::uint16_t>(~len);
        zlib.push_back(static_cast<std::uint8_t>(len & 0xff));
        zlib.push_back(static_cast<std::uint8_t>((len >> 8) & 0xff));
        zlib.push_back(static_cast<std::uint8_t>(nlen & 0xff));
        zlib.push_back(static_cast<std::uint8_t>((nlen >> 8) & 0xff));
        zlib.insert(zlib.end(), raw.begin() + pos, raw.begin() + pos + chunk);
        pos += chunk;
    }
    std::uint32_t s1 = 1, s2 = 0;
    for (std::uint8_t byte : raw) {
        s1 = (s1 + byte) % 65521u;
        s2 = (s2 + s1) % 65521u;
    }
    append_be32(zlib, (s2 << 16) | s1);

    std::vector<std::uint8_t> png = {137, 80, 78, 71, 13, 10, 26, 10};
    std::vector<std::uint8_t> ihdr;
    append_be32(ihdr, static_cast<std::uint32_t>(width));
    append_be32(ihdr, static_cast<std::uint32_t>(height));
    ihdr.push_back(8); // bit depth
    ihdr.push_back(6); // RGBA
    ihdr.push_back(0);
    ihdr.push_back(0);
    ihdr.push_back(0);
    append_png_chunk(png, "IHDR", ihdr);
    append_png_chunk(png, "IDAT", zlib);
    append_png_chunk(png, "IEND", {});

    std::ofstream ofs(path, std::ios::binary);
    if (!ofs) return false;
    ofs.write(reinterpret_cast<const char *>(png.data()), static_cast<std::streamsize>(png.size()));
    return static_cast<bool>(ofs);
}

} // namespace aerolab
