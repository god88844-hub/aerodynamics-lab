"""Phase 0B software verification: CAD history/exchange/2D drawing, coupled lifting-line/6-DoF polars, & lessons."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from desktop_worker.learning_experiments import EQUATIONS_AND_ASSUMPTIONS, create_fixed_wing_lesson_bundle
from geometry.fixed_wing_cad import (
    FeatureHistoryStack,
    ParametricWingSpec,
    assemble_fixed_wing_vehicle,
    export_2d_engineering_drawing_svg_dxf,
)
from physics.aerodynamics.fixed_wing import (
    compute_fixed_wing_cruise_trim,
    solve_lifting_line_wing,
    verify_fixed_wing_convergence,
)
from physics.aerodynamics.sixdof_fixed_wing import build_derivatives_from_wing, simulate_6dof_fixed_wing
from physics.validation.protocol_registry import load_frozen_protocol_catalog

ROOT = Path(__file__).resolve().parents[2]
EXT_CATALOG = ROOT / "data" / "research" / "extended_protocols.json"


def _sample_wing() -> ParametricWingSpec:
    return ParametricWingSpec(
        name="AeroGlider-Wing",
        wingspan_m=1.80,
        root_chord_m=0.26,
        tip_chord_m=0.14,
        sweep_le_deg=4.0,
        dihedral_deg=3.0,
        twist_tip_deg=-2.0,
        airfoil_code="2412",
        material_density_kg_m3=110.0,
        density_source="UNVERIFIED_ESTIMATE_EPS_CARBON_SPAR",
    )


def test_p0b_feature_history_undo_redo_and_boolean_refusal():
    stack = FeatureHistoryStack()
    snap1 = stack.add_feature("extrude", name="spar_box", params_m={"width_m": 0.04, "height_m": 0.02, "depth_m": 1.6})
    snap2 = stack.add_feature("revolve", name="spinner_cone", params_m={"outer_radius_m": 0.03, "inner_radius_m": 0.01, "length_m": 0.06})
    assert snap2["feature_count"] == 2
    assert snap2["net_volume_m3"] > snap1["net_volume_m3"]

    after_undo = stack.undo()
    assert after_undo["feature_count"] == 1
    assert after_undo["redo_available"] == 1
    assert after_undo["net_volume_m3"] == pytest.approx(snap1["net_volume_m3"])

    after_redo = stack.redo()
    assert after_redo["feature_count"] == 2
    assert after_redo["net_volume_m3"] == pytest.approx(snap2["net_volume_m3"])

    # Oversized boolean cut exceeding positive solid fails closed
    with pytest.raises(ValueError, match="negative net solid volume"):
        stack.add_feature("boolean_cut", name="bad_cut", params_m={"width_m": 1.0, "height_m": 1.0, "depth_m": 1.0})


def test_p0b_distributed_assembly_and_2d_svg_dxf_drawing(tmp_path):
    wing = _sample_wing()
    assembled = assemble_fixed_wing_vehicle(wing, fuselage_mass_kg=1.15)
    assert assembled["total_mass_kg"] > 1.15
    assert assembled["frame"] == "body_right_handed_z_up"
    assert assembled["physical_validation_status"] == "UNVALIDATED"
    assert assembled["inertia_about_cog_kg_m2"][2][2] > assembled["inertia_about_cog_kg_m2"][1][1]

    # Fail closed if wing mass & density are both missing
    no_mass_wing = ParametricWingSpec(name="NoMass", wingspan_m=1.4, root_chord_m=0.2, tip_chord_m=0.12)
    with pytest.raises(ValueError, match="Fail-closed"):
        assemble_fixed_wing_vehicle(no_mass_wing, fuselage_mass_kg=1.0)

    svg_file = tmp_path / "wing_drawing.svg"
    dxf_file = tmp_path / "wing_drawing.dxf"
    drawing = export_2d_engineering_drawing_svg_dxf(wing, svg_path=svg_file, dxf_path=dxf_file)
    assert svg_file.is_file() and "<svg" in svg_file.read_text(encoding="utf-8")
    assert dxf_file.is_file() and len(drawing["outputs"]["dxf"]["sha256"]) == 64


def test_p0b_reynolds_coupled_lifting_line_convergence_and_6dof_geometry():
    wing = _sample_wing()
    ll_re = solve_lifting_line_wing(wing, alpha_deg=4.0, airspeed_m_s=18.0, use_reynolds_polar=True)
    assert ll_re["reynolds"] > 1.5e5
    assert ll_re["lift_to_drag"] > 12.0

    conv = verify_fixed_wing_convergence(wing)
    assert conv["refinement_monotone"] is True
    assert conv["span_sensitivity_ld_delta"] > 0.0

    derivs = build_derivatives_from_wing(wing)
    sim = simulate_6dof_fixed_wing(aero=derivs, thrust_n=3.5, duration_s=1.0, dt_s=0.01)
    assert sim["status"] == "completed"
    assert len(sim["telemetry"]["t"]) == len(sim["telemetry"]["q_wxyz"]) == len(sim["telemetry"]["x"])


def test_p0b_fixed_wing_lesson_and_extended_protocol_catalog(tmp_path):
    wing = _sample_wing()
    lesson = create_fixed_wing_lesson_bundle(wing, hypothesis="Increasing aspect ratio at constant wing area reduces induced drag and raises cruise L/D.")
    assert lesson["modified_cruise_ld"] > lesson["baseline_cruise_ld"]
    assert lesson["modified_range_m"] > 100.0
    assert len(EQUATIONS_AND_ASSUMPTIONS) >= 4

    loaded = load_frozen_protocol_catalog(EXT_CATALOG)
    ids = {p["protocol_id"] for p in loaded["protocols"]}
    assert {
        "P0B012-FIXEDWING-GLIDER-V1",
        "P0C014-ROTORCRAFT-VTOL-V1",
        "P0D009-ADVERSE-WEATHER-V1",
        "P0D019-AUTONOMY-SITL-V1",
    } <= ids

    in_path = tmp_path / "fixed_wing_in.json"
    out_path = tmp_path / "fixed_wing_out.json"
    in_path.write_text(json.dumps({"wingspan_m": 1.8, "mass_kg": 1.8, "duration_s": 5.0}), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "fixed-wing-sim", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    fw_out = json.loads(out_path.read_text(encoding="utf-8"))
    assert fw_out["mission"]["aircraft_family"] == "fixed_wing"
    assert fw_out["mission"]["verdict"] == "NO_MODELED_LIMIT_BREACHED"
