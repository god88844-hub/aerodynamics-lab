"""Freeform 2D constrained sketch solver & Open CASCADE B-rep feature engine (boss, cut, revolve, loft, fillet, chamfer, shell)."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

import ezdxf
import numpy as np


def _norm3(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise ValueError("Zero-length 3D axis vector")
    return v / n


def normalize_workplane(wp: dict[str, Any] | None) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return orthonormal (origin_m, u_axis, v_axis, normal) frame in right-handed SI meters."""
    if not wp:
        return (
            np.array([0.0, 0.0, 0.0], dtype=float),
            np.array([1.0, 0.0, 0.0], dtype=float),
            np.array([0.0, 1.0, 0.0], dtype=float),
            np.array([0.0, 0.0, 1.0], dtype=float),
        )
    preset = str(wp.get("preset", "")).upper()
    origin = np.array(wp.get("origin_m", [0.0, 0.0, 0.0]), dtype=float)
    if preset == "XZ":
        return origin, np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0]), np.array([0.0, -1.0, 0.0])
    if preset == "YZ":
        return origin, np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])
    n = _norm3(np.array(wp.get("normal", [0.0, 0.0, 1.0]), dtype=float))
    if "u_axis" in wp:
        u = np.array(wp["u_axis"], dtype=float)
        u = u - float(np.dot(u, n)) * n
        u = _norm3(u) if np.linalg.norm(u) > 1e-8 else _norm3(np.cross(np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0]), n))
    else:
        ref = np.array([0.0, 0.0, 1.0]) if abs(n[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = _norm3(np.cross(ref, n))
    v = _norm3(np.cross(n, u))
    return origin, u, v, n


def expand_entities_with_primitives(raw_entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand high-level helpers (e.g., rectangle) into canonical line/arc/circle/spline entities."""
    out: list[dict[str, Any]] = []
    for idx, ent in enumerate(raw_entities):
        kind = str(ent.get("kind", "line")).lower()
        eid = str(ent.get("id", f"e{idx}"))
        cons = bool(ent.get("construction", False))
        if kind == "rect":
            cx, cy = [float(x) for x in ent.get("center", [0.0, 0.0])]
            w = float(ent.get("width_m", 0.06))
            h = float(ent.get("height_m", 0.04))
            hw, hh = 0.5 * w, 0.5 * h
            pts = [[cx - hw, cy - hh], [cx + hw, cy - hh], [cx + hw, cy + hh], [cx - hw, cy + hh]]
            for k in range(4):
                out.append({"id": f"{eid}_{k}", "kind": "line", "p0": pts[k], "p1": pts[(k + 1) % 4], "construction": cons})
        elif kind == "line":
            out.append({
                "id": eid,
                "kind": "line",
                "p0": [float(ent["p0"][0]), float(ent["p0"][1])],
                "p1": [float(ent["p1"][0]), float(ent["p1"][1])],
                "construction": cons,
            })
        elif kind == "circle":
            out.append({
                "id": eid,
                "kind": "circle",
                "center": [float(ent["center"][0]), float(ent["center"][1])],
                "radius": float(ent["radius"]),
                "construction": cons,
            })
        elif kind == "arc":
            out.append({
                "id": eid,
                "kind": "arc",
                "center": [float(ent["center"][0]), float(ent["center"][1])],
                "radius": float(ent["radius"]),
                "start_deg": float(ent.get("start_deg", 0.0)),
                "end_deg": float(ent.get("end_deg", 180.0)),
                "construction": cons,
            })
        elif kind == "spline":
            pts = [[float(p[0]), float(p[1])] for p in ent.get("points", [])]
            if len(pts) < 3:
                raise ValueError(f"Spline {eid!r} requires at least 3 control points")
            out.append({"id": eid, "kind": "spline", "points": pts, "closed": bool(ent.get("closed", True)), "construction": cons})
        else:
            raise ValueError(f"Unsupported sketch entity kind: {kind!r}")
    return out


def solve_freeform_sketch(sketch: dict[str, Any]) -> dict[str, Any]:
    """Solve 2D geometric & dimensional constraints using damped Levenberg-Marquardt."""
    entities = expand_entities_with_primitives(list(sketch.get("entities", [])))
    constraints = list(sketch.get("constraints", []))
    by_id = {e["id"]: e for e in entities}

    var_slices: dict[str, tuple[int, int]] = {}
    q0: list[float] = []
    for e in entities:
        start = len(q0)
        k = e["kind"]
        if k == "line":
            q0.extend([e["p0"][0], e["p0"][1], e["p1"][0], e["p1"][1]])
        elif k == "circle":
            q0.extend([e["center"][0], e["center"][1], max(1e-4, e["radius"])])
        elif k == "arc":
            q0.extend([e["center"][0], e["center"][1], max(1e-4, e["radius"]), e["start_deg"], e["end_deg"]])
        elif k == "spline":
            for pt in e["points"]:
                q0.extend([pt[0], pt[1]])
        var_slices[e["id"]] = (start, len(q0))

    q = np.array(q0, dtype=float)
    n_vars = len(q)

    def _pt(qvec: np.ndarray, eid: str, pt_idx: int) -> tuple[float, float]:
        ent = by_id[eid]
        s, _ = var_slices[eid]
        k = ent["kind"]
        if k == "line":
            return (float(qvec[s + 2]), float(qvec[s + 3])) if pt_idx == 1 else (float(qvec[s]), float(qvec[s + 1]))
        if k == "circle":
            return (float(qvec[s]), float(qvec[s + 1]))
        if k == "arc":
            cx, cy, r, a0, a1 = qvec[s : s + 5]
            if pt_idx == 0:
                return (float(cx), float(cy))
            ang = math.radians(float(a0 if pt_idx == 1 else a1))
            return (float(cx + r * math.cos(ang)), float(cy + r * math.sin(ang)))
        pts_start = s
        npts = len(ent["points"])
        idx = max(0, min(npts - 1, pt_idx))
        return (float(qvec[pts_start + 2 * idx]), float(qvec[pts_start + 2 * idx + 1]))

    def _line_vec(qvec: np.ndarray, eid: str) -> tuple[float, float, float]:
        s, _ = var_slices[eid]
        dx = float(qvec[s + 2] - qvec[s])
        dy = float(qvec[s + 3] - qvec[s + 1])
        return dx, dy, math.hypot(dx, dy)

    def _residuals(qvec: np.ndarray) -> np.ndarray:
        if not constraints:
            return np.zeros(0, dtype=float)
        res: list[float] = []
        for c in constraints:
            ck = str(c["kind"]).lower()
            ea = str(c["a"])
            eb = str(c["b"]) if c.get("b") is not None else ""
            pa = int(c.get("pt_a", 0))
            pb = int(c.get("pt_b", 0))
            if ea not in by_id:
                raise ValueError(f"Constraint references unknown entity {ea!r}")
            if eb and eb not in by_id:
                raise ValueError(f"Constraint references unknown entity {eb!r}")
            sa, _ = var_slices[ea]
            if ck == "horizontal":
                res.append(float(qvec[sa + 3] - qvec[sa + 1]))
            elif ck == "vertical":
                res.append(float(qvec[sa + 2] - qvec[sa]))
            elif ck == "length":
                _, _, L = _line_vec(qvec, ea)
                res.append(L - float(c["value"]))
            elif ck == "radius":
                res.append(float(qvec[sa + 2]) - float(c["value"]))
            elif ck == "fixed":
                tx, ty = [float(v) for v in c["target_xy"]]
                px, py = _pt(qvec, ea, pa)
                res.extend([px - tx, py - ty])
            elif ck == "coincident":
                ax, ay = _pt(qvec, ea, pa)
                bx, by = _pt(qvec, eb, pb)
                res.extend([ax - bx, ay - by])
            elif ck == "distance":
                ax, ay = _pt(qvec, ea, pa)
                bx, by = _pt(qvec, eb, pb)
                res.append(math.hypot(bx - ax, by - ay) - float(c["value"]))
            elif ck == "perpendicular":
                dxa, dya, la = _line_vec(qvec, ea)
                dxb, dyb, lb = _line_vec(qvec, eb)
                res.append((dxa * dxb + dya * dyb) / max(la * lb, 1e-9))
            elif ck == "parallel":
                dxa, dya, la = _line_vec(qvec, ea)
                dxb, dyb, lb = _line_vec(qvec, eb)
                res.append((dxa * dyb - dya * dxb) / max(la * lb, 1e-9))
            elif ck == "equal":
                ka, kb = by_id[ea]["kind"], by_id[eb]["kind"]
                if ka == "line" and kb == "line":
                    _, _, la = _line_vec(qvec, ea)
                    _, _, lb = _line_vec(qvec, eb)
                    res.append(la - lb)
                elif ka in {"circle", "arc"} and kb in {"circle", "arc"}:
                    sb, _ = var_slices[eb]
                    res.append(float(qvec[sa + 2] - qvec[sb + 2]))
                else:
                    raise ValueError("Equal constraint requires compatible entity types")
            elif ck == "tangent":
                if by_id[ea]["kind"] == "line" and by_id[eb]["kind"] in {"circle", "arc"}:
                    line_id, circ_id = ea, eb
                elif by_id[eb]["kind"] == "line" and by_id[ea]["kind"] in {"circle", "arc"}:
                    line_id, circ_id = eb, ea
                else:
                    raise ValueError("Tangent constraint connects a line and a circle/arc")
                sl, _ = var_slices[line_id]
                sc, _ = var_slices[circ_id]
                x0, y0, x1, y1 = qvec[sl : sl + 4]
                cx, cy, r = qvec[sc : sc + 3]
                seg = max(1e-9, math.hypot(x1 - x0, y1 - y0))
                dist = abs((x1 - x0) * (y0 - cy) - (x0 - cx) * (y1 - y0)) / seg
                res.append(dist - abs(float(r)))
            else:
                raise ValueError(f"Unsupported constraint kind: {ck!r}")
        return np.array(res, dtype=float)

    def _jacobian(qvec: np.ndarray, r0: np.ndarray) -> np.ndarray:
        m = len(r0)
        if m == 0 or n_vars == 0:
            return np.zeros((m, n_vars), dtype=float)
        J = np.zeros((m, n_vars), dtype=float)
        eps = 1e-7
        for j in range(n_vars):
            qp = qvec.copy()
            qp[j] += eps
            J[:, j] = (_residuals(qp) - r0) / eps
        return J

    max_res = 0.0
    rank = 0
    if constraints and n_vars > 0:
        lam = 1e-5
        for _ in range(45):
            r = _residuals(q)
            max_res = float(np.max(np.abs(r))) if len(r) else 0.0
            if max_res < 1e-10:
                break
            J = _jacobian(q, r)
            A = J.T @ J + lam * np.eye(n_vars)
            b = -(J.T @ r)
            try:
                dq = np.linalg.solve(A, b)
            except np.linalg.LinAlgError:
                dq, *_ = np.linalg.lstsq(J, -r, rcond=None)
            q_next = q + dq
            for e in entities:
                if e["kind"] in {"circle", "arc"}:
                    s, _ = var_slices[e["id"]]
                    q_next[s + 2] = max(1e-4, q_next[s + 2])
            r_next = _residuals(q_next)
            if np.dot(r_next, r_next) <= np.dot(r, r) + 1e-18:
                q = q_next
                lam = max(1e-8, lam * 0.5)
            else:
                lam = min(1e3, lam * 4.0)
        r_final = _residuals(q)
        max_res = float(np.max(np.abs(r_final))) if len(r_final) else 0.0
        if len(r_final) > 0:
            J_final = _jacobian(q, r_final)
            rank = int(np.linalg.matrix_rank(J_final, tol=1e-6))
    dof = max(0, n_vars - rank)
    converged = max_res < 1e-4
    if not converged:
        status = "failed"
    elif dof == 0:
        status = "fully_constrained"
    else:
        status = "under_constrained"

    solved_entities: list[dict[str, Any]] = []
    for e in entities:
        s, _ = var_slices[e["id"]]
        k = e["kind"]
        ecopy = dict(e)
        if k == "line":
            ecopy["p0"] = [float(q[s]), float(q[s + 1])]
            ecopy["p1"] = [float(q[s + 2]), float(q[s + 3])]
        elif k == "circle":
            ecopy["center"] = [float(q[s]), float(q[s + 1])]
            ecopy["radius"] = float(q[s + 2])
        elif k == "arc":
            ecopy["center"] = [float(q[s]), float(q[s + 1])]
            ecopy["radius"] = float(q[s + 2])
            ecopy["start_deg"] = float(q[s + 3])
            ecopy["end_deg"] = float(q[s + 4])
        elif k == "spline":
            npts = len(e["points"])
            ecopy["points"] = [[float(q[s + 2 * i]), float(q[s + 2 * i + 1])] for i in range(npts)]
        solved_entities.append(ecopy)

    return {
        "schema_version": "1.0",
        "converged": converged,
        "status": status,
        "max_residual": max_res,
        "degrees_of_freedom": dof,
        "constraint_count": len(constraints),
        "entities": solved_entities,
    }


def _sketch_wire_cq(cq, solved_entities: list[dict[str, Any]], workplane: dict[str, Any] | None):
    """Build an exact closed OCCT Wire/Face in millimetres on the target 3D workplane."""
    origin_m, u_ax, v_ax, normal_ax = normalize_workplane(workplane)

    def to_mm3(x_m: float, y_m: float) -> Any:
        p = (origin_m + x_m * u_ax + y_m * v_ax) * 1000.0
        return cq.Vector(float(p[0]), float(p[1]), float(p[2]))

    active = [e for e in solved_entities if not e.get("construction", False)]
    if not active:
        raise ValueError("Sketch has no non-construction geometry to build a solid feature")

    edges: list[Any] = []
    for e in active:
        k = e["kind"]
        if k == "line":
            p0, p1 = e["p0"], e["p1"]
            if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < 1e-6:
                continue
            edges.append(cq.Edge.makeLine(to_mm3(p0[0], p0[1]), to_mm3(p1[0], p1[1])))
        elif k == "circle":
            cx, cy = e["center"]
            r_mm = float(e["radius"]) * 1000.0
            if r_mm <= 0.05:
                raise ValueError("Circle radius must be > 0.05 mm")
            edges.append(cq.Edge.makeCircle(r_mm, to_mm3(cx, cy), cq.Vector(*normal_ax.tolist())))
        elif k == "arc":
            cx, cy = e["center"]
            r = float(e["radius"])
            a0 = math.radians(float(e["start_deg"]))
            a1 = math.radians(float(e["end_deg"]))
            am = 0.5 * (a0 + a1)
            edges.append(
                cq.Edge.makeThreePointArc(
                    to_mm3(cx + r * math.cos(a0), cy + r * math.sin(a0)),
                    to_mm3(cx + r * math.cos(am), cy + r * math.sin(am)),
                    to_mm3(cx + r * math.cos(a1), cy + r * math.sin(a1)),
                )
            )
        elif k == "spline":
            pts = [to_mm3(pt[0], pt[1]) for pt in e["points"]]
            if e.get("closed", True):
                edges.append(cq.Edge.makeSpline(pts, periodic=True))
            else:
                edges.append(cq.Edge.makeSpline(pts))

    wires = cq.Wire.assembleEdges(edges) if len(edges) > 1 else edges[0]
    if isinstance(wires, list):
        wire = wires[0]
    elif isinstance(wires, cq.Edge):
        wire = cq.Wire.assembleEdges([wires])
    else:
        wire = wires
    if not wire.IsClosed():
        raise ValueError("Sketch profile must form a closed loop before 3D extrude/revolve/loft")
    return wire, origin_m, u_ax, v_ax, normal_ax


def _tessellate_occt_shape(shape, deflection_mm: float = 0.35) -> dict[str, Any]:
    """Extract per-face triangles, outward face planes, and sharp B-rep edges in SI meters."""
    from OCP.Bnd import Bnd_Box
    from OCP.BRep import BRep_Tool
    from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp, BRepGProp_Face
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Pnt, gp_Vec

    BRepMesh_IncrementalMesh(shape.wrapped, deflection_mm, False, 0.35, True)

    vertices: list[list[float]] = []
    indices: list[int] = []
    faces_meta: list[dict[str, Any]] = []
    edges_out: list[list[float]] = []

    f_exp = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    face_idx = 0
    while f_exp.More():
        face = TopoDS.Face_s(f_exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        sprops = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, sprops)
        farea_m2 = float(sprops.Mass()) * 1e-6
        fcm = sprops.CentreOfMass()

        surf_adapt = BRepAdaptor_Surface(face, True)
        u0, u1 = surf_adapt.FirstUParameter(), surf_adapt.LastUParameter()
        v0, v1 = surf_adapt.FirstVParameter(), surf_adapt.LastVParameter()
        um, vm = 0.5 * (u0 + u1), 0.5 * (v0 + v1)
        gface = BRepGProp_Face(face)
        pnt = gp_Pnt()
        nvec = gp_Vec()
        gface.Normal(um, vm, pnt, nvec)
        if nvec.Magnitude() > 1e-9:
            nvec.Normalize()
        n_arr = np.array([nvec.X(), nvec.Y(), nvec.Z()], dtype=float)
        if float(np.linalg.norm(n_arr)) < 1e-8:
            n_arr = np.array([0.0, 0.0, 1.0])
        n_arr = _norm3(n_arr)
        ref = np.array([0.0, 0.0, 1.0]) if abs(n_arr[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u_ax = _norm3(np.cross(ref, n_arr))
        v_ax = _norm3(np.cross(n_arr, u_ax))
        stype = surf_adapt.GetType()
        kind = "plane" if stype == GeomAbs_Plane else ("cylinder" if stype == GeomAbs_Cylinder else "bspline")

        faces_meta.append({
            "face_id": face_idx,
            "kind": kind,
            "area_m2": farea_m2,
            "center_m": [float(fcm.X()) * 1e-3, float(fcm.Y()) * 1e-3, float(fcm.Z()) * 1e-3],
            "normal": [float(n_arr[0]), float(n_arr[1]), float(n_arr[2])],
            "u_axis": [float(u_ax[0]), float(u_ax[1]), float(u_ax[2])],
            "v_axis": [float(v_ax[0]), float(v_ax[1]), float(v_ax[2])],
        })

        if tri is not None and tri.NbTriangles() > 0:
            trsf = loc.Transformation()
            nb_nodes = tri.NbNodes()
            base = len(vertices)
            rev = face.Orientation() == TopAbs_REVERSED
            for ni in range(1, nb_nodes + 1):
                p = tri.Node(ni).Transformed(trsf)
                vertices.append([
                    float(p.X()) * 1e-3,
                    float(p.Y()) * 1e-3,
                    float(p.Z()) * 1e-3,
                    float(n_arr[0]),
                    float(n_arr[1]),
                    float(n_arr[2]),
                    face_idx,
                ])
            for ti in range(1, tri.NbTriangles() + 1):
                t = tri.Triangle(ti)
                i1, i2, i3 = t.Get()
                if rev:
                    indices.extend([base + i1 - 1, base + i3 - 1, base + i2 - 1])
                else:
                    indices.extend([base + i1 - 1, base + i2 - 1, base + i3 - 1])

        face_idx += 1
        f_exp.Next()

    e_exp = TopExp_Explorer(shape.wrapped, TopAbs_EDGE)
    edge_idx = 0
    while e_exp.More():
        edge = TopoDS.Edge_s(e_exp.Current())
        curve = BRepAdaptor_Curve(edge)
        t0, t1 = curve.FirstParameter(), curve.LastParameter()
        if math.isfinite(t0) and math.isfinite(t1) and abs(t1 - t0) > 1e-9:
            segs = 1 if curve.GetType() == 0 else 14
            for k in range(segs):
                pa = curve.Value(t0 + (t1 - t0) * k / segs)
                pb = curve.Value(t0 + (t1 - t0) * (k + 1) / segs)
                edges_out.append([
                    float(pa.X()) * 1e-3, float(pa.Y()) * 1e-3, float(pa.Z()) * 1e-3,
                    float(pb.X()) * 1e-3, float(pb.Y()) * 1e-3, float(pb.Z()) * 1e-3,
                    edge_idx,
                ])
        edge_idx += 1
        e_exp.Next()

    bbox = Bnd_Box()
    BRepBndLib.Add_s(shape.wrapped, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return {
        "vertices": vertices,
        "indices": indices,
        "edges": edges_out,
        "faces": faces_meta,
        "bbox_min_m": [xmin * 1e-3, ymin * 1e-3, zmin * 1e-3],
        "bbox_max_m": [xmax * 1e-3, ymax * 1e-3, zmax * 1e-3],
    }


def _export_2d_dxf(solved_entities: list[dict[str, Any]], dxf_path: Path) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for e in solved_entities:
        if e.get("construction", False):
            continue
        k = e["kind"]
        if k == "line":
            msp.add_line((e["p0"][0] * 1000.0, e["p0"][1] * 1000.0), (e["p1"][0] * 1000.0, e["p1"][1] * 1000.0))
        elif k == "circle":
            msp.add_circle((e["center"][0] * 1000.0, e["center"][1] * 1000.0), radius=e["radius"] * 1000.0)
        elif k == "arc":
            msp.add_arc(
                (e["center"][0] * 1000.0, e["center"][1] * 1000.0),
                radius=e["radius"] * 1000.0,
                start_angle=e["start_deg"],
                end_angle=e["end_deg"],
            )
        elif k == "spline":
            pts_mm = [(pt[0] * 1000.0, pt[1] * 1000.0) for pt in e["points"]]
            if e.get("closed", True) and len(pts_mm) >= 3:
                pts_mm.append(pts_mm[0])
            msp.add_spline(pts_mm)
    dxf_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(dxf_path))


def _resolve_face_plane(spec_wp: dict[str, Any] | None, current_faces: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Resolve workplane against exact B-rep picked face if face_id is provided."""
    if not spec_wp:
        return None
    if "face_id" in spec_wp and spec_wp["face_id"] is not None and int(spec_wp["face_id"]) >= 0:
        fid = int(spec_wp["face_id"])
        for f in current_faces:
            if f["face_id"] == fid:
                return {
                    "origin_m": f["center_m"],
                    "normal": f["normal"],
                    "u_axis": f["u_axis"],
                    "v_axis": f["v_axis"],
                }
    return spec_wp


def build_freeform_cad_model(spec: dict[str, Any], export_dir: Path | None = None) -> dict[str, Any]:
    """Execute constrained 2D sketches + OCCT B-rep operations (boss/cut/revolve/loft/fillet/chamfer/shell)."""
    import cadquery as cq
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepFilletAPI import BRepFilletAPI_MakeChamfer, BRepFilletAPI_MakeFillet
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid, BRepOffsetAPI_ThruSections
    from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol
    from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp, TopExp_Explorer
    from OCP.TopTools import TopTools_IndexedDataMapOfShapeListOfShape, TopTools_ListOfShape
    from OCP.TopoDS import TopoDS
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Vec

    part_name = str(spec.get("part_name", "FreeformPart")).strip() or "FreeformPart"
    density = float(spec.get("density_kg_m3", 1580.0))
    density_source = str(spec.get("density_source", "")).strip()
    if not math.isfinite(density) or density <= 0.0:
        raise ValueError("density_kg_m3 must be finite and > 0")
    if not density_source:
        raise ValueError("density_source provenance is required for mass properties")

    features = [f for f in spec.get("features", []) if not bool(f.get("suppressed", False))]
    if not features:
        raise ValueError("At least one active CAD feature is required")

    solid: Any | None = None
    last_sketch_solved: dict[str, Any] | None = None
    feature_log: list[str] = []
    cached_faces: list[dict[str, Any]] = []

    for f_idx, feat in enumerate(features):
        op = str(feat.get("op", "extrude_boss")).lower()

        if op in {"extrude_boss", "extrude_cut", "revolve"}:
            sk_spec = feat.get("sketch") or spec.get("sketch")
            if not sk_spec:
                raise ValueError(f"Feature #{f_idx} ({op}) missing sketch definition")
            solved = solve_freeform_sketch(sk_spec)
            if not solved["converged"]:
                raise ValueError(f"Sketch constraints failed to converge in feature #{f_idx} (max residual={solved['max_residual']:.3e})")
            last_sketch_solved = solved
            wp = _resolve_face_plane(feat.get("workplane") or sk_spec.get("workplane"), cached_faces)
            wire, origin_m, u_ax, v_ax, n_ax = _sketch_wire_cq(cq, solved["entities"], wp)
            face = cq.Face.makeFromWires(wire)

            if op in {"extrude_boss", "extrude_cut"}:
                depth_m = float(feat.get("depth_m", 0.02))
                if depth_m <= 1e-5:
                    raise ValueError(f"{op} depth_m must be > 0.01 mm")
                dir_sign = -1.0 if op == "extrude_cut" else 1.0
                if bool(feat.get("flip_direction", False)):
                    dir_sign *= -1.0
                vec = n_ax * (dir_sign * depth_m * 1000.0)
                if bool(feat.get("symmetric", False)) and op == "extrude_boss":
                    p_half = cq.Shape.cast(BRepPrimAPI_MakePrism(face.wrapped, gp_Vec(*(0.5 * vec).tolist())).Shape())
                    n_half = cq.Shape.cast(BRepPrimAPI_MakePrism(face.wrapped, gp_Vec(*(-0.5 * vec).tolist())).Shape())
                    prism = p_half.fuse(n_half)
                else:
                    prism = cq.Shape.cast(BRepPrimAPI_MakePrism(face.wrapped, gp_Vec(*vec.tolist())).Shape())
                if op == "extrude_boss":
                    solid = prism if solid is None else solid.fuse(prism)
                else:
                    if solid is None:
                        raise ValueError("extrude_cut requires an existing base solid body")
                    solid = solid.cut(prism)
                feature_log.append(f"{op}:{depth_m*1000:.1f}mm")

            elif op == "revolve":
                ang_deg = float(feat.get("angle_deg", 360.0))
                if not (0.5 <= ang_deg <= 360.0):
                    raise ValueError("Revolve angle_deg must be within [0.5, 360.0]")
                ax_pt = feat.get("axis_origin_m", [0.0, 0.0])
                ax_dir2 = feat.get("axis_dir_2d", [1.0, 0.0])
                p3 = (origin_m + float(ax_pt[0]) * u_ax + float(ax_pt[1]) * v_ax) * 1000.0
                d3 = _norm3(float(ax_dir2[0]) * u_ax + float(ax_dir2[1]) * v_ax)
                ax1 = gp_Ax1(gp_Pnt(*p3.tolist()), gp_Dir(*d3.tolist()))
                rev = cq.Shape.cast(BRepPrimAPI_MakeRevol(face.wrapped, ax1, math.radians(ang_deg)).Shape())
                solid = rev if solid is None else solid.fuse(rev)
                feature_log.append(f"revolve:{ang_deg:.0f}deg")

        elif op == "loft":
            stations = feat.get("stations") or []
            wires_to_loft: list[Any] = []
            if len(stations) >= 2:
                for st in stations:
                    solved = solve_freeform_sketch(st)
                    if not solved["converged"]:
                        raise ValueError("Loft station sketch constraints did not converge")
                    last_sketch_solved = solved
                    wire, *_ = _sketch_wire_cq(cq, solved["entities"], st.get("workplane"))
                    wires_to_loft.append(wire)
            else:
                sk_spec = feat.get("sketch") or spec.get("sketch")
                if not sk_spec:
                    raise ValueError("Loft requires either >=2 stations or 1 base sketch + loft_offset_m")
                solved = solve_freeform_sketch(sk_spec)
                if not solved["converged"]:
                    raise ValueError("Loft base sketch failed constraints")
                last_sketch_solved = solved
                wp0 = _resolve_face_plane(feat.get("workplane") or sk_spec.get("workplane"), cached_faces)
                wire0, o0, u0, v0, n0 = _sketch_wire_cq(cq, solved["entities"], wp0)
                offset_m = float(feat.get("loft_offset_m", 0.08))
                scale_f = float(feat.get("loft_scale", 0.55))
                if abs(offset_m) < 1e-4 or scale_f <= 0.05:
                    raise ValueError("Invalid loft_offset_m or loft_scale")
                wp1 = {"origin_m": (o0 + n0 * offset_m).tolist(), "normal": n0.tolist(), "u_axis": u0.tolist()}
                scaled_ents = []
                for e in solved["entities"]:
                    se = dict(e)
                    if e["kind"] == "line":
                        se["p0"] = [e["p0"][0] * scale_f, e["p0"][1] * scale_f]
                        se["p1"] = [e["p1"][0] * scale_f, e["p1"][1] * scale_f]
                    elif e["kind"] in {"circle", "arc"}:
                        se["center"] = [e["center"][0] * scale_f, e["center"][1] * scale_f]
                        se["radius"] = e["radius"] * scale_f
                    elif e["kind"] == "spline":
                        se["points"] = [[pt[0] * scale_f, pt[1] * scale_f] for pt in e["points"]]
                    scaled_ents.append(se)
                wire1, *_ = _sketch_wire_cq(cq, scaled_ents, wp1)
                wires_to_loft = [wire0, wire1]
            thru = BRepOffsetAPI_ThruSections(True, bool(feat.get("ruled", False)))
            for w in wires_to_loft:
                thru.AddWire(w.wrapped)
            thru.Build()
            if not thru.IsDone():
                raise ValueError("Open CASCADE Loft (ThruSections) failed for these profiles")
            loft_shape = cq.Shape.cast(thru.Shape())
            solid = loft_shape if solid is None else solid.fuse(loft_shape)
            feature_log.append("loft")

        elif op in {"fillet", "chamfer"}:
            if solid is None:
                raise ValueError(f"{op} requires an existing base solid body")
            val_mm = float(feat.get("radius_m" if op == "fillet" else "distance_m", 0.002)) * 1000.0
            if val_mm <= 0.05:
                raise ValueError(f"{op} value must be > 0.05 mm")
            edge_indices = [int(i) for i in feat.get("edge_indices", [])]
            e_exp = TopExp_Explorer(solid.wrapped, TopAbs_EDGE)
            target_edges = []
            idx_e = 0
            while e_exp.More():
                edge = TopoDS.Edge_s(e_exp.Current())
                if not edge_indices or idx_e in edge_indices:
                    target_edges.append(edge)
                idx_e += 1
                e_exp.Next()
            if not target_edges:
                raise ValueError(f"No edges selected for {op}")

            if op == "fillet":
                builder = BRepFilletAPI_MakeFillet(solid.wrapped)
                for edge in target_edges:
                    builder.Add(val_mm, edge)
            else:
                ef_map = TopTools_IndexedDataMapOfShapeListOfShape()
                TopExp.MapShapesAndAncestors_s(solid.wrapped, TopAbs_EDGE, TopAbs_FACE, ef_map)
                builder = BRepFilletAPI_MakeChamfer(solid.wrapped)
                for edge in target_edges:
                    if ef_map.Contains(edge):
                        faces = ef_map.FindFromKey(edge)
                        if not faces.IsEmpty():
                            builder.Add(val_mm, val_mm, edge, TopoDS.Face_s(faces.First()))
            builder.Build()
            if not builder.IsDone():
                raise ValueError(f"Open CASCADE {op} ({val_mm:.2f} mm) exceeds local edge curvature or fails geometry check")
            solid = cq.Shape.cast(builder.Shape())
            feature_log.append(f"{op}:{val_mm:.2f}mm")

        elif op == "shell":
            if solid is None:
                raise ValueError("shell requires an existing base solid body")
            thick_mm = float(feat.get("thickness_m", 0.003)) * 1000.0
            if thick_mm <= 0.1:
                raise ValueError("Shell wall thickness must be > 0.1 mm")
            face_indices = [int(i) for i in feat.get("face_indices", [])]
            remove_list = TopTools_ListOfShape()
            f_exp = TopExp_Explorer(solid.wrapped, TopAbs_FACE)
            all_faces = []
            while f_exp.More():
                all_faces.append(TopoDS.Face_s(f_exp.Current()))
                f_exp.Next()
            if not all_faces:
                raise ValueError("Solid has no faces to shell")
            if face_indices:
                for fi in face_indices:
                    if 0 <= fi < len(all_faces):
                        remove_list.Append(all_faces[fi])
            else:
                # Default: open the highest-Z face cleanly (common aerospace enclosure hollowing)
                best_i = max(range(len(cached_faces)), key=lambda i: cached_faces[i]["center_m"][2]) if cached_faces else (len(all_faces) - 1)
                remove_list.Append(all_faces[min(best_i, len(all_faces) - 1)])

            shell_builder = BRepOffsetAPI_MakeThickSolid()
            shell_builder.MakeThickSolidByJoin(solid.wrapped, remove_list, -thick_mm, 1e-3)
            shell_builder.Build()
            if not shell_builder.IsDone():
                raise ValueError(f"Open CASCADE Shell (-{thick_mm:.2f} mm) failed: wall thickness too large for geometry")
            solid = cq.Shape.cast(shell_builder.Shape())
            feature_log.append(f"shell:{thick_mm:.2f}mm")

        else:
            raise ValueError(f"Unsupported CAD operation: {op!r}")

        if solid is None or not solid.isValid() or len(solid.Solids()) == 0 or solid.Volume() <= 0.0:
            raise ValueError(f"Feature #{f_idx} ({op}) produced invalid or zero-volume B-rep solid")
        # Refresh per-face metadata so subsequent features can sketch on picked faces created by earlier features!
        cached_faces = _tessellate_occt_shape(solid, deflection_mm=0.6)["faces"]

    assert solid is not None
    tess = _tessellate_occt_shape(solid, deflection_mm=0.25)
    vol_m3 = float(solid.Volume()) * 1e-9
    mass_kg = vol_m3 * density
    cm = solid.Center()
    cog_m = [float(cm.x) * 1e-3, float(cm.y) * 1e-3, float(cm.z) * 1e-3]
    inertia_mat = (np.asarray(cq.Shape.matrixOfInertia(solid), dtype=float) * density * 1e-15).tolist()

    exports: dict[str, str | None] = {"step": None, "stl": None, "dxf": None, "mesh_json": None}
    slug = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in part_name.lower()).strip("_") or "freeform_part"
    if export_dir is not None:
        export_dir.mkdir(parents=True, exist_ok=True)
        step_p = Path(spec.get("export_step_path") or (export_dir / f"{slug}.step"))
        stl_p = Path(spec.get("export_stl_path") or (export_dir / f"{slug}.stl"))
        step_p.parent.mkdir(parents=True, exist_ok=True)
        stl_p.parent.mkdir(parents=True, exist_ok=True)
        cq.exporters.export(solid, str(step_p))
        cq.exporters.export(solid, str(stl_p))
        exports["step"] = str(step_p)
        exports["stl"] = str(stl_p)
        if last_sketch_solved is not None:
            dxf_p = Path(spec.get("export_dxf_path") or (export_dir / f"{slug}_sketch.dxf"))
            _export_2d_dxf(last_sketch_solved["entities"], dxf_p)
            exports["dxf"] = str(dxf_p)
    else:
        for key, ext_fn in (("export_step_path", "step"), ("export_stl_path", "stl")):
            if spec.get(key):
                p = Path(spec[key])
                p.parent.mkdir(parents=True, exist_ok=True)
                cq.exporters.export(solid, str(p))
                exports[ext_fn] = str(p)
        if spec.get("export_dxf_path") and last_sketch_solved is not None:
            dxf_p = Path(spec["export_dxf_path"])
            _export_2d_dxf(last_sketch_solved["entities"], dxf_p)
            exports["dxf"] = str(dxf_p)

    payload = {
        "schema_version": "1.0",
        "part_name": part_name,
        "geometry_backend": "cadquery_occt",
        "occt_exact_brep": True,
        "is_valid": bool(solid.isValid()),
        "solid_count": len(solid.Solids()),
        "feature_history": feature_log,
        "sketch_status": last_sketch_solved["status"] if last_sketch_solved else "none",
        "sketch_dof": last_sketch_solved["degrees_of_freedom"] if last_sketch_solved else 0,
        "volume_m3": vol_m3,
        "mass_kg": mass_kg,
        "density_kg_m3": density,
        "density_source": density_source,
        "center_of_mass_m": cog_m,
        "inertia_about_cog_kg_m2": inertia_mat,
        "bbox_min_m": tess["bbox_min_m"],
        "bbox_max_m": tess["bbox_max_m"],
        "face_count": len(tess["faces"]),
        "edge_count": len(tess["edges"]),
        "triangle_count": len(tess["indices"]) // 3,
        "exports": exports,
        "physical_validation_status": "UNVALIDATED_CUSTOM",
        "tessellation": tess,
        "spec_sha256": sha256(json.dumps(spec, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    if spec.get("mesh_out_path"):
        mp = Path(spec["mesh_out_path"])
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps({"tessellation": tess, "volume_m3": vol_m3, "mass_kg": mass_kg, "center_of_mass_m": cog_m, "face_count": len(tess["faces"])}), encoding="utf-8")
        exports["mesh_json"] = str(mp)
    return payload
