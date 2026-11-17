"""M25.1 structural tests are analytical/synthetic, not physical coupon tests."""
from dataclasses import replace
from pathlib import Path
import copy
import math

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.structures.combined_metal import (
    evaluate_combined_metal_screen, von_mises_bending_torsion_pa,
)
from physics.structures.materials import load_materials

ROOT = Path(__file__).resolve().parents[2]


def resources():
    design = DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )
    materials = load_materials(ROOT / "data/components/materials.json")
    return design, materials


def metal_design():
    design, materials = resources()
    design.frame.material_id = "alu_6061_t6"
    return design, materials


def run(design=None, materials=None, forces=None, torques=None, safety_factor=1.5):
    if design is None or materials is None:
        design, materials = metal_design()
    return evaluate_combined_metal_screen(
        design, [
            ("synthetic_hover", forces if forces is not None else [5.] * 4,
             torques if torques is not None else [.1] * 4),
        ], materials, safety_factor=safety_factor,
        load_case_source="Synthetic forces/torques for mathematical verification only",
    )


def test_combined_stress_matches_analytic_von_mises_formula():
    assert von_mises_bending_torsion_pa(3., 4.) == pytest.approx(math.sqrt(57))
    assert von_mises_bending_torsion_pa(0., 4.) == pytest.approx(4 * math.sqrt(3))
    assert von_mises_bending_torsion_pa(3., 0.) == pytest.approx(3)
    assert von_mises_bending_torsion_pa(0., 0.) == 0


def test_ductile_aluminum_analytic_screen_never_grants_real_strength_validation():
    report = run()
    assert report["status"] == "ANALYTICAL_ISOTROPIC_STATIC_SCREEN_ONLY"
    assert report["screen_passed"] is True
    assert report["independent_structural_validation_established"] is False
    assert report["flightworthiness_established"] is False
    assert len(report["cases"][0]["rotors"]) == 4
    arm = report["cases"][0]["rotors"][0]
    assert arm["von_mises_pa"] == pytest.approx(
        math.hypot(arm["bending_normal_pa"], math.sqrt(3)*arm["torsional_shear_pa"])
    )
    assert report["allowable_pa"] == pytest.approx(
        report["material_nominal_yield_pa"] / 1.5
    )


def test_high_thrust_is_known_declared_static_failure():
    report = run(forces=[1e6] * 4, torques=[100.] * 4)
    assert report["status"] == "EXCEEDS_DECLARED_COMBINED_STATIC_ALLOWABLE"
    assert report["screen_passed"] is False
    assert all(x["below_declared_combined_allowable"] is False for x in report["cases"][0]["rotors"])


def test_unloaded_case_cannot_earn_strength_pass():
    report = run(forces=[0.] * 4, torques=[0.] * 4)
    assert report["status"] == "NO_NONZERO_DECLARED_LOAD"
    assert report["screen_passed"] is False
    assert all(x["static_margin_over_required_allowable"] is None for x in report["cases"][0]["rotors"])


def test_composite_and_printed_polymer_do_not_use_metal_von_mises_yield():
    design, mats = resources()
    assert design.frame.material_id == "cfrp_quasi_iso"
    out = run(design, mats)
    assert out["status"] == "UNSUPPORTED_MATERIAL_FAILURE_MODEL"
    assert out["screen_passed"] is False
    assert out["independent_structural_validation_established"] is False
    design.frame.material_id = "pa12_nylon"
    assert run(design, mats)["status"] == "UNSUPPORTED_MATERIAL_FAILURE_MODEL"


@pytest.mark.parametrize("args", [
    (float("nan"), 1.),
    (float("inf"), 1.),
    (-1., 0.),
    (1., float("nan")),
    (1e308, 1e308),
    (True, 1.),
])
def test_bad_combined_stresses_fail_closed(args):
    with pytest.raises(ValueError, match="finite|nonnegative|overflow"):
        von_mises_bending_torsion_pa(*args)


@pytest.mark.parametrize("safety", [0., -1., float("nan"), 11.])
def test_invalid_safety_factor_fails_closed(safety):
    with pytest.raises(ValueError, match="safety_factor"):
        run(safety_factor=safety)


def test_missing_torque_does_not_get_silently_assumed_zero():
    design, materials = metal_design()
    with pytest.raises(ValueError, match="requires explicit torque"):
        evaluate_combined_metal_screen(
            design, [("bad", [5.] * 4, None)], materials,
            safety_factor=1.5, load_case_source="synthetic",
        )


def test_nonfinite_material_allowable_or_uncertainty_is_rejected():
    design, materials = metal_design()
    materials["alu_6061_t6"] = replace(
        materials["alu_6061_t6"], uncertainty_pct=float("nan"),
    )
    with pytest.raises(ValueError, match="uncertainty"):
        run(design, materials)
    materials["alu_6061_t6"] = replace(
        materials["alu_6061_t6"], yield_strength_pa=float("inf"),
    )
    with pytest.raises(ValueError, match="yield"):
        run(design, materials)


def test_audit_is_read_only_for_materials_and_design():
    design, mats = metal_design()
    original = copy.deepcopy(design.model_dump())
    mat = copy.deepcopy(mats)
    run(design, mats)
    assert design.model_dump() == original
    assert mats == mat
