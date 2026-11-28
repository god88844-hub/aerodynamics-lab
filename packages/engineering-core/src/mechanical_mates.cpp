#include "lab/mechanical_mates.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <numbers>

namespace lab {
namespace {

constexpr double kPi = std::numbers::pi_v<double>;
constexpr double kGravity = 9.80665;

std::array<double, 3> norm3(std::array<double, 3> v) {
    const double n = std::sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    if (n <= 1e-12) return {0.0, 0.0, 1.0};
    return {v[0] / n, v[1] / n, v[2] / n};
}

std::array<double, 4> quat_norm(std::array<double, 4> q) {
    const double n = std::sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
    if (n <= 1e-12) return {1.0, 0.0, 0.0, 0.0};
    return {q[0] / n, q[1] / n, q[2] / n, q[3] / n};
}

std::array<double, 4> quat_mul(const std::array<double, 4> &a, const std::array<double, 4> &b) {
    return quat_norm({
        a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
        a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
        a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
        a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
    });
}

std::array<double, 4> quat_axis_deg(std::array<double, 3> axis, double angle_deg) {
    axis = norm3(axis);
    const double half = 0.5 * angle_deg * (kPi / 180.0);
    const double s = std::sin(half);
    return quat_norm({std::cos(half), axis[0] * s, axis[1] * s, axis[2] * s});
}

std::array<double, 3> quat_rot(const std::array<double, 4> &q, const std::array<double, 3> &v) {
    const double w = q[0], x = q[1], y = q[2], z = q[3];
    const double tx = 2.0 * (y * v[2] - z * v[1]);
    const double ty = 2.0 * (z * v[0] - x * v[2]);
    const double tz = 2.0 * (x * v[1] - y * v[0]);
    return {
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    };
}

int free_dof_for_mate(MateKind kind) {
    switch (kind) {
    case MateKind::Rigid: return 0;
    case MateKind::Revolute: return 1;
    case MateKind::Prismatic: return 1;
    case MateKind::Cylindrical: return 2;
    case MateKind::Spherical: return 3;
    case MateKind::Gear: return 0;       // Constrained to driver mate
    case MateKind::RackPinion: return 0; // Constrained to driver mate
    case MateKind::Planar: return 3;     // tx, ty, rot_z
    }
    return 0;
}

MechanicalMatesSolution run_fk_pass(
    const std::vector<RigidBodyNode> &bodies,
    const std::vector<MechanicalMateSpec> &mates,
    bool animate,
    double anim_time_s,
    double external_load_scale,
    const std::string &override_mate_id,
    double override_drive) {
    MechanicalMatesSolution sol;
    std::map<std::string, std::size_t> body_idx;
    sol.body_poses.resize(bodies.size());
    for (std::size_t i = 0; i < bodies.size(); ++i) {
        body_idx[bodies[i].id] = i;
        sol.body_poses[i].body_id = bodies[i].id;
        sol.body_poses[i].visited = bodies[i].grounded;
    }

    // Track primary solved scalar per mate id so Gear/RackPinion can couple accurately
    std::map<std::string, double> mate_scalar;
    std::vector<double> eff_drive(mates.size(), 0.0);
    std::vector<double> eff_sec(mates.size(), 0.0);
    std::vector<bool> violated(mates.size(), false);

    // First pass: resolve primary drivers (non-coupled mates)
    for (std::size_t mi = 0; mi < mates.size(); ++mi) {
        const auto &m = mates[mi];
        if (m.suppressed) continue;
        double d = (!override_mate_id.empty() && m.id == override_mate_id) ? override_drive : m.drive_value;
        double d2 = m.secondary_value;

        if (animate && m.kind != MateKind::Rigid && m.kind != MateKind::Gear && m.kind != MateKind::RackPinion) {
            if (m.kind == MateKind::Revolute || m.kind == MateKind::Spherical) {
                const double span = m.limit_max - m.limit_min;
                if (span > 1e-3 && span < 350.0) {
                    const double s_wave = 0.5 - 0.5 * std::cos(anim_time_s * 2.2);
                    d = m.limit_min + span * s_wave;
                } else {
                    d = m.drive_value + anim_time_s * 180.0;
                }
            } else if (m.kind == MateKind::Prismatic || m.kind == MateKind::Cylindrical || m.kind == MateKind::Planar) {
                const double span = m.limit_max - m.limit_min;
                if (span > 1e-4) {
                    const double s_wave = 0.5 - 0.5 * std::cos(anim_time_s * 2.2);
                    d = m.limit_min + span * s_wave;
                }
                if (m.kind == MateKind::Cylindrical) {
                    d2 = m.secondary_value + anim_time_s * 240.0;
                }
            }
        }

        if (m.enforce_limits && m.kind != MateKind::Gear && m.kind != MateKind::RackPinion && m.kind != MateKind::Rigid) {
            const double span = m.limit_max - m.limit_min;
            if (span < 359.0 || m.kind == MateKind::Prismatic) {
                if (d < m.limit_min - 1e-6 || d > m.limit_max + 1e-6) {
                    violated[mi] = true;
                }
                d = std::clamp(d, m.limit_min, m.limit_max);
            }
        }
        eff_drive[mi] = d;
        eff_sec[mi] = d2;
        mate_scalar[m.id] = d;
    }

    // Propagate Gear and RackPinion couplings (multi-pass for chained couplings)
    for (int pass = 0; pass < 4; ++pass) {
        for (std::size_t mi = 0; mi < mates.size(); ++mi) {
            const auto &m = mates[mi];
            if (m.suppressed) continue;
            if (m.kind == MateKind::Gear) {
                const auto it = mate_scalar.find(m.coupled_mate_id);
                const double parent_deg = (it != mate_scalar.end()) ? it->second : 0.0;
                double d = m.gear_ratio * parent_deg + m.drive_value;
                if (m.enforce_limits && (m.limit_max - m.limit_min) < 359.0) {
                    if (d < m.limit_min - 1e-6 || d > m.limit_max + 1e-6) violated[mi] = true;
                    d = std::clamp(d, m.limit_min, m.limit_max);
                }
                eff_drive[mi] = d;
                mate_scalar[m.id] = d;
            } else if (m.kind == MateKind::RackPinion) {
                const auto it = mate_scalar.find(m.coupled_mate_id);
                const double parent_deg = (it != mate_scalar.end()) ? it->second : 0.0;
                const double rad = parent_deg * (kPi / 180.0);
                double slide_m = m.pitch_radius_m * rad + m.drive_value;
                if (m.enforce_limits && m.limit_max > m.limit_min) {
                    if (slide_m < m.limit_min - 1e-6 || slide_m > m.limit_max + 1e-6) violated[mi] = true;
                    slide_m = std::clamp(slide_m, m.limit_min, m.limit_max);
                }
                eff_drive[mi] = slide_m;
                mate_scalar[m.id] = slide_m;
            }
        }
    }

    // Topological SE(3) propagation across kinematic tree
    for (std::size_t pass = 0; pass < bodies.size() + 2; ++pass) {
        bool progressed = false;
        for (std::size_t mi = 0; mi < mates.size(); ++mi) {
            const auto &m = mates[mi];
            if (m.suppressed) continue;
            const auto itp = body_idx.find(m.parent_body);
            const auto itc = body_idx.find(m.child_body);
            if (itp == body_idx.end() || itc == body_idx.end()) continue;
            auto &parent_pose = sol.body_poses[itp->second];
            auto &child_pose = sol.body_poses[itc->second];
            if (!parent_pose.visited || child_pose.visited) continue;

            const std::array<double, 3> axis_n = norm3(m.axis_local);
            const std::array<double, 3> world_anchor_p = {
                parent_pose.world_pos_m[0] + quat_rot(parent_pose.quat_wxyz, m.anchor_parent_m)[0],
                parent_pose.world_pos_m[1] + quat_rot(parent_pose.quat_wxyz, m.anchor_parent_m)[1],
                parent_pose.world_pos_m[2] + quat_rot(parent_pose.quat_wxyz, m.anchor_parent_m)[2],
            };

            std::array<double, 4> q_rel{1.0, 0.0, 0.0, 0.0};
            std::array<double, 3> slide_local{0.0, 0.0, 0.0};

            if (m.kind == MateKind::Revolute || m.kind == MateKind::Gear) {
                q_rel = quat_axis_deg(axis_n, eff_drive[mi]);
            } else if (m.kind == MateKind::Prismatic || m.kind == MateKind::RackPinion) {
                slide_local = {axis_n[0] * eff_drive[mi], axis_n[1] * eff_drive[mi], axis_n[2] * eff_drive[mi]};
            } else if (m.kind == MateKind::Cylindrical) {
                q_rel = quat_axis_deg(axis_n, eff_sec[mi]);
                slide_local = {axis_n[0] * eff_drive[mi], axis_n[1] * eff_drive[mi], axis_n[2] * eff_drive[mi]};
            } else if (m.kind == MateKind::Spherical) {
                const auto q1 = quat_axis_deg({0.0, 1.0, 0.0}, eff_drive[mi]);
                const auto q2 = quat_axis_deg({1.0, 0.0, 0.0}, eff_sec[mi]);
                q_rel = quat_mul(q1, q2);
            } else if (m.kind == MateKind::Planar) {
                slide_local = {eff_drive[mi], eff_sec[mi], 0.0};
            }

            const std::array<double, 4> q_child = quat_mul(parent_pose.quat_wxyz, q_rel);
            const std::array<double, 3> slide_world = quat_rot(parent_pose.quat_wxyz, slide_local);
            const std::array<double, 3> child_anchor_world = quat_rot(q_child, m.anchor_child_m);
            child_pose.quat_wxyz = q_child;
            child_pose.world_pos_m = {
                world_anchor_p[0] + slide_world[0] - child_anchor_world[0],
                world_anchor_p[1] + slide_world[1] - child_anchor_world[1],
                world_anchor_p[2] + slide_world[2] - child_anchor_world[2],
            };
            child_pose.visited = true;
            progressed = true;
        }
        if (!progressed) break;
    }

    // Build mate states, DOF count, reaction forces & bearing/fastener safety
    for (std::size_t mi = 0; mi < mates.size(); ++mi) {
        const auto &m = mates[mi];
        if (m.suppressed) continue;
        ++sol.active_mates;
        sol.total_free_dof += free_dof_for_mate(m.kind);
        if (violated[mi]) sol.any_limit_violated = true;

        SolvedMateState st;
        st.mate_id = m.id;
        st.kind = m.kind;
        st.effective_drive = eff_drive[mi];
        st.effective_secondary = eff_sec[mi];
        st.limit_violated = violated[mi];
        st.free_dof = free_dof_for_mate(m.kind);

        double child_mass = 0.25;
        const auto itc = body_idx.find(m.child_body);
        if (itc != body_idx.end()) {
            child_mass = bodies[itc->second].mass_kg;
        }
        const auto itp = body_idx.find(m.parent_body);
        if (itp != body_idx.end()) {
            const auto &pp = sol.body_poses[itp->second];
            const auto wa = quat_rot(pp.quat_wxyz, m.anchor_parent_m);
            st.joint_world_pos_m = {pp.world_pos_m[0] + wa[0], pp.world_pos_m[1] + wa[1], pp.world_pos_m[2] + wa[2]};
            st.joint_world_axis = norm3(quat_rot(pp.quat_wxyz, m.axis_local));
        }

        const double base_load_n = std::max(0.2, child_mass * kGravity * std::max(0.5, external_load_scale));
        const double lever = std::sqrt(m.anchor_child_m[0] * m.anchor_child_m[0] +
                                       m.anchor_child_m[1] * m.anchor_child_m[1] +
                                       m.anchor_child_m[2] * m.anchor_child_m[2]);
        st.reaction_force_n = base_load_n * (m.kind == MateKind::Gear ? 1.35 : 1.0);
        st.reaction_torque_nm = base_load_n * std::max(0.03, lever);
        st.joint_fos = std::max(0.05, m.load_capacity_n / std::max(0.1, st.reaction_force_n));
        sol.mate_states.push_back(std::move(st));
    }

    // Multi-body AABB separation / interference scan across non-mated body pairs
    std::map<std::pair<std::string, std::string>, bool> adj;
    for (const auto &m : mates) {
        if (m.suppressed) continue;
        adj[{m.parent_body, m.child_body}] = true;
        adj[{m.child_body, m.parent_body}] = true;
    }
    for (std::size_t i = 0; i < bodies.size(); ++i) {
        if (!bodies[i].collision_enabled) continue;
        for (std::size_t j = i + 1; j < bodies.size(); ++j) {
            if (!bodies[j].collision_enabled) continue;
            if (adj.contains({bodies[i].id, bodies[j].id})) continue;
            const auto &pi = sol.body_poses[i].world_pos_m;
            const auto &pj = sol.body_poses[j].world_pos_m;
            const auto &ei = bodies[i].half_extents_m;
            const auto &ej = bodies[j].half_extents_m;
            const double gx = std::abs(pi[0] - pj[0]) - (ei[0] + ej[0]);
            const double gy = std::abs(pi[1] - pj[1]) - (ei[1] + ej[1]);
            const double gz = std::abs(pi[2] - pj[2]) - (ei[2] + ej[2]);
            const double max_sep = std::max({gx, gy, gz});
            sol.min_clearance_mm = std::min(sol.min_clearance_mm, max_sep * 1000.0);
            if (max_sep < -0.002) { // > 2 mm overlap
                sol.any_interference = true;
                sol.interference_pairs.emplace_back(bodies[i].id, bodies[j].id);
            }
        }
    }

    sol.valid = true;
    sol.summary = "Mates: " + std::to_string(sol.active_mates) + " | Free DoF: " + std::to_string(sol.total_free_dof) +
                  (sol.any_limit_violated ? " | LIMIT BREACH" : " | Limits OK") +
                  (sol.any_interference ? " | INTERFERENCE" : "");
    return sol;
}

} // namespace

const char *mate_kind_name(MateKind kind) {
    switch (kind) {
    case MateKind::Rigid: return "Rigid";
    case MateKind::Revolute: return "Revolute";
    case MateKind::Prismatic: return "Prismatic";
    case MateKind::Cylindrical: return "Cylindrical";
    case MateKind::Spherical: return "Spherical";
    case MateKind::Gear: return "Gear";
    case MateKind::RackPinion: return "Rack & Pinion";
    case MateKind::Planar: return "Planar";
    }
    return "Rigid";
}

MechanicalMatesSolution solve_mechanical_mates(
    const std::vector<RigidBodyNode> &bodies,
    const std::vector<MechanicalMateSpec> &mates,
    bool animate,
    double anim_time_s,
    double external_load_scale,
    const ClosedLoopTarget *loop_closure) {
    std::string override_id;
    double override_val = 0.0;
    double loop_err_mm = 0.0;

    if (loop_closure && loop_closure->active && !loop_closure->driver_mate_id.empty()) {
        // Closed-loop 1D Gauss-Newton refinement for 4-bar / pushrod closure
        for (const auto &m : mates) {
            if (m.id == loop_closure->driver_mate_id) {
                override_id = m.id;
                override_val = m.drive_value;
                break;
            }
        }
        auto eval_err = [&](double d_val) -> double {
            const auto fk = run_fk_pass(bodies, mates, false, 0.0, external_load_scale, override_id, d_val);
            for (const auto &bp : fk.body_poses) {
                if (bp.body_id == loop_closure->tip_body_id) {
                    const auto tip_off = quat_rot(bp.quat_wxyz, loop_closure->tip_local_offset_m);
                    const double dx = (bp.world_pos_m[0] + tip_off[0]) - loop_closure->target_world_m[0];
                    const double dy = (bp.world_pos_m[1] + tip_off[1]) - loop_closure->target_world_m[1];
                    const double dz = (bp.world_pos_m[2] + tip_off[2]) - loop_closure->target_world_m[2];
                    return std::sqrt(dx * dx + dy * dy + dz * dz);
                }
            }
            return 1e6;
        };
        if (!override_id.empty()) {
            double x = override_val;
            for (int iter = 0; iter < 18; ++iter) {
                const double e0 = eval_err(x);
                if (e0 < 1e-5) break;
                const double step = 0.25;
                const double ep = eval_err(x + step);
                const double em = eval_err(x - step);
                double best_x = x;
                double best_e = e0;
                // Coarse-to-fine coordinate &secant step
                const double g = (ep - em) / (2.0 * step);
                if (std::abs(g) > 1e-7) {
                    const double cand = std::clamp(x - std::clamp(e0 / g, -15.0, 15.0), -180.0, 180.0);
                    const double ec = eval_err(cand);
                    if (ec < best_e) { best_e = ec; best_x = cand; }
                }
                for (double delta : {-4.0, -1.0, -0.25, 0.25, 1.0, 4.0}) {
                    const double ec = eval_err(x + delta);
                    if (ec < best_e) { best_e = ec; best_x = x + delta; }
                }
                x = best_x;
                if (std::abs(e0 - best_e) < 1e-6) break;
            }
            override_val = x;
            loop_err_mm = eval_err(override_val) * 1000.0;
        }
    }

    auto out = run_fk_pass(bodies, mates, animate && override_id.empty(), anim_time_s,
                           external_load_scale, override_id, override_val);
    out.max_loop_error_mm = loop_err_mm;
    return out;
}

} // namespace lab
