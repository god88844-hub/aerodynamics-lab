"""Multi-Body Mechanical Mates & Kinematic Solver (Rigid, Revolute, Prismatic, Cylindrical, Spherical, Gear, RackPinion, Planar)."""

from __future__ import annotations

import math
from typing import Any


def _norm3(v: list[float]) -> list[float]:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if n <= 1e-12:
        return [0.0, 0.0, 1.0]
    return [v[0] / n, v[1] / n, v[2] / n]


def _quat_mul(a: list[float], b: list[float]) -> list[float]:
    q = [
        a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
        a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
        a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
        a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0],
    ]
    n = math.sqrt(sum(c * c for c in q))
    return [c / n for c in q] if n > 1e-12 else [1.0, 0.0, 0.0, 0.0]


def _quat_axis_deg(axis: list[float], deg: float) -> list[float]:
    ax = _norm3(axis)
    h = 0.5 * math.radians(deg)
    s = math.sin(h)
    return [math.cos(h), ax[0] * s, ax[1] * s, ax[2] * s]


def _quat_rot(q: list[float], v: list[float]) -> list[float]:
    w, x, y, z = q
    tx = 2.0 * (y * v[2] - z * v[1])
    ty = 2.0 * (z * v[0] - x * v[2])
    tz = 2.0 * (x * v[1] - y * v[0])
    return [
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    ]


_DOF_MAP = {
    "rigid": 0,
    "revolute": 1,
    "prismatic": 1,
    "cylindrical": 2,
    "spherical": 3,
    "gear": 0,
    "rack_pinion": 0,
    "planar": 3,
}


def solve_mechanical_mates(spec: dict[str, Any]) -> dict[str, Any]:
    """Solve multi-body mate kinematics, gear/rack ratios, joint stops, reactions, and interference."""
    bodies = spec.get("bodies", [])
    mates = spec.get("mates", [])
    animate = bool(spec.get("animate", False))
    anim_time_s = float(spec.get("anim_time_s", 0.0))
    load_scale = max(0.2, float(spec.get("external_load_scale", 1.0)))

    poses: dict[str, dict[str, Any]] = {}
    body_map: dict[str, dict[str, Any]] = {}
    for b in bodies:
        bid = str(b["id"])
        body_map[bid] = b
        poses[bid] = {
            "body_id": bid,
            "world_pos_m": [0.0, 0.0, 0.0],
            "quat_wxyz": [1.0, 0.0, 0.0, 0.0],
            "visited": bool(b.get("grounded", False)),
        }

    eff_drive: dict[str, float] = {}
    eff_sec: dict[str, float] = {}
    violated: dict[str, bool] = {}

    for m in mates:
        if m.get("suppressed"):
            continue
        mid = str(m["id"])
        kind = str(m.get("kind", "revolute")).lower()
        d = float(m.get("drive_value", 0.0))
        d2 = float(m.get("secondary_value", 0.0))
        lmin = float(m.get("limit_min", -180.0))
        lmax = float(m.get("limit_max", 180.0))
        if animate and kind in {"revolute", "prismatic", "cylindrical", "spherical", "planar"}:
            span = lmax - lmin
            s_wave = 0.5 - 0.5 * math.cos(anim_time_s * 2.2)
            if kind in {"revolute", "spherical"} and 1e-3 < span < 350.0:
                d = lmin + span * s_wave
            elif kind in {"revolute", "spherical"}:
                d += anim_time_s * 180.0
            else:
                if span > 1e-4:
                    d = lmin + span * s_wave
                if kind == "cylindrical":
                    d2 += anim_time_s * 240.0
        lim_bad = False
        if m.get("enforce_limits", True) and kind in {"revolute", "prismatic", "cylindrical", "spherical", "planar"}:
            if (lmax - lmin) < 359.0 or kind == "prismatic":
                if d < lmin - 1e-6 or d > lmax + 1e-6:
                    lim_bad = True
                d = max(lmin, min(lmax, d))
        eff_drive[mid] = d
        eff_sec[mid] = d2
        violated[mid] = lim_bad

    for _ in range(4):
        for m in mates:
            if m.get("suppressed"):
                continue
            mid = str(m["id"])
            kind = str(m.get("kind", "revolute")).lower()
            if kind == "gear":
                pdeg = eff_drive.get(str(m.get("coupled_mate_id", "")), 0.0)
                eff_drive[mid] = float(m.get("gear_ratio", 1.0)) * pdeg + float(m.get("drive_value", 0.0))
            elif kind == "rack_pinion":
                pdeg = eff_drive.get(str(m.get("coupled_mate_id", "")), 0.0)
                eff_drive[mid] = float(m.get("pitch_radius_m", 0.02)) * math.radians(pdeg) + float(m.get("drive_value", 0.0))

    for _ in range(len(bodies) + 2):
        progressed = False
        for m in mates:
            if m.get("suppressed"):
                continue
            p_id = str(m.get("parent_body", ""))
            c_id = str(m.get("child_body", ""))
            if p_id not in poses or c_id not in poses:
                continue
            pp, cp = poses[p_id], poses[c_id]
            if not pp["visited"] or cp["visited"]:
                continue
            mid = str(m["id"])
            kind = str(m.get("kind", "revolute")).lower()
            ax = _norm3([float(x) for x in m.get("axis_local", [0.0, 0.0, 1.0])])
            ap = _quat_rot(pp["quat_wxyz"], [float(x) for x in m.get("anchor_parent_m", [0.0, 0.0, 0.0])])
            wa = [pp["world_pos_m"][k] + ap[k] for k in range(3)]
            q_rel = [1.0, 0.0, 0.0, 0.0]
            slide = [0.0, 0.0, 0.0]
            d = eff_drive.get(mid, 0.0)
            d2 = eff_sec.get(mid, 0.0)
            if kind in {"revolute", "gear"}:
                q_rel = _quat_axis_deg(ax, d)
            elif kind in {"prismatic", "rack_pinion"}:
                slide = [ax[k] * d for k in range(3)]
            elif kind == "cylindrical":
                q_rel = _quat_axis_deg(ax, d2)
                slide = [ax[k] * d for k in range(3)]
            elif kind == "spherical":
                q_rel = _quat_mul(_quat_axis_deg([0.0, 1.0, 0.0], d), _quat_axis_deg([1.0, 0.0, 0.0], d2))
            elif kind == "planar":
                slide = [d, d2, 0.0]

            q_child = _quat_mul(pp["quat_wxyz"], q_rel)
            sw = _quat_rot(pp["quat_wxyz"], slide)
            ac = _quat_rot(q_child, [float(x) for x in m.get("anchor_child_m", [0.0, 0.0, 0.0])])
            cp["quat_wxyz"] = [round(v, 6) for v in q_child]
            cp["world_pos_m"] = [round(wa[k] + sw[k] - ac[k], 6) for k in range(3)]
            cp["visited"] = True
            progressed = True
        if not progressed:
            break

    adj = set()
    mate_states: list[dict[str, Any]] = []
    free_dof = 0
    for m in mates:
        if m.get("suppressed"):
            continue
        mid = str(m["id"])
        kind = str(m.get("kind", "revolute")).lower()
        p_id = str(m.get("parent_body", ""))
        c_id = str(m.get("child_body", ""))
        adj.add((p_id, c_id))
        adj.add((c_id, p_id))
        free_dof += _DOF_MAP.get(kind, 0)
        cmass = float(body_map.get(c_id, {}).get("mass_kg", 0.25))
        cap = float(m.get("load_capacity_n", 475.0))
        rforce = max(0.2, cmass * 9.80665 * load_scale * (1.35 if kind == "gear" else 1.0))
        mate_states.append({
            "mate_id": mid,
            "kind": kind,
            "effective_drive": round(eff_drive.get(mid, 0.0), 6),
            "effective_secondary": round(eff_sec.get(mid, 0.0), 6),
            "limit_violated": bool(violated.get(mid, False)),
            "reaction_force_n": round(rforce, 3),
            "joint_fos": round(cap / max(0.1, rforce), 2),
        })

    interference_pairs: list[list[str]] = []
    min_clr = 999.0
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            bi, bj = bodies[i], bodies[j]
            if not bi.get("collision_enabled", True) or not bj.get("collision_enabled", True):
                continue
            if (bi["id"], bj["id"]) in adj:
                continue
            pi, pj = poses[bi["id"]]["world_pos_m"], poses[bj["id"]]["world_pos_m"]
            ei = bi.get("half_extents_m", [0.05, 0.05, 0.02])
            ej = bj.get("half_extents_m", [0.05, 0.05, 0.02])
            sep = max(abs(pi[k] - pj[k]) - (ei[k] + ej[k]) for k in range(3))
            min_clr = min(min_clr, sep * 1000.0)
            if sep < -0.002:
                interference_pairs.append([bi["id"], bj["id"]])

    return {
        "schema_version": "1.0",
        "total_free_dof": free_dof,
        "active_mates": len(mate_states),
        "any_limit_violated": any(violated.values()),
        "any_interference": len(interference_pairs) > 0,
        "min_clearance_mm": round(min_clr, 3),
        "interference_pairs": interference_pairs,
        "body_poses": list(poses.values()),
        "mate_states": mate_states,
    }
