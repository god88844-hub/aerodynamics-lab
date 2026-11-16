"""M10.8 analytical torsion and joint-capacity checks: verification only."""
import math

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.structures.advanced import (
    evaluate_advanced_envelope, tube_peak_torsional_shear_pa,
    tube_polar_second_moment_m4,
)
from physics.structures.beam import tube_second_moment
from physics.structures.materials import MaterialProps

MATERIAL = MaterialProps(
    id="test", name="analytic metal", density_kg_m3=1000,
    youngs_modulus_pa=10e9, yield_strength_pa=100e6,
    ultimate_tensile_strength_pa=120e6, source="test fixture",
    uncertainty_pct=0, notes="not physical validation",
)


def sample():
    return DroneDesign.model_validate({
        "name": "test_two_arm",
        "parts": [{"name": "frame", "mass_kg": 1.0, "position_m": [0, 0, 0]}],
        "rotors": [{"position_m": [.3, 0, 0]},
                   {"position_m": [0, .5, 0]}],
        "frame": {"arm_length_m": .3, "tube_od_m": .012,
                  "tube_id_m": .010, "material_id": "test"},
    })


def evaluate(cases, **kwargs):
    return evaluate_advanced_envelope(sample(), cases, {"test": MATERIAL}, **kwargs)


def test_circular_tube_polar_moment_is_twice_bending_moment():
    assert tube_polar_second_moment_m4(.012, .010) == pytest.approx(
        2 * tube_second_moment(.012, .010)
    )


def test_analytical_peak_shear_matches_hand_formula_and_torque_sign():
    j = math.pi / 32 * (.012**4 - .010**4)
    expected = 1.5 * .006 / j
    assert tube_peak_torsional_shear_pa(1.5, .012, .010) == pytest.approx(expected)
    assert tube_peak_torsional_shear_pa(-1.5, .012, .010) == pytest.approx(expected)
    assert tube_peak_torsional_shear_pa(0, .012, .010) == 0


def test_explicit_torque_and_joint_screens_have_auditable_margins():
    report = evaluate([("case", [2., 2.], [1., -2.])],
        shear_allowable_pa=90e6, shear_allowable_source="bench sample",
        joint_allowables={"bending_moment_n_m": 3.,
                          "axial_torque_n_m": 3., "evidence_source": "joint bench"})
    arms = report["cases"][0]["rotors"]
    assert arms[0]["root_bending_moment_n_m"] == pytest.approx(.6)
    assert arms[1]["root_bending_moment_n_m"] == pytest.approx(1.0)
    assert arms[1]["arm_axial_torque_n_m"] == pytest.approx(-2)
    assert arms[1]["joint_axial_torque_margin"] == pytest.approx(1.5)
    assert arms[1]["joint_bending_margin"] == pytest.approx(3)
    assert report["advanced_loads"]["joint_bending_screen"] is True
    assert report["advanced_loads"]["joint_axial_torque_screen"] is True
    assert report["advanced_loads"]["combined_interaction"] == "NOT_MODELED"
    assert report["advanced_loads"]["screening_verdict"] == "INCOMPLETE_EVIDENCE"


def test_missing_torque_is_unknown_not_zero():
    report = evaluate([("hover", [2., 2.], None)],
        shear_allowable_pa=90e6, shear_allowable_source="tested sample",
        joint_allowables={"bending_moment_n_m": 3., "axial_torque_n_m": 3.,
                          "evidence_source": "joint test"})
    a = report["cases"][0]["rotors"][0]
    assert a["arm_axial_torque_n_m"] is None
    assert a["tube_peak_shear_stress_pa"] is None
    assert a["tube_shear_margin"] is None
    assert report["advanced_loads"]["tube_torsion_screen"] is None
    assert report["advanced_loads"]["joint_axial_torque_screen"] is None


def test_zero_torque_is_not_claimed_as_torsion_strength_evidence():
    report = evaluate([("hover", [1., 1.], [0., 0.])],
        shear_allowable_pa=90e6, shear_allowable_source="tested sample")
    assert report["advanced_loads"]["tube_torsion_screen"] is None
    assert report["cases"][0]["rotors"][0]["tube_shear_margin"] is None


def test_known_joint_capacity_breach_is_reported_even_if_other_data_missing():
    report = evaluate([("hover", [2., 100.], None)],
        joint_allowables={"bending_moment_n_m": 1., "axial_torque_n_m": 2.,
                          "evidence_source": "test report"})
    assert report["advanced_loads"]["joint_bending_screen"] is False
    assert report["advanced_loads"]["screening_verdict"] == "EXCEEDS_DECLARED_LIMIT"


@pytest.mark.parametrize("torques", [[1.], [float("nan"), 1.],
                                     [float("inf"), 1.], ["bad", 1.]])
def test_bad_torque_data_fails_closed(torques):
    with pytest.raises(ValueError, match="axial torques"):
        evaluate([("case", [1., 1.], torques)])


@pytest.mark.parametrize("kwargs", [
    {"shear_allowable_pa": 50e6},
    {"shear_allowable_source": "missing value"},
    {"shear_allowable_pa": float("nan"), "shear_allowable_source": "source"},
    {"shear_allowable_pa": -1, "shear_allowable_source": "source"},
    {"shear_allowable_pa": 5e6, "shear_allowable_source": ""},
    {"joint_allowables": {"bending_moment_n_m": 0, "axial_torque_n_m": 1.,
                          "evidence_source": "test"}},
    {"joint_allowables": {"bending_moment_n_m": 2., "axial_torque_n_m": 1.,
                          "evidence_source": ""}},
])
def test_invalid_allowables_or_absent_provenance_rejected(kwargs):
    with pytest.raises(ValueError):
        evaluate([("case", [1., 1.], [1., 1.])], **kwargs)


def test_legacy_bending_result_unchanged_with_opt_in_feature():
    old = evaluate([("legacy", [1., 2.], None)])
    new = evaluate([("legacy", [1., 2.], [0.5, -0.5])])
    for a, b in zip(old["cases"][0]["rotors"], new["cases"][0]["rotors"]):
        for key in ("thrust_n", "span_m", "root_bending_moment_n_m",
                    "bending_stress_pa", "margin"):
            assert a[key] == b[key]
    assert old["advanced_loads"]["screening_verdict"] == "INCOMPLETE_EVIDENCE"
