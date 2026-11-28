#include "freeform_sketch_cad.hpp"

#include "imgui.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <unordered_map>

namespace aerolab {
namespace {

constexpr float kPiF = 3.14159265358979323846f;

std::array<float, 3> v3_sub(std::array<float, 3> a, std::array<float, 3> b) {
    return {a[0] - b[0], a[1] - b[1], a[2] - b[2]};
}
std::array<float, 3> v3_add(std::array<float, 3> a, std::array<float, 3> b) {
    return {a[0] + b[0], a[1] + b[1], a[2] + b[2]};
}
std::array<float, 3> v3_scale(std::array<float, 3> a, float s) {
    return {a[0] * s, a[1] * s, a[2] * s};
}
float v3_dot(std::array<float, 3> a, std::array<float, 3> b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
std::array<float, 3> v3_cross(std::array<float, 3> a, std::array<float, 3> b) {
    return {a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]};
}
std::array<float, 3> v3_norm(std::array<float, 3> v) {
    const float l = std::sqrt(v3_dot(v, v));
    return l > 1e-7f ? std::array<float, 3>{v[0] / l, v[1] / l, v[2] / l} : std::array<float, 3>{0.0f, 0.0f, 1.0f};
}

WorkplaneSpec make_workplane_from_normal(int face_id, std::array<float, 3> origin, std::array<float, 3> normal) {
    WorkplaneSpec wp;
    wp.preset = (face_id >= 0) ? "FACE" : "XY";
    wp.picked_face_id = face_id;
    wp.origin_m = origin;
    wp.normal = v3_norm(normal);
    const std::array<float, 3> ref = (std::abs(wp.normal[2]) < 0.9f) ? std::array<float, 3>{0, 0, 1} : std::array<float, 3>{1, 0, 0};
    wp.u_axis = v3_norm(v3_cross(ref, wp.normal));
    wp.v_axis = v3_norm(v3_cross(wp.normal, wp.u_axis));
    return wp;
}

bool solve_linear_system(std::vector<double> A, std::vector<double> b, std::vector<double> &x, int n) {
    x.assign(n, 0.0);
    for (int col = 0; col < n; ++col) {
        int piv = col;
        double best = std::abs(A[col * n + col]);
        for (int row = col + 1; row < n; ++row) {
            if (std::abs(A[row * n + col]) > best) {
                best = std::abs(A[row * n + col]);
                piv = row;
            }
        }
        if (best < 1e-12) return false;
        if (piv != col) {
            for (int j = col; j < n; ++j) std::swap(A[col * n + j], A[piv * n + j]);
            std::swap(b[col], b[piv]);
        }
        const double inv = 1.0 / A[col * n + col];
        for (int row = col + 1; row < n; ++row) {
            const double f = A[row * n + col] * inv;
            for (int j = col; j < n; ++j) A[row * n + j] -= f * A[col * n + j];
            b[row] -= f * b[col];
        }
    }
    for (int row = n - 1; row >= 0; --row) {
        double sum = b[row];
        for (int j = row + 1; j < n; ++j) sum -= A[row * n + j] * x[j];
        x[row] = sum / A[row * n + row];
    }
    return true;
}

int matrix_rank(std::vector<double> J, int m, int n) {
    int rank = 0;
    int col = 0;
    for (int row = 0; row < m && col < n; ++col) {
        int piv = row;
        double best = std::abs(J[row * n + col]);
        for (int r = row + 1; r < m; ++r) {
            if (std::abs(J[r * n + col]) > best) {
                best = std::abs(J[r * n + col]);
                piv = r;
            }
        }
        if (best < 1e-5) continue;
        if (piv != row) {
            for (int j = col; j < n; ++j) std::swap(J[row * n + j], J[piv * n + j]);
        }
        const double inv = 1.0 / J[row * n + col];
        for (int r = row + 1; r < m; ++r) {
            const double f = J[r * n + col] * inv;
            for (int j = col; j < n; ++j) J[r * n + j] -= f * J[row * n + j];
        }
        ++rank;
        ++row;
    }
    return rank;
}

const char *constraint_kind_str(FreeformConstraintKind k) {
    switch (k) {
    case FreeformConstraintKind::Horizontal: return "horizontal";
    case FreeformConstraintKind::Vertical: return "vertical";
    case FreeformConstraintKind::Length: return "length";
    case FreeformConstraintKind::Radius: return "radius";
    case FreeformConstraintKind::Fixed: return "fixed";
    case FreeformConstraintKind::Coincident: return "coincident";
    case FreeformConstraintKind::Perpendicular: return "perpendicular";
    case FreeformConstraintKind::Parallel: return "parallel";
    case FreeformConstraintKind::Tangent: return "tangent";
    case FreeformConstraintKind::Equal: return "equal";
    case FreeformConstraintKind::Distance: return "distance";
    }
    return "length";
}

const char *op_kind_str(FreeformOpKind k) {
    switch (k) {
    case FreeformOpKind::ExtrudeBoss: return "extrude_boss";
    case FreeformOpKind::ExtrudeCut: return "extrude_cut";
    case FreeformOpKind::Revolve: return "revolve";
    case FreeformOpKind::Loft: return "loft";
    case FreeformOpKind::Fillet: return "fillet";
    case FreeformOpKind::Chamfer: return "chamfer";
    case FreeformOpKind::Shell: return "shell";
    }
    return "extrude_boss";
}

const char *op_label_str(FreeformOpKind k) {
    switch (k) {
    case FreeformOpKind::ExtrudeBoss: return "Extrude Boss";
    case FreeformOpKind::ExtrudeCut: return "Extrude Cut";
    case FreeformOpKind::Revolve: return "Revolve";
    case FreeformOpKind::Loft: return "Loft";
    case FreeformOpKind::Fillet: return "Fillet";
    case FreeformOpKind::Chamfer: return "Chamfer";
    case FreeformOpKind::Shell: return "Shell";
    }
    return "Feature";
}

std::string make_next_id(const FreeformSketchState &sk, char prefix) {
    int idx = static_cast<int>(sk.entities.size());
    for (;;) {
        std::string cand = std::string(1, prefix) + std::to_string(idx++);
        bool used = false;
        for (const auto &e : sk.entities) {
            if (e.id == cand) { used = true; break; }
        }
        if (!used) return cand;
    }
}

void write_sketch_json(std::ostringstream &oss, const FreeformSketchState &sk, const WorkplaneSpec &wp, int indent = 4) {
    std::string pad(indent, ' ');
    oss << pad << "\"workplane\": {\n"
        << pad << "  \"preset\": \"" << wp.preset << "\",\n"
        << pad << "  \"face_id\": " << wp.picked_face_id << ",\n"
        << pad << "  \"origin_m\": [" << wp.origin_m[0] << ", " << wp.origin_m[1] << ", " << wp.origin_m[2] << "],\n"
        << pad << "  \"normal\": [" << wp.normal[0] << ", " << wp.normal[1] << ", " << wp.normal[2] << "],\n"
        << pad << "  \"u_axis\": [" << wp.u_axis[0] << ", " << wp.u_axis[1] << ", " << wp.u_axis[2] << "]\n"
        << pad << "},\n";
    oss << pad << "\"entities\": [\n";
    for (std::size_t i = 0; i < sk.entities.size(); ++i) {
        const auto &e = sk.entities[i];
        oss << pad << "  {\"id\": \"" << e.id << "\", \"construction\": " << (e.construction ? "true" : "false") << ", ";
        if (e.kind == FreeformEntityKind::Line) {
            oss << "\"kind\": \"line\", \"p0\": [" << e.x0 << ", " << e.y0 << "], \"p1\": [" << e.x1 << ", " << e.y1 << "]";
        } else if (e.kind == FreeformEntityKind::Circle) {
            oss << "\"kind\": \"circle\", \"center\": [" << e.x0 << ", " << e.y0 << "], \"radius\": " << e.radius;
        } else if (e.kind == FreeformEntityKind::Arc) {
            oss << "\"kind\": \"arc\", \"center\": [" << e.x0 << ", " << e.y0 << "], \"radius\": " << e.radius
                << ", \"start_deg\": " << e.start_deg << ", \"end_deg\": " << e.end_deg;
        } else {
            oss << "\"kind\": \"spline\", \"closed\": " << (e.closed ? "true" : "false") << ", \"points\": [";
            for (std::size_t k = 0; k < e.spline_pts.size(); ++k) {
                oss << "[" << e.spline_pts[k][0] << ", " << e.spline_pts[k][1] << "]" << (k + 1 < e.spline_pts.size() ? ", " : "");
            }
            oss << "]";
        }
        oss << "}" << (i + 1 < sk.entities.size() ? "," : "") << "\n";
    }
    oss << pad << "],\n" << pad << "\"constraints\": [\n";
    for (std::size_t i = 0; i < sk.constraints.size(); ++i) {
        const auto &c = sk.constraints[i];
        oss << pad << "  {\"kind\": \"" << constraint_kind_str(c.kind) << "\", \"a\": \"" << c.a << "\"";
        if (!c.b.empty()) oss << ", \"b\": \"" << c.b << "\"";
        oss << ", \"pt_a\": " << c.pt_a << ", \"pt_b\": " << c.pt_b
            << ", \"value\": " << c.value << ", \"target_xy\": [" << c.target_x << ", " << c.target_y << "]}"
            << (i + 1 < sk.constraints.size() ? "," : "") << "\n";
    }
    oss << pad << "]\n";
}

} // namespace

void init_default_freeform_sketch(CustomPartParams &part) {
    if (!part.freeform_sketch.entities.empty() && !part.freeform_features.empty()) return;
    part.sketch_kind = SketchShapeKind::FreeformBrep;
    part.freeform_mode = true;
    part.active_workplane = make_workplane_from_normal(-1, {0.0f, 0.0f, 0.0f}, {0.0f, 0.0f, 1.0f});
    part.active_workplane.preset = "XY";

    FreeformSketchState sk;
    sk.workplane = part.active_workplane;
    sk.entities = {
        {"l0", FreeformEntityKind::Line, false, true, -0.05f, -0.04f, 0.05f, -0.04f},
        {"l1", FreeformEntityKind::Line, false, true,  0.05f, -0.04f, 0.05f,  0.04f},
        {"l2", FreeformEntityKind::Line, false, true,  0.05f,  0.04f, -0.05f, 0.04f},
        {"l3", FreeformEntityKind::Line, false, true, -0.05f,  0.04f, -0.05f, -0.04f},
    };
    sk.constraints = {
        {FreeformConstraintKind::Fixed, "l0", "", 0, 0, 0.0f, -0.05f, -0.04f},
        {FreeformConstraintKind::Coincident, "l0", "l1", 1, 0, 0.0f},
        {FreeformConstraintKind::Coincident, "l1", "l2", 1, 0, 0.0f},
        {FreeformConstraintKind::Coincident, "l2", "l3", 1, 0, 0.0f},
        {FreeformConstraintKind::Coincident, "l3", "l0", 1, 0, 0.0f},
        {FreeformConstraintKind::Horizontal, "l0", "", 0, 0, 0.0f},
        {FreeformConstraintKind::Perpendicular, "l0", "l1", 0, 0, 0.0f},
        {FreeformConstraintKind::Parallel, "l0", "l2", 0, 0, 0.0f},
        {FreeformConstraintKind::Perpendicular, "l2", "l3", 0, 0, 0.0f},
        {FreeformConstraintKind::Length, "l0", "", 0, 0, 0.100f},
        {FreeformConstraintKind::Length, "l1", "", 0, 0, 0.080f},
    };
    solve_sketch_constraints_cpp(sk);
    part.freeform_sketch = sk;

    if (part.freeform_features.empty()) {
        FreeformCadFeature f0;
        f0.op = FreeformOpKind::ExtrudeBoss;
        f0.depth_m = 0.036f;
        f0.sketch = sk;
        part.freeform_features.push_back(std::move(f0));
    }
}

bool solve_sketch_constraints_cpp(FreeformSketchState &sketch) {
    std::unordered_map<std::string, std::size_t> by_id;
    std::vector<int> var_start(sketch.entities.size());
    std::vector<double> q;
    for (std::size_t i = 0; i < sketch.entities.size(); ++i) {
        by_id[sketch.entities[i].id] = i;
        var_start[i] = static_cast<int>(q.size());
        const auto &e = sketch.entities[i];
        if (e.kind == FreeformEntityKind::Line) {
            q.push_back(e.x0); q.push_back(e.y0); q.push_back(e.x1); q.push_back(e.y1);
        } else if (e.kind == FreeformEntityKind::Circle) {
            q.push_back(e.x0); q.push_back(e.y0); q.push_back(std::max(0.0005f, e.radius));
        } else if (e.kind == FreeformEntityKind::Arc) {
            q.push_back(e.x0); q.push_back(e.y0); q.push_back(std::max(0.0005f, e.radius));
            q.push_back(e.start_deg); q.push_back(e.end_deg);
        } else {
            for (const auto &pt : e.spline_pts) {
                q.push_back(pt[0]); q.push_back(pt[1]);
            }
        }
    }
    const int n_vars = static_cast<int>(q.size());
    auto get_pt = [&](const std::vector<double> &qv, const std::string &id, int pt_idx) -> std::pair<double, double> {
        const auto it = by_id.find(id);
        if (it == by_id.end()) return {0.0, 0.0};
        const std::size_t ei = it->second;
        const int s = var_start[ei];
        const auto &e = sketch.entities[ei];
        if (e.kind == FreeformEntityKind::Line) {
            return (pt_idx == 1) ? std::make_pair(qv[s + 2], qv[s + 3]) : std::make_pair(qv[s], qv[s + 1]);
        }
        if (e.kind == FreeformEntityKind::Circle) {
            return {qv[s], qv[s + 1]};
        }
        if (e.kind == FreeformEntityKind::Arc) {
            if (pt_idx == 0) return {qv[s], qv[s + 1]};
            const double ang = (pt_idx == 1 ? qv[s + 3] : qv[s + 4]) * (3.14159265358979323846 / 180.0);
            return {qv[s] + qv[s + 2] * std::cos(ang), qv[s + 1] + qv[s + 2] * std::sin(ang)};
        }
        if (e.spline_pts.empty()) return {0.0, 0.0};
        const int k = std::clamp(pt_idx, 0, static_cast<int>(e.spline_pts.size()) - 1);
        return {qv[s + 2 * k], qv[s + 2 * k + 1]};
    };

    auto eval_res = [&](const std::vector<double> &qv) -> std::vector<double> {
        std::vector<double> r;
        for (const auto &c : sketch.constraints) {
            const auto ia = by_id.find(c.a);
            if (ia == by_id.end()) continue;
            const int sa = var_start[ia->second];
            const auto &ea = sketch.entities[ia->second];
            const auto ib = !c.b.empty() ? by_id.find(c.b) : by_id.end();
            switch (c.kind) {
            case FreeformConstraintKind::Horizontal:
                if (ea.kind == FreeformEntityKind::Line) r.push_back(qv[sa + 3] - qv[sa + 1]);
                break;
            case FreeformConstraintKind::Vertical:
                if (ea.kind == FreeformEntityKind::Line) r.push_back(qv[sa + 2] - qv[sa]);
                break;
            case FreeformConstraintKind::Length:
                if (ea.kind == FreeformEntityKind::Line)
                    r.push_back(std::hypot(qv[sa + 2] - qv[sa], qv[sa + 3] - qv[sa + 1]) - c.value);
                break;
            case FreeformConstraintKind::Radius:
                if (ea.kind == FreeformEntityKind::Circle || ea.kind == FreeformEntityKind::Arc)
                    r.push_back(qv[sa + 2] - c.value);
                break;
            case FreeformConstraintKind::Fixed: {
                const auto [px, py] = get_pt(qv, c.a, c.pt_a);
                r.push_back(px - c.target_x);
                r.push_back(py - c.target_y);
                break;
            }
            case FreeformConstraintKind::Coincident:
                if (ib != by_id.end()) {
                    const auto [ax, ay] = get_pt(qv, c.a, c.pt_a);
                    const auto [bx, by] = get_pt(qv, c.b, c.pt_b);
                    r.push_back(ax - bx);
                    r.push_back(ay - by);
                }
                break;
            case FreeformConstraintKind::Distance:
                if (ib != by_id.end()) {
                    const auto [ax, ay] = get_pt(qv, c.a, c.pt_a);
                    const auto [bx, by] = get_pt(qv, c.b, c.pt_b);
                    r.push_back(std::hypot(bx - ax, by - ay) - c.value);
                }
                break;
            case FreeformConstraintKind::Perpendicular:
                if (ib != by_id.end() && ea.kind == FreeformEntityKind::Line && sketch.entities[ib->second].kind == FreeformEntityKind::Line) {
                    const int sb = var_start[ib->second];
                    const double dxa = qv[sa + 2] - qv[sa], dya = qv[sa + 3] - qv[sa + 1];
                    const double dxb = qv[sb + 2] - qv[sb], dyb = qv[sb + 3] - qv[sb + 1];
                    const double dn = std::max(1e-9, std::hypot(dxa, dya) * std::hypot(dxb, dyb));
                    r.push_back((dxa * dxb + dya * dyb) / dn);
                }
                break;
            case FreeformConstraintKind::Parallel:
                if (ib != by_id.end() && ea.kind == FreeformEntityKind::Line && sketch.entities[ib->second].kind == FreeformEntityKind::Line) {
                    const int sb = var_start[ib->second];
                    const double dxa = qv[sa + 2] - qv[sa], dya = qv[sa + 3] - qv[sa + 1];
                    const double dxb = qv[sb + 2] - qv[sb], dyb = qv[sb + 3] - qv[sb + 1];
                    const double dn = std::max(1e-9, std::hypot(dxa, dya) * std::hypot(dxb, dyb));
                    r.push_back((dxa * dyb - dya * dxb) / dn);
                }
                break;
            case FreeformConstraintKind::Equal:
                if (ib != by_id.end()) {
                    const int sb = var_start[ib->second];
                    const auto &eb = sketch.entities[ib->second];
                    if (ea.kind == FreeformEntityKind::Line && eb.kind == FreeformEntityKind::Line) {
                        r.push_back(std::hypot(qv[sa + 2] - qv[sa], qv[sa + 3] - qv[sa + 1]) -
                                    std::hypot(qv[sb + 2] - qv[sb], qv[sb + 3] - qv[sb + 1]));
                    } else if ((ea.kind == FreeformEntityKind::Circle || ea.kind == FreeformEntityKind::Arc) &&
                               (eb.kind == FreeformEntityKind::Circle || eb.kind == FreeformEntityKind::Arc)) {
                        r.push_back(qv[sa + 2] - qv[sb + 2]);
                    }
                }
                break;
            case FreeformConstraintKind::Tangent:
                if (ib != by_id.end()) {
                    const auto &eb = sketch.entities[ib->second];
                    int sl = -1, sc = -1;
                    if (ea.kind == FreeformEntityKind::Line && (eb.kind == FreeformEntityKind::Circle || eb.kind == FreeformEntityKind::Arc)) {
                        sl = sa; sc = var_start[ib->second];
                    } else if (eb.kind == FreeformEntityKind::Line && (ea.kind == FreeformEntityKind::Circle || ea.kind == FreeformEntityKind::Arc)) {
                        sl = var_start[ib->second]; sc = sa;
                    }
                    if (sl >= 0 && sc >= 0) {
                        const double x0 = qv[sl], y0 = qv[sl + 1], x1 = qv[sl + 2], y1 = qv[sl + 3];
                        const double cx = qv[sc], cy = qv[sc + 1], rad = qv[sc + 2];
                        const double seg = std::max(1e-9, std::hypot(x1 - x0, y1 - y0));
                        const double dist = std::abs((x1 - x0) * (y0 - cy) - (x0 - cx) * (y1 - y0)) / seg;
                        r.push_back(dist - std::abs(rad));
                    }
                }
                break;
            }
        }
        return r;
    };

    double max_r = 0.0;
    int rank = 0;
    if (n_vars > 0 && !sketch.constraints.empty()) {
        double lam = 1e-5;
        for (int it = 0; it < 40; ++it) {
            const auto r = eval_res(q);
            if (r.empty()) break;
            const int m = static_cast<int>(r.size());
            double norm2 = 0.0;
            max_r = 0.0;
            for (double v : r) { norm2 += v * v; max_r = std::max(max_r, std::abs(v)); }
            if (max_r < 1e-9) break;

            std::vector<double> J(static_cast<std::size_t>(m) * n_vars, 0.0);
            for (int j = 0; j < n_vars; ++j) {
                auto qp = q;
                qp[j] += 1e-7;
                const auto rp = eval_res(qp);
                for (int i = 0; i < m; ++i) J[i * n_vars + j] = (rp[i] - r[i]) * 1e7;
            }
            std::vector<double> A(static_cast<std::size_t>(n_vars) * n_vars, 0.0), b(n_vars, 0.0), dq;
            for (int row = 0; row < n_vars; ++row) {
                A[row * n_vars + row] = lam;
                for (int i = 0; i < m; ++i) {
                    b[row] -= J[i * n_vars + row] * r[i];
                    for (int col = 0; col < n_vars; ++col) {
                        A[row * n_vars + col] += J[i * n_vars + row] * J[i * n_vars + col];
                    }
                }
            }
            if (!solve_linear_system(std::move(A), std::move(b), dq, n_vars)) break;
            auto qn = q;
            for (int j = 0; j < n_vars; ++j) qn[j] += dq[j];
            for (std::size_t i = 0; i < sketch.entities.size(); ++i) {
                if (sketch.entities[i].kind == FreeformEntityKind::Circle || sketch.entities[i].kind == FreeformEntityKind::Arc) {
                    qn[var_start[i] + 2] = std::max(0.0005, qn[var_start[i] + 2]);
                }
            }
            const auto rn = eval_res(qn);
            double norm2_n = 0.0;
            for (double v : rn) norm2_n += v * v;
            if (norm2_n <= norm2 + 1e-16) {
                q = std::move(qn);
                lam = std::max(1e-8, lam * 0.5);
            } else {
                lam = std::min(1e3, lam * 4.0);
            }
        }
        const auto rf = eval_res(q);
        max_r = 0.0;
        for (double v : rf) max_r = std::max(max_r, std::abs(v));
        if (!rf.empty()) {
            const int m = static_cast<int>(rf.size());
            std::vector<double> Jf(static_cast<std::size_t>(m) * n_vars, 0.0);
            for (int j = 0; j < n_vars; ++j) {
                auto qp = q;
                qp[j] += 1e-7;
                const auto rp = eval_res(qp);
                for (int i = 0; i < m; ++i) Jf[i * n_vars + j] = (rp[i] - rf[i]) * 1e7;
            }
            rank = matrix_rank(std::move(Jf), m, n_vars);
        }
    }

    for (std::size_t i = 0; i < sketch.entities.size(); ++i) {
        const int s = var_start[i];
        auto &e = sketch.entities[i];
        if (e.kind == FreeformEntityKind::Line) {
            e.x0 = static_cast<float>(q[s]); e.y0 = static_cast<float>(q[s + 1]);
            e.x1 = static_cast<float>(q[s + 2]); e.y1 = static_cast<float>(q[s + 3]);
        } else if (e.kind == FreeformEntityKind::Circle) {
            e.x0 = static_cast<float>(q[s]); e.y0 = static_cast<float>(q[s + 1]);
            e.radius = static_cast<float>(q[s + 2]);
        } else if (e.kind == FreeformEntityKind::Arc) {
            e.x0 = static_cast<float>(q[s]); e.y0 = static_cast<float>(q[s + 1]);
            e.radius = static_cast<float>(q[s + 2]);
            e.start_deg = static_cast<float>(q[s + 3]); e.end_deg = static_cast<float>(q[s + 4]);
        } else {
            for (std::size_t k = 0; k < e.spline_pts.size(); ++k) {
                e.spline_pts[k][0] = static_cast<float>(q[s + 2 * k]);
                e.spline_pts[k][1] = static_cast<float>(q[s + 2 * k + 1]);
            }
        }
    }
    sketch.max_residual = max_r;
    sketch.converged = (max_r < 2e-4);
    sketch.dof = std::max(0, n_vars - rank);
    return sketch.converged;
}

PickedFaceResult pick_face_under_cursor(const GeneratedCADScene &scene, const FreeformBrepCache &brep,
                                        const CameraOrbitState &cam, ViewportLayout layout, int vp_w, int vp_h,
                                        float local_mx, float local_my) {
    PickedFaceResult out;
    if (vp_w <= 2 || vp_h <= 2 || scene.indices.size() < 3) return out;
    if (layout != ViewportLayout::Single3D) return out;

    const float yaw = cam.yaw_deg * kPiF / 180.0f;
    const float pitch = std::clamp(cam.pitch_deg, -85.0f, 85.0f) * kPiF / 180.0f;
    const std::array<float, 3> eye{
        cam.target_m[0] + cam.distance_m * std::cos(pitch) * std::cos(yaw),
        cam.target_m[1] + cam.distance_m * std::cos(pitch) * std::sin(yaw),
        cam.target_m[2] + cam.distance_m * std::sin(pitch),
    };
    const auto f = v3_norm(v3_sub(cam.target_m, eye));
    const auto s = v3_norm(v3_cross(f, {0.0f, 0.0f, 1.0f}));
    const auto u = v3_cross(s, f);
    const float aspect = static_cast<float>(vp_w) / static_cast<float>(vp_h);
    const float tan_hy = std::tan(42.0f * 0.5f * kPiF / 180.0f);
    const float tan_hx = tan_hy * aspect;
    const float ndc_x = 2.0f * (local_mx / static_cast<float>(vp_w)) - 1.0f;
    const float ndc_y = 1.0f - 2.0f * (local_my / static_cast<float>(vp_h));
    const auto ray_d = v3_norm(v3_add(v3_add(f, v3_scale(s, ndc_x * tan_hx)), v3_scale(u, ndc_y * tan_hy)));

    float best_t = 1e9f;
    std::size_t best_tri = 0;
    std::array<float, 3> best_n{0.0f, 0.0f, 1.0f};
    const std::size_t n_tris = scene.indices.size() / 3;
    for (std::size_t ti = 0; ti < n_tris; ++ti) {
        const auto &v0 = scene.vertices[scene.indices[3 * ti + 0]];
        const auto &v1 = scene.vertices[scene.indices[3 * ti + 1]];
        const auto &v2 = scene.vertices[scene.indices[3 * ti + 2]];
        const std::array<float, 3> p0{v0.px, v0.py, v0.pz}, p1{v1.px, v1.py, v1.pz}, p2{v2.px, v2.py, v2.pz};
        const auto e1 = v3_sub(p1, p0), e2 = v3_sub(p2, p0);
        const auto pvec = v3_cross(ray_d, e2);
        const float det = v3_dot(e1, pvec);
        if (std::abs(det) < 1e-8f) continue;
        const float inv_det = 1.0f / det;
        const auto tvec = v3_sub(eye, p0);
        const float bu = v3_dot(tvec, pvec) * inv_det;
        if (bu < 0.0f || bu > 1.0f) continue;
        const auto qvec = v3_cross(tvec, e1);
        const float bv = v3_dot(ray_d, qvec) * inv_det;
        if (bv < 0.0f || bu + bv > 1.0f) continue;
        const float t = v3_dot(e2, qvec) * inv_det;
        if (t > 0.02f && t < best_t) {
            best_t = t;
            best_tri = ti;
            best_n = v3_norm(v3_cross(e1, e2));
            if (v3_dot(best_n, ray_d) > 0.0f) best_n = v3_scale(best_n, -1.0f);
        }
    }
    if (best_t > 1e8f) return out;
    out.hit = true;
    out.hit_pos_m = v3_add(eye, v3_scale(ray_d, best_t));
    if (best_tri < scene.tri_face_ids.size() && scene.tri_face_ids[best_tri] >= 0) {
        out.face_id = scene.tri_face_ids[best_tri];
        for (const auto &fm : brep.faces) {
            if (fm.face_id == out.face_id) {
                out.workplane.preset = "FACE";
                out.workplane.picked_face_id = out.face_id;
                out.workplane.origin_m = fm.center_m;
                out.workplane.normal = fm.normal;
                out.workplane.u_axis = fm.u_axis;
                out.workplane.v_axis = fm.v_axis;
                return out;
            }
        }
    }
    out.face_id = static_cast<int>(best_tri);
    out.workplane = make_workplane_from_normal(-1, out.hit_pos_m, best_n);
    out.workplane.preset = "FACE";
    return out;
}

std::string build_freeform_cad_payload_json(const CustomPartParams &part, const std::filesystem::path &mesh_out_path,
                                            const std::filesystem::path &export_dir) {
    std::ostringstream oss;
    oss << "{\n"
        << "  \"part_name\": \"" << part.part_name << "\",\n"
        << "  \"density_kg_m3\": " << part.density_kg_m3 << ",\n"
        << "  \"density_source\": \"builtin_material_library\",\n"
        << "  \"mesh_out_path\": \"" << mesh_out_path.generic_string() << "\",\n"
        << "  \"export_dir\": \"" << export_dir.generic_string() << "\",\n"
        << "  \"features\": [\n";
    for (std::size_t fi = 0; fi < part.freeform_features.size(); ++fi) {
        const auto &ft = part.freeform_features[fi];
        const auto &sk = ft.sketch.entities.empty() ? part.freeform_sketch : ft.sketch;
        const auto &wp = sk.workplane.normal[0] == 0.0f && sk.workplane.normal[1] == 0.0f && sk.workplane.normal[2] == 0.0f
                             ? part.active_workplane
                             : sk.workplane;
        oss << "    {\n"
            << "      \"op\": \"" << op_kind_str(ft.op) << "\",\n"
            << "      \"suppressed\": " << (ft.suppressed ? "true" : "false") << ",\n"
            << "      \"symmetric\": " << (ft.symmetric ? "true" : "false") << ",\n"
            << "      \"depth_m\": " << ft.depth_m << ",\n"
            << "      \"angle_deg\": " << ft.angle_deg << ",\n"
            << "      \"radius_m\": " << ft.radius_m << ",\n"
            << "      \"distance_m\": " << ft.radius_m << ",\n"
            << "      \"thickness_m\": " << ft.radius_m << ",\n"
            << "      \"loft_offset_m\": " << ft.loft_offset_m << ",\n"
            << "      \"loft_scale\": " << ft.loft_scale << ",\n";
        if (ft.op == FreeformOpKind::Fillet || ft.op == FreeformOpKind::Chamfer) {
            oss << "      \"edge_indices\": [";
        } else {
            oss << "      \"face_indices\": [";
        }
        for (std::size_t ti = 0; ti < ft.target_indices.size(); ++ti) {
            oss << ft.target_indices[ti] << (ti + 1 < ft.target_indices.size() ? ", " : "");
        }
        oss << "],\n      \"workplane\": {\n"
            << "        \"preset\": \"" << wp.preset << "\",\n"
            << "        \"face_id\": " << wp.picked_face_id << ",\n"
            << "        \"origin_m\": [" << wp.origin_m[0] << ", " << wp.origin_m[1] << ", " << wp.origin_m[2] << "],\n"
            << "        \"normal\": [" << wp.normal[0] << ", " << wp.normal[1] << ", " << wp.normal[2] << "],\n"
            << "        \"u_axis\": [" << wp.u_axis[0] << ", " << wp.u_axis[1] << ", " << wp.u_axis[2] << "]\n"
            << "      },\n"
            << "      \"sketch\": {\n";
        write_sketch_json(oss, sk, wp, 8);
        oss << "      }\n"
            << "    }" << (fi + 1 < part.freeform_features.size() ? "," : "") << "\n";
    }
    oss << "  ]\n}\n";
    return oss.str();
}

namespace {
std::vector<double> parse_number_array_section(const std::string &text, const std::string &key) {
    std::vector<double> nums;
    const auto kpos = text.find("\"" + key + "\"");
    if (kpos == std::string::npos) return nums;
    const auto lb = text.find('[', kpos);
    if (lb == std::string::npos) return nums;
    int depth = 0;
    std::size_t end_pos = text.size();
    for (std::size_t i = lb; i < text.size(); ++i) {
        if (text[i] == '[') ++depth;
        else if (text[i] == ']') {
            --depth;
            if (depth == 0) { end_pos = i; break; }
        }
    }
    const char *p = text.c_str() + lb;
    const char *pend = text.c_str() + end_pos;
    while (p < pend) {
        if ((*p >= '0' && *p <= '9') || *p == '-' || *p == '.') {
            char *next_p = nullptr;
            double v = std::strtod(p, &next_p);
            if (next_p > p) {
                nums.push_back(v);
                p = next_p;
                continue;
            }
        }
        ++p;
    }
    return nums;
}
} // namespace

bool load_occt_mesh_json(const std::filesystem::path &mesh_json_path, FreeformBrepCache &cache) {
    std::ifstream ifs(mesh_json_path);
    if (!ifs) return false;
    std::string text((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    if (text.empty()) return false;

    const auto v_nums = parse_number_array_section(text, "vertices");
    const auto i_nums = parse_number_array_section(text, "indices");
    const auto e_nums = parse_number_array_section(text, "edges");
    const auto vol_nums = parse_number_array_section(text, "volume_m3");
    if (v_nums.size() < 21 || i_nums.size() < 3) return false;

    cache.vertices.clear();
    cache.indices.clear();
    cache.tri_face_ids.clear();
    cache.edges.clear();
    cache.faces.clear();

    const std::size_t nv = v_nums.size() / 7;
    std::vector<int> vert_fids(nv, -1);
    cache.vertices.reserve(nv);
    for (std::size_t i = 0; i < nv; ++i) {
        const std::size_t k = i * 7;
        cache.vertices.push_back({static_cast<float>(v_nums[k + 0]), static_cast<float>(v_nums[k + 1]),
                                  static_cast<float>(v_nums[k + 2]), static_cast<float>(v_nums[k + 3]),
                                  static_cast<float>(v_nums[k + 4]), static_cast<float>(v_nums[k + 5]),
                                  0.76f, 0.82f, 0.90f, 0.0f});
        vert_fids[i] = static_cast<int>(std::llround(v_nums[k + 6]));
    }
    for (std::size_t i = 0; i + 2 < i_nums.size(); i += 3) {
        const auto a = static_cast<std::uint32_t>(i_nums[i + 0]);
        const auto b = static_cast<std::uint32_t>(i_nums[i + 1]);
        const auto c = static_cast<std::uint32_t>(i_nums[i + 2]);
        if (a < nv && b < nv && c < nv) {
            cache.indices.push_back(a); cache.indices.push_back(b); cache.indices.push_back(c);
            cache.tri_face_ids.push_back(vert_fids[a]);
        }
    }
    for (std::size_t i = 0; i + 6 < e_nums.size(); i += 7) {
        cache.edges.push_back({static_cast<float>(e_nums[i + 0]), static_cast<float>(e_nums[i + 1]),
                               static_cast<float>(e_nums[i + 2]), 0.14f, 0.18f, 0.24f});
        cache.edges.push_back({static_cast<float>(e_nums[i + 3]), static_cast<float>(e_nums[i + 4]),
                               static_cast<float>(e_nums[i + 5]), 0.14f, 0.18f, 0.24f});
    }

    auto read_scalar = [&](const char *key, double fallback) -> double {
        const auto kp = text.find(std::string("\"") + key + "\"");
        if (kp == std::string::npos) return fallback;
        const auto cp = text.find(':', kp);
        if (cp == std::string::npos) return fallback;
        return std::atof(text.c_str() + cp + 1);
    };
    cache.volume_m3 = read_scalar("volume_m3", 0.0);
    cache.mass_kg = read_scalar("mass_kg", 0.0);
    const auto cog = parse_number_array_section(text, "center_of_mass_m");
    if (cog.size() == 3) cache.cog_m = {cog[0], cog[1], cog[2]};

    // Parse faces list metadata
    const auto fpos = text.find("\"faces\"");
    if (fpos != std::string::npos) {
        std::size_t scan = fpos;
        while (true) {
            const auto idp = text.find("\"face_id\"", scan);
            if (idp == std::string::npos) break;
            const auto brace_end = text.find('}', idp);
            if (brace_end == std::string::npos) break;
            const std::string slice = text.substr(idp, brace_end - idp + 1);
            BrepFaceMeta fm;
            fm.face_id = static_cast<int>(std::atoi(slice.c_str() + slice.find(':') + 1));
            const auto cm = parse_number_array_section(slice, "center_m");
            const auto nm = parse_number_array_section(slice, "normal");
            const auto um = parse_number_array_section(slice, "u_axis");
            const auto vm = parse_number_array_section(slice, "v_axis");
            if (cm.size() == 3) fm.center_m = {static_cast<float>(cm[0]), static_cast<float>(cm[1]), static_cast<float>(cm[2])};
            if (nm.size() == 3) fm.normal = {static_cast<float>(nm[0]), static_cast<float>(nm[1]), static_cast<float>(nm[2])};
            if (um.size() == 3) fm.u_axis = {static_cast<float>(um[0]), static_cast<float>(um[1]), static_cast<float>(um[2])};
            if (vm.size() == 3) fm.v_axis = {static_cast<float>(vm[0]), static_cast<float>(vm[1]), static_cast<float>(vm[2])};
            cache.faces.push_back(fm);
            scan = brace_end + 1;
        }
    }
    cache.has_occt_mesh = !cache.indices.empty();
    cache.occt_exact_brep = cache.has_occt_mesh;
    cache.status_summary = "OCCT B-Rep Ready (" + std::to_string(cache.faces.size()) + " faces, " +
                           std::to_string(cache.indices.size() / 3) + " tris)";
    (void)vol_nums;
    return cache.has_occt_mesh;
}

std::string serialize_freeform_part_json(const CustomPartParams &part) {
    std::ostringstream oss;
    oss << "{\n"
        << "  \"freeform_mode\": " << (part.freeform_mode ? "true" : "false") << ",\n"
        << "  \"picked_face_id\": " << part.picked_face_id << ",\n"
        << "  \"freeform_sketch\": {\n";
    write_sketch_json(oss, part.freeform_sketch, part.active_workplane, 4);
    oss << "  },\n"
        << "  \"freeform_features\": [\n";
    for (std::size_t fi = 0; fi < part.freeform_features.size(); ++fi) {
        const auto &ft = part.freeform_features[fi];
        oss << "    {\n"
            << "      \"op\": \"" << op_kind_str(ft.op) << "\",\n"
            << "      \"suppressed\": " << (ft.suppressed ? "true" : "false") << ",\n"
            << "      \"symmetric\": " << (ft.symmetric ? "true" : "false") << ",\n"
            << "      \"depth_m\": " << ft.depth_m << ",\n"
            << "      \"angle_deg\": " << ft.angle_deg << ",\n"
            << "      \"radius_m\": " << ft.radius_m << ",\n"
            << "      \"loft_offset_m\": " << ft.loft_offset_m << ",\n"
            << "      \"loft_scale\": " << ft.loft_scale << ",\n"
            << "      \"sketch\": {\n";
        write_sketch_json(oss, ft.sketch, ft.sketch.workplane, 8);
        oss << "      }\n"
            << "    }" << (fi + 1 < part.freeform_features.size() ? "," : "") << "\n";
    }
    oss << "  ]\n}";
    return oss.str();
}

namespace {
std::vector<std::string> split_json_objects_in_array(const std::string &arr_slice) {
    std::vector<std::string> objs;
    int depth = 0;
    std::size_t start = std::string::npos;
    for (std::size_t i = 0; i < arr_slice.size(); ++i) {
        if (arr_slice[i] == '{') {
            if (depth == 0) start = i;
            ++depth;
        } else if (arr_slice[i] == '}') {
            --depth;
            if (depth == 0 && start != std::string::npos) {
                objs.push_back(arr_slice.substr(start, i - start + 1));
                start = std::string::npos;
            }
        }
    }
    return objs;
}

std::string find_array_slice(const std::string &obj, const std::string &key) {
    const auto kp = obj.find("\"" + key + "\"");
    if (kp == std::string::npos) return {};
    const auto lb = obj.find('[', kp);
    if (lb == std::string::npos) return {};
    int depth = 0;
    for (std::size_t i = lb; i < obj.size(); ++i) {
        if (obj[i] == '[') ++depth;
        else if (obj[i] == ']') {
            --depth;
            if (depth == 0) return obj.substr(lb, i - lb + 1);
        }
    }
    return {};
}

std::string find_obj_slice(const std::string &obj, const std::string &key) {
    const auto kp = obj.find("\"" + key + "\"");
    if (kp == std::string::npos) return {};
    const auto lb = obj.find('{', kp);
    if (lb == std::string::npos) return {};
    int depth = 0;
    for (std::size_t i = lb; i < obj.size(); ++i) {
        if (obj[i] == '{') ++depth;
        else if (obj[i] == '}') {
            --depth;
            if (depth == 0) return obj.substr(lb, i - lb + 1);
        }
    }
    return {};
}

std::string read_str_field(const std::string &obj, const char *key, const char *def_val = "") {
    const std::string pat = std::string("\"") + key + "\"";
    const auto kp = obj.find(pat);
    if (kp == std::string::npos) return def_val;
    const auto col = obj.find(':', kp + pat.size());
    if (col == std::string::npos) return def_val;
    const auto q1 = obj.find('"', col + 1);
    if (q1 == std::string::npos) return def_val;
    const auto q2 = obj.find('"', q1 + 1);
    return (q2 != std::string::npos) ? obj.substr(q1 + 1, q2 - q1 - 1) : def_val;
}

double read_num_field(const std::string &obj, const char *key, double def_val) {
    const std::string pat = std::string("\"") + key + "\"";
    const auto kp = obj.find(pat);
    if (kp == std::string::npos) return def_val;
    const auto col = obj.find(':', kp + pat.size());
    if (col == std::string::npos) return def_val;
    return std::atof(obj.c_str() + col + 1);
}

bool read_bool_field(const std::string &obj, const char *key, bool def_val) {
    const std::string pat = std::string("\"") + key + "\"";
    const auto kp = obj.find(pat);
    if (kp == std::string::npos) return def_val;
    const auto col = obj.find(':', kp + pat.size());
    if (col == std::string::npos) return def_val;
    const auto sub = obj.substr(col + 1, 12);
    if (sub.find("true") != std::string::npos) return true;
    if (sub.find("false") != std::string::npos) return false;
    return def_val;
}

void parse_sketch_block(const std::string &sk_obj, FreeformSketchState &sk) {
    if (sk_obj.empty()) return;
    const std::string wp_obj = find_obj_slice(sk_obj, "workplane");
    if (!wp_obj.empty()) {
        sk.workplane.preset = read_str_field(wp_obj, "preset", "XY");
        sk.workplane.picked_face_id = static_cast<int>(read_num_field(wp_obj, "face_id", -1.0));
        const auto om = parse_number_array_section(wp_obj, "origin_m");
        const auto nm = parse_number_array_section(wp_obj, "normal");
        const auto um = parse_number_array_section(wp_obj, "u_axis");
        if (om.size() == 3) sk.workplane.origin_m = {static_cast<float>(om[0]), static_cast<float>(om[1]), static_cast<float>(om[2])};
        if (nm.size() == 3) sk.workplane.normal = {static_cast<float>(nm[0]), static_cast<float>(nm[1]), static_cast<float>(nm[2])};
        if (um.size() == 3) {
            sk.workplane.u_axis = {static_cast<float>(um[0]), static_cast<float>(um[1]), static_cast<float>(um[2])};
            sk.workplane.v_axis = v3_norm(v3_cross(sk.workplane.normal, sk.workplane.u_axis));
        }
    }
    sk.entities.clear();
    for (const auto &eo : split_json_objects_in_array(find_array_slice(sk_obj, "entities"))) {
        FreeformSketchEntity e;
        e.id = read_str_field(eo, "id", "e0");
        e.construction = read_bool_field(eo, "construction", false);
        const std::string kd = read_str_field(eo, "kind", "line");
        if (kd == "circle") {
            e.kind = FreeformEntityKind::Circle;
            const auto c = parse_number_array_section(eo, "center");
            if (c.size() >= 2) { e.x0 = static_cast<float>(c[0]); e.y0 = static_cast<float>(c[1]); }
            e.radius = static_cast<float>(read_num_field(eo, "radius", 0.015));
        } else if (kd == "arc") {
            e.kind = FreeformEntityKind::Arc;
            const auto c = parse_number_array_section(eo, "center");
            if (c.size() >= 2) { e.x0 = static_cast<float>(c[0]); e.y0 = static_cast<float>(c[1]); }
            e.radius = static_cast<float>(read_num_field(eo, "radius", 0.015));
            e.start_deg = static_cast<float>(read_num_field(eo, "start_deg", 0.0));
            e.end_deg = static_cast<float>(read_num_field(eo, "end_deg", 180.0));
        } else if (kd == "spline") {
            e.kind = FreeformEntityKind::Spline;
            e.closed = read_bool_field(eo, "closed", true);
            const auto pts = parse_number_array_section(eo, "points");
            for (std::size_t k = 0; k + 1 < pts.size(); k += 2) {
                e.spline_pts.push_back({static_cast<float>(pts[k]), static_cast<float>(pts[k + 1])});
            }
        } else {
            e.kind = FreeformEntityKind::Line;
            const auto p0 = parse_number_array_section(eo, "p0");
            const auto p1 = parse_number_array_section(eo, "p1");
            if (p0.size() >= 2) { e.x0 = static_cast<float>(p0[0]); e.y0 = static_cast<float>(p0[1]); }
            if (p1.size() >= 2) { e.x1 = static_cast<float>(p1[0]); e.y1 = static_cast<float>(p1[1]); }
        }
        sk.entities.push_back(std::move(e));
    }
    sk.constraints.clear();
    for (const auto &co : split_json_objects_in_array(find_array_slice(sk_obj, "constraints"))) {
        FreeformSketchConstraint c;
        const std::string ck = read_str_field(co, "kind", "length");
        if (ck == "horizontal") c.kind = FreeformConstraintKind::Horizontal;
        else if (ck == "vertical") c.kind = FreeformConstraintKind::Vertical;
        else if (ck == "radius") c.kind = FreeformConstraintKind::Radius;
        else if (ck == "fixed") c.kind = FreeformConstraintKind::Fixed;
        else if (ck == "coincident") c.kind = FreeformConstraintKind::Coincident;
        else if (ck == "perpendicular") c.kind = FreeformConstraintKind::Perpendicular;
        else if (ck == "parallel") c.kind = FreeformConstraintKind::Parallel;
        else if (ck == "tangent") c.kind = FreeformConstraintKind::Tangent;
        else if (ck == "equal") c.kind = FreeformConstraintKind::Equal;
        else if (ck == "distance") c.kind = FreeformConstraintKind::Distance;
        else c.kind = FreeformConstraintKind::Length;
        c.a = read_str_field(co, "a", "");
        c.b = read_str_field(co, "b", "");
        c.pt_a = static_cast<int>(read_num_field(co, "pt_a", 0.0));
        c.pt_b = static_cast<int>(read_num_field(co, "pt_b", 0.0));
        c.value = static_cast<float>(read_num_field(co, "value", 0.05));
        const auto tx = parse_number_array_section(co, "target_xy");
        if (tx.size() >= 2) { c.target_x = static_cast<float>(tx[0]); c.target_y = static_cast<float>(tx[1]); }
        sk.constraints.push_back(std::move(c));
    }
    solve_sketch_constraints_cpp(sk);
}
} // namespace

bool deserialize_freeform_part_json(const std::string &json_text, CustomPartParams &part) {
    if (json_text.find("\"freeform_mode\": true") == std::string::npos) return false;
    part.freeform_mode = true;
    part.sketch_kind = SketchShapeKind::FreeformBrep;
    part.picked_face_id = static_cast<int>(read_num_field(json_text, "picked_face_id", -1.0));
    const std::string sk_obj = find_obj_slice(json_text, "freeform_sketch");
    if (!sk_obj.empty()) {
        parse_sketch_block(sk_obj, part.freeform_sketch);
        part.active_workplane = part.freeform_sketch.workplane;
    }
    const std::string f_arr = find_array_slice(json_text, "freeform_features");
    if (!f_arr.empty()) {
        part.freeform_features.clear();
        for (const auto &fo : split_json_objects_in_array(f_arr)) {
            FreeformCadFeature ft;
            const std::string op = read_str_field(fo, "op", "extrude_boss");
            if (op == "extrude_cut") ft.op = FreeformOpKind::ExtrudeCut;
            else if (op == "revolve") ft.op = FreeformOpKind::Revolve;
            else if (op == "loft") ft.op = FreeformOpKind::Loft;
            else if (op == "fillet") ft.op = FreeformOpKind::Fillet;
            else if (op == "chamfer") ft.op = FreeformOpKind::Chamfer;
            else if (op == "shell") ft.op = FreeformOpKind::Shell;
            else ft.op = FreeformOpKind::ExtrudeBoss;
            ft.suppressed = read_bool_field(fo, "suppressed", false);
            ft.symmetric = read_bool_field(fo, "symmetric", false);
            ft.depth_m = static_cast<float>(read_num_field(fo, "depth_m", 0.030));
            ft.angle_deg = static_cast<float>(read_num_field(fo, "angle_deg", 360.0));
            ft.radius_m = static_cast<float>(read_num_field(fo, "radius_m", 0.002));
            ft.loft_offset_m = static_cast<float>(read_num_field(fo, "loft_offset_m", 0.060));
            ft.loft_scale = static_cast<float>(read_num_field(fo, "loft_scale", 0.55));
            const std::string fsk = find_obj_slice(fo, "sketch");
            if (!fsk.empty()) parse_sketch_block(fsk, ft.sketch);
            part.freeform_features.push_back(std::move(ft));
        }
    }
    if (part.freeform_sketch.entities.empty() && part.freeform_features.empty()) {
        init_default_freeform_sketch(part);
    }
    return true;
}

std::string build_embedded_cfd_fea_payload_json(const AircraftDesignParams &params, const GeneratedCADScene &scene,
                                                const LiveEvidenceSummary &summary,
                                                const std::filesystem::path &field_out_path,
                                                const std::filesystem::path &export_dir) {
    std::ostringstream oss;
    oss << "{\n"
        << "  \"wingspan_m\": " << params.wingspan_m << ",\n"
        << "  \"root_chord_m\": " << params.root_chord_m << ",\n"
        << "  \"tip_chord_m\": " << params.tip_chord_m << ",\n"
        << "  \"sweep_deg\": " << params.sweep_deg << ",\n"
        << "  \"airfoil_code\": \"" << params.airfoil_code << "\",\n"
        << "  \"airspeed_m_s\": " << params.airspeed_m_s << ",\n"
        << "  \"alpha_deg\": " << params.alpha_deg << ",\n"
        << "  \"air_density_kg_m3\": " << summary.air_density_kg_m3 << ",\n"
        << "  \"mach\": " << summary.mach << ",\n"
        << "  \"total_mass_kg\": " << std::max(0.1, summary.total_mass_kg) << ",\n"
        << "  \"youngs_modulus_pa\": " << (params.titanium_screws ? 110.0e9 : 42.0e9) << ",\n"
        << "  \"yield_strength_mpa\": " << (params.family == VehicleFamily::CustomPart ? 275.0 : 240.0) << ",\n"
        << "  \"mesh_resolution\": \"medium\",\n"
        << "  \"field_out_path\": \"" << field_out_path.generic_string() << "\",\n"
        << "  \"export_dir\": \"" << export_dir.generic_string() << "\"";

    const std::size_t n_tris = scene.indices.size() / 3;
    if (!scene.vertices.empty() && n_tris >= 4 && n_tris <= 12000) {
        oss << ",\n  \"vertices\": [\n";
        for (std::size_t i = 0; i < scene.vertices.size(); ++i) {
            const auto &v = scene.vertices[i];
            oss << "    [" << v.px << ", " << v.py << ", " << v.pz << "]"
                << (i + 1 < scene.vertices.size() ? "," : "") << "\n";
        }
        oss << "  ],\n  \"triangles\": [\n";
        for (std::size_t t = 0; t < n_tris; ++t) {
            oss << "    [" << scene.indices[3 * t] << ", " << scene.indices[3 * t + 1] << ", "
                << scene.indices[3 * t + 2] << "]" << (t + 1 < n_tris ? "," : "") << "\n";
        }
        oss << "  ]\n";
    } else {
        oss << "\n";
    }
    oss << "}";
    return oss.str();
}

bool load_embedded_cfd_fea_json(const std::filesystem::path &field_json_path, EmbeddedCfdFeaCache &cache) {
    std::ifstream ifs(field_json_path);
    if (!ifs) return false;
    std::string text((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    if (text.empty()) return false;

    const auto cp_vals = parse_number_array_section(text, "panel_cp");
    const auto vm_vals = parse_number_array_section(text, "panel_von_mises_mpa");
    if (cp_vals.empty() || vm_vals.size() != cp_vals.size()) return false;

    cache.n_fluid_cells = static_cast<int>(read_num_field(text, "n_fluid_cells", 0.0));
    cache.n_boundary_cut_cells = static_cast<int>(read_num_field(text, "n_boundary_cut_cells", 0.0));
    cache.n_solid_elems = static_cast<int>(read_num_field(text, "n_solid_elems", 0.0));
    cache.integrated_cl = read_num_field(text, "integrated_cl", 0.0);
    cache.integrated_cd = read_num_field(text, "integrated_cd", 0.0);
    cache.peak_suction_cp = read_num_field(text, "peak_suction_cp", 0.0);
    cache.peak_vm_mpa = read_num_field(text, "peak_von_mises_mpa", 0.0);
    cache.max_disp_mm = read_num_field(text, "max_disp_mm", 0.0);
    cache.structural_fos = read_num_field(text, "structural_fos", 5.0);

    cache.panel_cp.resize(cp_vals.size());
    cache.panel_vm_mpa.resize(vm_vals.size());
    for (std::size_t i = 0; i < cp_vals.size(); ++i) {
        cache.panel_cp[i] = static_cast<float>(cp_vals[i]);
        cache.panel_vm_mpa[i] = static_cast<float>(vm_vals[i]);
    }

    cache.streamlines_3d.clear();
    const std::string sl_arr = find_array_slice(text, "streamlines_3d");
    if (!sl_arr.empty()) {
        int depth = 0;
        std::size_t line_start = std::string::npos;
        std::size_t pt_start = std::string::npos;
        std::vector<std::array<float, 3>> cur_line;
        for (std::size_t i = 0; i < sl_arr.size(); ++i) {
            if (sl_arr[i] == '[') {
                ++depth;
                if (depth == 2) {
                    cur_line.clear();
                    line_start = i;
                } else if (depth == 3) {
                    pt_start = i;
                }
            } else if (sl_arr[i] == ']') {
                if (depth == 3 && pt_start != std::string::npos) {
                    float px = 0.0f, py = 0.0f, pz = 0.0f;
                    if (std::sscanf(sl_arr.c_str() + pt_start + 1, "%f , %f , %f", &px, &py, &pz) == 3) {
                        cur_line.push_back({px, py, pz});
                    }
                    pt_start = std::string::npos;
                } else if (depth == 2 && line_start != std::string::npos) {
                    if (cur_line.size() >= 2) {
                        cache.streamlines_3d.push_back(std::move(cur_line));
                    }
                    line_start = std::string::npos;
                }
                --depth;
            }
        }
    }

    cache.has_field = true;
    cache.status_summary = "3D FVM/FEM Solved (" + std::to_string(cache.n_fluid_cells) + " fluid, " +
                           std::to_string(cache.n_solid_elems) + " C3D8)";
    return true;
}

void draw_freeform_sketcher_window(FreeformSketchUiState &ui, AircraftDesignParams &params,
                                   const FreeformBrepCache &brep,
                                   const std::function<void()> &on_push_undo,
                                   const std::function<void()> &on_rebuild_local,
                                   const std::function<void()> &on_build_occt) {
    if (!ui.open_window) return;
    init_default_freeform_sketch(params.active_part);
    auto &part = params.active_part;
    auto &sk = part.freeform_sketch;

    const ImGuiViewport *vp = ImGui::GetMainViewport();
    ImGui::SetNextWindowPos(ImVec2(vp->WorkPos.x + 18.0f, vp->WorkPos.y + 74.0f), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowSize(ImVec2(545.0f, 600.0f), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("Freeform Constraint Sketcher & OCCT CAD Studio", &ui.open_window)) {
        ImGui::End();
        return;
    }

    // 1. Workplane & 3D Face Picker Bar
    ImGui::Text("Sketch Workplane: %s", part.active_workplane.preset.c_str());
    if (part.active_workplane.picked_face_id >= 0) {
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(0.10f, 0.45f, 0.85f, 1.0f), "(Face #%d)", part.active_workplane.picked_face_id);
    }
    if (ImGui::SmallButton("XY Plane")) {
        on_push_undo();
        part.active_workplane = make_workplane_from_normal(-1, {0, 0, 0}, {0, 0, 1});
        part.active_workplane.preset = "XY";
        part.picked_face_id = -1;
        sk.workplane = part.active_workplane;
    }
    ImGui::SameLine();
    if (ImGui::SmallButton("XZ Plane")) {
        on_push_undo();
        part.active_workplane = make_workplane_from_normal(-1, {0, 0, 0}, {0, -1, 0});
        part.active_workplane.preset = "XZ";
        part.active_workplane.u_axis = {1, 0, 0};
        part.active_workplane.v_axis = {0, 0, 1};
        part.picked_face_id = -1;
        sk.workplane = part.active_workplane;
    }
    ImGui::SameLine();
    if (ImGui::SmallButton("YZ Plane")) {
        on_push_undo();
        part.active_workplane = make_workplane_from_normal(-1, {0, 0, 0}, {1, 0, 0});
        part.active_workplane.preset = "YZ";
        part.active_workplane.u_axis = {0, 1, 0};
        part.active_workplane.v_axis = {0, 0, 1};
        part.picked_face_id = -1;
        sk.workplane = part.active_workplane;
    }
    ImGui::SameLine();
    if (ImGui::Button(ui.pick_face_mode ? "Picking 3D Face..." : "Pick 3D Face")) {
        ui.pick_face_mode = !ui.pick_face_mode;
    }

    ImGui::Separator();
    // 2. Draw Tool Strip
    auto tool_btn = [&](const char *lbl, SketchTool t) {
        const bool active = (ui.active_tool == t);
        if (active) ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.18f, 0.45f, 0.90f, 1.0f));
        if (active) ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(1, 1, 1, 1));
        if (ImGui::SmallButton(lbl)) { ui.active_tool = t; ui.pending_pts.clear(); }
        if (active) ImGui::PopStyleColor(2);
        ImGui::SameLine();
    };
    tool_btn("Drag", SketchTool::SelectDrag);
    tool_btn("Line", SketchTool::DrawLine);
    tool_btn("Rect", SketchTool::DrawRect);
    tool_btn("Circle", SketchTool::DrawCircle);
    tool_btn("3Pt Arc", SketchTool::DrawArc);
    tool_btn("Spline", SketchTool::DrawSpline);
    if (ImGui::SmallButton("Clear")) {
        on_push_undo();
        sk.entities.clear();
        sk.constraints.clear();
        ui.selected_entity_idx = -1;
        ui.second_entity_idx = -1;
        ui.pending_pts.clear();
    }

    // 3. Interactive 2D CAD Canvas
    const ImVec2 avail = ImGui::GetContentRegionAvail();
    const ImVec2 size(std::max(240.0f, avail.x), 240.0f);
    const ImVec2 p0 = ImGui::GetCursorScreenPos();
    const ImVec2 p1(p0.x + size.x, p0.y + size.y);
    ImDrawList *dl = ImGui::GetWindowDrawList();
    dl->AddRectFilled(p0, p1, IM_COL32(249, 251, 255, 255), 4.0f);
    dl->AddRect(p0, p1, IM_COL32(190, 202, 220, 255), 4.0f);

    const ImVec2 origin_px(p0.x + size.x * 0.5f, p0.y + size.y * 0.5f);
    const float px_per_m = (size.x * 0.45f) / 0.12f; // +-120 mm visible span
    auto to_px = [&](float xm, float ym) -> ImVec2 {
        return ImVec2(origin_px.x + xm * px_per_m, origin_px.y - ym * px_per_m);
    };
    auto to_m = [&](ImVec2 mp) -> std::array<float, 2> {
        float x = (mp.x - origin_px.x) / px_per_m;
        float y = (origin_px.y - mp.y) / px_per_m;
        if (ui.snap_grid) {
            x = std::round(x / ui.grid_step_m) * ui.grid_step_m;
            y = std::round(y / ui.grid_step_m) * ui.grid_step_m;
        }
        return {x, y};
    };

    // Grid lines every 20 mm
    for (int mm = -120; mm <= 120; mm += 20) {
        const float d = static_cast<float>(mm) * 0.001f;
        const ImU32 gcol = (mm == 0) ? IM_COL32(170, 185, 205, 255) : IM_COL32(228, 234, 244, 255);
        dl->AddLine(ImVec2(origin_px.x + d * px_per_m, p0.y + 4), ImVec2(origin_px.x + d * px_per_m, p1.y - 4), gcol);
        dl->AddLine(ImVec2(p0.x + 4, origin_px.y - d * px_per_m), ImVec2(p1.x - 4, origin_px.y - d * px_per_m), gcol);
    }

    // Render all entities
    for (int ei = 0; ei < static_cast<int>(sk.entities.size()); ++ei) {
        const auto &e = sk.entities[ei];
        const bool sel1 = (ei == ui.selected_entity_idx);
        const bool sel2 = (ei == ui.second_entity_idx);
        const ImU32 col = sel1 ? IM_COL32(220, 38, 38, 255)
                               : (sel2 ? IM_COL32(234, 88, 12, 255)
                                       : (e.construction ? IM_COL32(148, 163, 184, 255) : IM_COL32(29, 78, 216, 255)));
        const float thick = (sel1 || sel2) ? 2.6f : 1.8f;
        if (e.kind == FreeformEntityKind::Line) {
            const ImVec2 a = to_px(e.x0, e.y0), b = to_px(e.x1, e.y1);
            dl->AddLine(a, b, col, thick);
            dl->AddCircleFilled(a, 4.0f, col);
            dl->AddCircleFilled(b, 4.0f, col);
        } else if (e.kind == FreeformEntityKind::Circle) {
            const ImVec2 c = to_px(e.x0, e.y0);
            dl->AddCircle(c, std::max(3.0f, e.radius * px_per_m), col, 32, thick);
            dl->AddCircleFilled(c, 4.0f, col);
        } else if (e.kind == FreeformEntityKind::Arc) {
            const ImVec2 c = to_px(e.x0, e.y0);
            const float rad_px = std::max(3.0f, e.radius * px_per_m);
            const int segs = 20;
            for (int k = 0; k < segs; ++k) {
                const float a0 = (e.start_deg + (e.end_deg - e.start_deg) * k / segs) * kPiF / 180.0f;
                const float a1 = (e.start_deg + (e.end_deg - e.start_deg) * (k + 1) / segs) * kPiF / 180.0f;
                dl->AddLine(ImVec2(c.x + rad_px * std::cos(a0), c.y - rad_px * std::sin(a0)),
                            ImVec2(c.x + rad_px * std::cos(a1), c.y - rad_px * std::sin(a1)), col, thick);
            }
            dl->AddCircleFilled(c, 4.0f, col);
        } else if (e.kind == FreeformEntityKind::Spline && e.spline_pts.size() >= 2) {
            for (std::size_t k = 0; k + 1 < e.spline_pts.size(); ++k) {
                dl->AddLine(to_px(e.spline_pts[k][0], e.spline_pts[k][1]),
                            to_px(e.spline_pts[k + 1][0], e.spline_pts[k + 1][1]), col, thick);
            }
            if (e.closed && e.spline_pts.size() >= 3) {
                dl->AddLine(to_px(e.spline_pts.back()[0], e.spline_pts.back()[1]),
                            to_px(e.spline_pts.front()[0], e.spline_pts.front()[1]), col, thick);
            }
            for (const auto &sp : e.spline_pts) dl->AddCircleFilled(to_px(sp[0], sp[1]), 4.0f, col);
        }
    }

    // Mouse interaction inside sketch canvas
    ImGui::InvisibleButton("##freeform_sketch_canvas", size);
    if (ImGui::IsItemHovered()) {
        const ImVec2 mp = ImGui::GetIO().MousePos;
        const auto mpt = to_m(mp);
        if (ImGui::IsMouseClicked(ImGuiMouseButton_Left)) {
            if (ui.active_tool == SketchTool::SelectDrag) {
                int hit_e = -1, hit_pt = 0;
                float best_d = 12.0f;
                for (int ei = 0; ei < static_cast<int>(sk.entities.size()); ++ei) {
                    const auto &e = sk.entities[ei];
                    auto check_pt = [&](float pxm, float pym, int pt_id) {
                        const ImVec2 sp = to_px(pxm, pym);
                        const float d = std::hypot(mp.x - sp.x, mp.y - sp.y);
                        if (d < best_d) { best_d = d; hit_e = ei; hit_pt = pt_id; }
                    };
                    if (e.kind == FreeformEntityKind::Line) { check_pt(e.x0, e.y0, 0); check_pt(e.x1, e.y1, 1); }
                    else if (e.kind == FreeformEntityKind::Circle || e.kind == FreeformEntityKind::Arc) { check_pt(e.x0, e.y0, 0); }
                    else { for (int k = 0; k < static_cast<int>(e.spline_pts.size()); ++k) check_pt(e.spline_pts[k][0], e.spline_pts[k][1], k); }
                }
                if (hit_e >= 0) {
                    if (ImGui::GetIO().KeyShift) ui.second_entity_idx = hit_e;
                    else { ui.selected_entity_idx = hit_e; ui.drag_entity_idx = hit_e; ui.drag_pt_idx = hit_pt; on_push_undo(); }
                }
            } else if (ui.active_tool == SketchTool::DrawLine) {
                ui.pending_pts.push_back(mpt);
                if (ui.pending_pts.size() == 2) {
                    on_push_undo();
                    FreeformSketchEntity le;
                    le.id = make_next_id(sk, 'l'); le.kind = FreeformEntityKind::Line;
                    le.x0 = ui.pending_pts[0][0]; le.y0 = ui.pending_pts[0][1];
                    le.x1 = ui.pending_pts[1][0]; le.y1 = ui.pending_pts[1][1];
                    sk.entities.push_back(le);
                    ui.pending_pts.clear();
                    solve_sketch_constraints_cpp(sk);
                }
            } else if (ui.active_tool == SketchTool::DrawRect) {
                ui.pending_pts.push_back(mpt);
                if (ui.pending_pts.size() == 2) {
                    on_push_undo();
                    const float ax = ui.pending_pts[0][0], ay = ui.pending_pts[0][1], bx = mpt[0], by = mpt[1];
                    const std::string ids[4] = {make_next_id(sk, 'r'), make_next_id(sk, 's'), make_next_id(sk, 't'), make_next_id(sk, 'u')};
                    sk.entities.push_back({ids[0], FreeformEntityKind::Line, false, true, ax, ay, bx, ay});
                    sk.entities.push_back({ids[1], FreeformEntityKind::Line, false, true, bx, ay, bx, by});
                    sk.entities.push_back({ids[2], FreeformEntityKind::Line, false, true, bx, by, ax, by});
                    sk.entities.push_back({ids[3], FreeformEntityKind::Line, false, true, ax, by, ax, ay});
                    sk.constraints.push_back({FreeformConstraintKind::Horizontal, ids[0], "", 0, 0});
                    sk.constraints.push_back({FreeformConstraintKind::Perpendicular, ids[0], ids[1], 0, 0});
                    sk.constraints.push_back({FreeformConstraintKind::Coincident, ids[0], ids[1], 1, 0});
                    sk.constraints.push_back({FreeformConstraintKind::Coincident, ids[1], ids[2], 1, 0});
                    sk.constraints.push_back({FreeformConstraintKind::Coincident, ids[2], ids[3], 1, 0});
                    sk.constraints.push_back({FreeformConstraintKind::Coincident, ids[3], ids[0], 1, 0});
                    ui.pending_pts.clear();
                    solve_sketch_constraints_cpp(sk);
                }
            } else if (ui.active_tool == SketchTool::DrawCircle) {
                ui.pending_pts.push_back(mpt);
                if (ui.pending_pts.size() == 2) {
                    on_push_undo();
                    FreeformSketchEntity ce;
                    ce.id = make_next_id(sk, 'c'); ce.kind = FreeformEntityKind::Circle;
                    ce.x0 = ui.pending_pts[0][0]; ce.y0 = ui.pending_pts[0][1];
                    ce.radius = std::max(0.003f, std::hypot(mpt[0] - ce.x0, mpt[1] - ce.y0));
                    sk.entities.push_back(ce);
                    ui.pending_pts.clear();
                    solve_sketch_constraints_cpp(sk);
                }
            } else if (ui.active_tool == SketchTool::DrawArc) {
                ui.pending_pts.push_back(mpt);
                if (ui.pending_pts.size() == 3) {
                    on_push_undo();
                    FreeformSketchEntity ae;
                    ae.id = make_next_id(sk, 'a'); ae.kind = FreeformEntityKind::Arc;
                    ae.x0 = ui.pending_pts[0][0]; ae.y0 = ui.pending_pts[0][1];
                    ae.radius = std::max(0.005f, std::hypot(ui.pending_pts[1][0] - ae.x0, ui.pending_pts[1][1] - ae.y0));
                    ae.start_deg = std::atan2(ui.pending_pts[1][1] - ae.y0, ui.pending_pts[1][0] - ae.x0) * 180.0f / kPiF;
                    ae.end_deg = std::atan2(mpt[1] - ae.y0, mpt[0] - ae.x0) * 180.0f / kPiF;
                    sk.entities.push_back(ae);
                    ui.pending_pts.clear();
                    solve_sketch_constraints_cpp(sk);
                }
            } else if (ui.active_tool == SketchTool::DrawSpline) {
                ui.pending_pts.push_back(mpt);
            }
        }
        if (ImGui::IsMouseDragging(ImGuiMouseButton_Left) && ui.active_tool == SketchTool::SelectDrag && ui.drag_entity_idx >= 0 &&
            ui.drag_entity_idx < static_cast<int>(sk.entities.size())) {
            auto &e = sk.entities[ui.drag_entity_idx];
            if (e.kind == FreeformEntityKind::Line) {
                if (ui.drag_pt_idx == 1) { e.x1 = mpt[0]; e.y1 = mpt[1]; } else { e.x0 = mpt[0]; e.y0 = mpt[1]; }
            } else if (e.kind == FreeformEntityKind::Circle || e.kind == FreeformEntityKind::Arc) {
                e.x0 = mpt[0]; e.y0 = mpt[1];
            } else if (ui.drag_pt_idx >= 0 && ui.drag_pt_idx < static_cast<int>(e.spline_pts.size())) {
                e.spline_pts[ui.drag_pt_idx] = mpt;
            }
            solve_sketch_constraints_cpp(sk);
        }
    }
    if (ImGui::IsMouseReleased(ImGuiMouseButton_Left)) ui.drag_entity_idx = -1;
    if (ui.active_tool == SketchTool::DrawSpline && ui.pending_pts.size() >= 3 && ImGui::SmallButton("Finish Closed Spline")) {
        on_push_undo();
        FreeformSketchEntity se;
        se.id = make_next_id(sk, 'p'); se.kind = FreeformEntityKind::Spline; se.closed = true;
        se.spline_pts = ui.pending_pts;
        sk.entities.push_back(se);
        ui.pending_pts.clear();
        solve_sketch_constraints_cpp(sk);
    }

    // 4. Live DOF Status & Constraint Application Toolbar
    ImGui::TextColored(sk.dof == 0 && sk.converged ? ImVec4(0.10f, 0.58f, 0.25f, 1.0f) : ImVec4(0.80f, 0.45f, 0.08f, 1.0f),
                       "Constraints: %s | DOF: %d | Res: %.2e",
                       !sk.converged ? "Over/Failed" : (sk.dof == 0 ? "Fully Constrained" : "Under-Constrained"),
                       sk.dof, sk.max_residual);
    ImGui::SetNextItemWidth(90.0f);
    ImGui::InputFloat("Dim (mm)", &ui.dim_input_mm, 1.0f, 5.0f, "%.1f");
    ImGui::SameLine();
    auto add_c = [&](const char *lbl, FreeformConstraintKind ck, bool needs_two) {
        if (ImGui::SmallButton(lbl) && ui.selected_entity_idx >= 0 && ui.selected_entity_idx < static_cast<int>(sk.entities.size())) {
            if (!needs_two || (ui.second_entity_idx >= 0 && ui.second_entity_idx < static_cast<int>(sk.entities.size()))) {
                on_push_undo();
                FreeformSketchConstraint c;
                c.kind = ck;
                c.a = sk.entities[ui.selected_entity_idx].id;
                if (needs_two) c.b = sk.entities[ui.second_entity_idx].id;
                c.value = std::max(0.0005f, ui.dim_input_mm * 0.001f);
                c.target_x = sk.entities[ui.selected_entity_idx].x0;
                c.target_y = sk.entities[ui.selected_entity_idx].y0;
                sk.constraints.push_back(c);
                solve_sketch_constraints_cpp(sk);
            }
        }
    };
    add_c("H", FreeformConstraintKind::Horizontal, false); ImGui::SameLine();
    add_c("V", FreeformConstraintKind::Vertical, false); ImGui::SameLine();
    add_c("Len", FreeformConstraintKind::Length, false); ImGui::SameLine();
    add_c("Rad", FreeformConstraintKind::Radius, false); ImGui::SameLine();
    add_c("Fix", FreeformConstraintKind::Fixed, false); ImGui::SameLine();
    if (ImGui::SmallButton("Const") && ui.selected_entity_idx >= 0 && ui.selected_entity_idx < static_cast<int>(sk.entities.size())) {
        on_push_undo();
        sk.entities[ui.selected_entity_idx].construction = !sk.entities[ui.selected_entity_idx].construction;
    }
    add_c("Coinc", FreeformConstraintKind::Coincident, true); ImGui::SameLine();
    add_c("Perp", FreeformConstraintKind::Perpendicular, true); ImGui::SameLine();
    add_c("Par", FreeformConstraintKind::Parallel, true); ImGui::SameLine();
    add_c("Tan", FreeformConstraintKind::Tangent, true); ImGui::SameLine();
    add_c("Eq", FreeformConstraintKind::Equal, true); ImGui::SameLine();
    add_c("Dist", FreeformConstraintKind::Distance, true);

    ImGui::Separator();
    // 5. True B-Rep 3D Operations (Extrude Boss / Cut / Revolve / Loft / Fillet / Chamfer / Shell)
    ImGui::SetNextItemWidth(76.0f); ImGui::InputFloat("Depth(mm)", &ui.op_depth_mm, 2.0f, 10.0f, "%.1f"); ImGui::SameLine();
    ImGui::SetNextItemWidth(68.0f); ImGui::InputFloat("R/Th(mm)", &ui.op_radius_mm, 0.5f, 2.0f, "%.1f"); ImGui::SameLine();
    ImGui::Checkbox("Sym", &ui.op_symmetric);

    auto push_op = [&](FreeformOpKind op) {
        on_push_undo();
        part.freeform_mode = true;
        part.sketch_kind = SketchShapeKind::FreeformBrep;
        FreeformCadFeature f;
        f.op = op;
        f.depth_m = std::max(0.001f, ui.op_depth_mm * 0.001f);
        f.radius_m = std::max(0.0005f, ui.op_radius_mm * 0.001f);
        f.angle_deg = std::clamp(ui.op_angle_deg, 5.0f, 360.0f);
        f.loft_offset_m = std::max(0.005f, ui.op_loft_offset_mm * 0.001f);
        f.loft_scale = std::clamp(ui.op_loft_scale, 0.1f, 3.0f);
        f.symmetric = ui.op_symmetric;
        f.sketch = sk;
        f.sketch.workplane = part.active_workplane;
        if (op == FreeformOpKind::Shell && part.picked_face_id >= 0) {
            f.target_indices.push_back(part.picked_face_id);
        }
        part.freeform_features.push_back(std::move(f));
        on_rebuild_local();
        on_build_occt();
    };
    if (ImGui::Button("+ Extrude Boss")) push_op(FreeformOpKind::ExtrudeBoss); ImGui::SameLine();
    if (ImGui::Button("- Extrude Cut")) push_op(FreeformOpKind::ExtrudeCut); ImGui::SameLine();
    if (ImGui::Button("Revolve")) push_op(FreeformOpKind::Revolve); ImGui::SameLine();
    if (ImGui::Button("Loft")) push_op(FreeformOpKind::Loft);
    if (ImGui::Button("Fillet Edges")) push_op(FreeformOpKind::Fillet); ImGui::SameLine();
    if (ImGui::Button("Chamfer Edges")) push_op(FreeformOpKind::Chamfer); ImGui::SameLine();
    if (ImGui::Button("Shell Hollow")) push_op(FreeformOpKind::Shell); ImGui::SameLine();
    if (ImGui::Button("Rebuild OCCT B-Rep")) {
        part.freeform_mode = true;
        part.sketch_kind = SketchShapeKind::FreeformBrep;
        on_build_occt();
    }

    // 6. Ordered Feature Tree with Suppress / Delete
    ImGui::Separator();
    ImGui::Text("OCCT Feature History (%zu ops) - %s", part.freeform_features.size(), brep.status_summary.c_str());
    for (int fi = 0; fi < static_cast<int>(part.freeform_features.size()); ++fi) {
        auto &ft = part.freeform_features[fi];
        ImGui::PushID(fi);
        bool enabled = !ft.suppressed;
        if (ImGui::Checkbox("##act", &enabled)) {
            ft.suppressed = !enabled;
            on_build_occt();
        }
        ImGui::SameLine();
        ImGui::Text("%d. %s (%.1fmm)", fi + 1, op_label_str(ft.op),
                    (ft.op == FreeformOpKind::Fillet || ft.op == FreeformOpKind::Chamfer || ft.op == FreeformOpKind::Shell)
                        ? ft.radius_m * 1000.0f
                        : ft.depth_m * 1000.0f);
        ImGui::SameLine();
        if (ImGui::SmallButton("Del") && part.freeform_features.size() > 1) {
            on_push_undo();
            part.freeform_features.erase(part.freeform_features.begin() + fi);
            on_build_occt();
            ImGui::PopID();
            break;
        }
        ImGui::PopID();
    }

    ImGui::End();
}

} // namespace aerolab
