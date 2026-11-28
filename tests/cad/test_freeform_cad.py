"""Tests for 2D constraint sketch solver & Open CASCADE freeform B-rep operations."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

from geometry.freeform_cad import build_freeform_cad_model, solve_freeform_sketch

ROOT = Path(__file__).resolve().parents[2]


def test_2d_constraint_solver_converges_closed_quad_with_zero_dof() -> None:
    sketch = {
        "entities": [
            {"id": "e0", "kind": "line", "p0": [0.002, 0.001], "p1": [0.095, 0.005]},
            {"id": "e1", "kind": "line", "p0": [0.092, 0.003], "p1": [0.098, 0.055]},
            {"id": "e2", "kind": "line", "p0": [0.096, 0.052], "p1": [0.004, 0.048]},
            {"id": "e3", "kind": "line", "p0": [0.001, 0.049], "p1": [0.000, 0.002]},
        ],
        "constraints": [
            {"kind": "fixed", "a": "e0", "pt_a": 0, "target_xy": [0.0, 0.0]},
            {"kind": "coincident", "a": "e0", "pt_a": 1, "b": "e1", "pt_b": 0},
            {"kind": "coincident", "a": "e1", "pt_a": 1, "b": "e2", "pt_b": 0},
            {"kind": "coincident", "a": "e2", "pt_a": 1, "b": "e3", "pt_b": 0},
            {"kind": "coincident", "a": "e3", "pt_a": 1, "b": "e0", "pt_b": 0},
            {"kind": "horizontal", "a": "e0"},
            {"kind": "perpendicular", "a": "e0", "b": "e1"},
            {"kind": "parallel", "a": "e0", "b": "e2"},
            {"kind": "perpendicular", "a": "e2", "b": "e3"},
            {"kind": "length", "a": "e0", "value": 0.120},
            {"kind": "length", "a": "e1", "value": 0.060},
        ],
    }
    solved = solve_freeform_sketch(sketch)
    assert solved["converged"] is True
    assert solved["status"] == "fully_constrained"
    assert solved["degrees_of_freedom"] == 0
    e0 = solved["entities"][0]
    e1 = solved["entities"][1]
    assert math.hypot(e0["p1"][0] - e0["p0"][0], e0["p1"][1] - e0["p0"][1]) == pytest.approx(0.120, abs=1e-6)
    assert math.hypot(e1["p1"][0] - e1["p0"][0], e1["p1"][1] - e1["p0"][1]) == pytest.approx(0.060, abs=1e-6)


def test_2d_constraint_solver_tangent_and_equal() -> None:
    sketch = {
        "entities": [
            {"id": "c0", "kind": "circle", "center": [0.02, 0.03], "radius": 0.012},
            {"id": "c1", "kind": "circle", "center": [0.06, 0.03], "radius": 0.020},
            {"id": "l0", "kind": "line", "p0": [0.0, 0.0], "p1": [0.08, 0.0]},
        ],
        "constraints": [
            {"kind": "fixed", "a": "l0", "pt_a": 0, "target_xy": [0.0, 0.0]},
            {"kind": "fixed", "a": "l0", "pt_a": 1, "target_xy": [0.08, 0.0]},
            {"kind": "radius", "a": "c0", "value": 0.015},
            {"kind": "equal", "a": "c0", "b": "c1"},
            {"kind": "tangent", "a": "l0", "b": "c0"},
        ],
    }
    solved = solve_freeform_sketch(sketch)
    assert solved["converged"] is True
    c0, c1 = solved["entities"][0], solved["entities"][1]
    assert c0["radius"] == pytest.approx(0.015, abs=1e-6)
    assert c1["radius"] == pytest.approx(0.015, abs=1e-6)
    assert abs(c0["center"][1]) == pytest.approx(0.015, abs=1e-6)


def test_occt_freeform_extrude_face_cut_fillet_shell_and_exports(tmp_path: Path) -> None:
    pytest.importorskip("cadquery")
    spec = {
        "part_name": "Avionics Mount Block",
        "density_kg_m3": 2700.0,
        "density_source": "al_6061_t6_asm",
        "features": [
            {
                "op": "extrude_boss",
                "depth_m": 0.040,
                "workplane": {"preset": "XY"},
                "sketch": {
                    "entities": [{"id": "r0", "kind": "rect", "center": [0.0, 0.0], "width_m": 0.100, "height_m": 0.080}],
                    "constraints": [],
                },
            },
            {
                "op": "shell",
                "thickness_m": 0.004,
            },
            {
                "op": "extrude_cut",
                "depth_m": 0.020,
                "workplane": {"face_id": 0},
                "sketch": {
                    "entities": [{"id": "h0", "kind": "circle", "center": [0.0, 0.0], "radius": 0.012}],
                    "constraints": [],
                },
            },
            {
                "op": "fillet",
                "radius_m": 0.0015,
                "edge_indices": [0, 1],
            },
        ],
    }
    res = build_freeform_cad_model(spec, export_dir=tmp_path)
    assert res["occt_exact_brep"] is True
    assert res["is_valid"] is True
    assert res["solid_count"] == 1
    assert res["volume_m3"] > 1e-6
    # Shelled + pocketed block must have strictly smaller volume than solid 0.10*0.08*0.04 box (3.2e-4 m3)
    assert res["volume_m3"] < 3.2e-4
    assert res["face_count"] > 6
    assert res["triangle_count"] > 20
    assert Path(res["exports"]["step"]).is_file()
    assert Path(res["exports"]["stl"]).is_file()
    assert Path(res["exports"]["dxf"]).is_file()


def test_occt_freeform_revolve_loft_chamfer_and_spline(tmp_path: Path) -> None:
    cq = pytest.importorskip("cadquery")
    # 1. Spline loft between two airfoil-like sections
    loft_spec = {
        "part_name": "Spline Loft Fairing",
        "density_kg_m3": 1580.0,
        "density_source": "toray_cfrp",
        "features": [
            {
                "op": "loft",
                "loft_offset_m": 0.090,
                "loft_scale": 0.50,
                "sketch": {
                    "entities": [
                        {
                            "id": "sp0",
                            "kind": "spline",
                            "closed": True,
                            "points": [
                                [-0.04, 0.0],
                                [-0.01, 0.018],
                                [0.05, 0.006],
                                [-0.01, -0.014],
                            ],
                        }
                    ],
                    "constraints": [],
                },
            },
            {
                "op": "chamfer",
                "distance_m": 0.001,
                "edge_indices": [0],
            },
        ],
    }
    loft_res = build_freeform_cad_model(loft_spec, export_dir=tmp_path / "loft")
    assert loft_res["occt_exact_brep"] is True
    assert loft_res["volume_m3"] > 0.0
    exact = cq.importers.importStep(loft_res["exports"]["step"]).val()
    assert exact.isValid() and len(exact.Solids()) == 1

    # 2. Revolve + CLI invocation roundtrip
    rev_spec = {
        "part_name": "Nose Spinner",
        "density_kg_m3": 1200.0,
        "density_source": "abs_molded",
        "export_dir": str(tmp_path / "rev"),
        "features": [
            {
                "op": "revolve",
                "angle_deg": 360.0,
                "axis_origin_m": [0.0, 0.0],
                "axis_dir_2d": [1.0, 0.0],
                "workplane": {"preset": "XZ"},
                "sketch": {
                    "entities": [
                        {"id": "a", "kind": "line", "p0": [0.0, 0.002], "p1": [0.06, 0.002]},
                        {"id": "b", "kind": "line", "p0": [0.06, 0.002], "p1": [0.06, 0.025]},
                        {"id": "c", "kind": "line", "p0": [0.06, 0.025], "p1": [0.0, 0.002]},
                    ],
                    "constraints": [],
                },
            }
        ],
    }
    in_p = tmp_path / "rev_in.json"
    out_p = tmp_path / "rev_out.json"
    in_p.write_text(json.dumps(rev_spec), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "freeform-cad", str(in_p), str(out_p)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    cli_out = json.loads(out_p.read_text(encoding="utf-8"))
    assert cli_out["occt_exact_brep"] is True
    assert cli_out["volume_m3"] > 0.0
