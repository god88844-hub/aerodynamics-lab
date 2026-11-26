"""Slice 0B software verification: Constrained 2D sketch, parametric wing CAD, lifting-line VLM, and 6-DoF fixed-wing mission."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from geometry.fixed_wing_cad import (
    ConstrainedSketch2D,
    ParametricWingSpec,
    compute_wing_geometry_properties,
    export_cad_exchange_manifest,
    naca4_airfoil_coordinates,
)
from physics.aerodynamics.fixed_wing import (
    compute_fixed_wing_cruise_trim,
    run_fixed_wing_mission,
    solve_lifting_line_wing,
)

ROOT = Path(__file__).resolve().parents[2]


def test_sketch_airfoil_wing_geometry_and_unit_safe_exchange():
    sketch = ConstrainedSketch2D("wing_spar_box", width_m=0.12, height_m=0.04, thickness_m=1.2)
    tree = sketch.to_feature_tree()
    assert tree["area_m2"] == pytest.approx(0.0048)
    assert tree["volume_m3"] == pytest.approx(0.00576)

    pts = naca4_airfoil_coordinates("2412", n_points_per_surface=20)
    assert len(pts) == 39

    wing_unverified = ParametricWingSpec(name="Student Trainer Wing", wingspan_m=1.6, root_chord_m=0.28, tip_chord_m=0.18)
    props_unv = compute_wing_geometry_properties(wing_unverified)
    assert props_unv["mass_kg"] is None
    assert props_unv["mass_provenance_status"] == "UNVERIFIED_ESTIMATE"
    assert props_unv["planform_area_m2"] == pytest.approx(0.5 * (0.28 + 0.18) * 1.6)

    wing_mat = ParametricWingSpec(
        name="Carbon Wing",
        wingspan_m=1.6,
        root_chord_m=0.28,
        tip_chord_m=0.18,
        material_density_kg_m3=1550.0,
        density_source="cmh17_typical_cfrp",
    )
    ex = export_cad_exchange_manifest(wing_mat)
    assert ex["unit_system"] == "SI_METERS"
    assert ex["payload"]["mass_kg"] > 0.0
    with pytest.raises(ValueError, match="SI_METERS"):
        export_cad_exchange_manifest(wing_mat, unit_system="IMPERIAL_INCHES")


def test_lifting_line_trim_stall_refusal_and_mission_cli(tmp_path):
    wing = ParametricWingSpec(name="Glider Wing", wingspan_m=1.8, root_chord_m=0.26, tip_chord_m=0.16)
    aero = solve_lifting_line_wing(wing, alpha_deg=4.0, airspeed_m_s=18.0)
    assert aero["cl"] > 0.4
    assert aero["span_efficiency_e"] <= 1.0 and aero["span_efficiency_e"] > 0.7

    # Post-stall and compressible regimes fail closed
    with pytest.raises(ValueError, match="Post-stall"):
        solve_lifting_line_wing(wing, alpha_deg=22.0, airspeed_m_s=18.0)
    with pytest.raises(ValueError, match="Compressible"):
        solve_lifting_line_wing(wing, alpha_deg=2.0, airspeed_m_s=140.0)

    trim = compute_fixed_wing_cruise_trim(wing, mass_kg=2.2, airspeed_m_s=18.0)
    assert trim["trim_feasible"] is True
    assert 0.0 <= trim["alpha_trim_deg"] <= 8.0

    # Strict load-factor limit triggers FAIL
    overloaded = run_fixed_wing_mission(wing, mass_kg=2.2, max_load_factor_g=0.2, duration_s=2.0)
    assert overloaded["status"] == "failed" and overloaded["verdict"] == "FAIL"

    in_path = tmp_path / "fw_in.json"
    out_path = tmp_path / "fw_out.json"
    in_path.write_text(json.dumps({"wingspan_m": 1.8, "root_chord_m": 0.26, "tip_chord_m": 0.16, "mass_kg": 2.2}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "fixed-wing-sim", str(in_path), str(out_path)], check=True, cwd=ROOT)
    cli_res = json.loads(out_path.read_text(encoding="utf-8"))
    assert cli_res["mission"]["status"] == "completed"
