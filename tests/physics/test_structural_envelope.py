"""M10.7: analytical structural-load envelope verification, NOT physical validation."""
from pathlib import Path

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.structures.envelope import evaluate_load_envelope
from physics.structures.materials import MaterialProps


MATERIAL = MaterialProps(
    id="test", name="test material", density_kg_m3=1000,
    youngs_modulus_pa=10e9, yield_strength_pa=100e6,
    ultimate_tensile_strength_pa=120e6, source="analytic fixture",
    uncertainty_pct=0, notes="not real hardware",
)


def design():
    return DroneDesign.model_validate({
        "name": "structural_envelope_test",
        "parts": [{"name": "frame", "mass_kg": 1, "position_m": [0, 0, 0]}],
        "rotors": [
            {"position_m": [.25, .25, .02], "spin_direction": 1},
            {"position_m": [-.5, .0, .02], "spin_direction": -1},
        ],
        "frame": {"arm_length_m": .25, "tube_od_m": .012,
                  "tube_id_m": .010, "material_id": "test"},
    })


def eval_cases(cases):
    return evaluate_load_envelope(design(), cases, {"test": MATERIAL})


def test_governing_rotor_uses_own_load_and_span():
    result = eval_cases([("hover", [9, 4]), ("maneuver", [8, 12])])
    import math
    expected_span = .5
    expected_moment = 12 * expected_span
    assert result["governing"]["case"] == "maneuver"
    assert result["governing"]["rotor_index"] == 1
    assert result["governing"]["span_m"] == pytest.approx(expected_span)
    assert result["governing"]["root_bending_moment_n_m"] == pytest.approx(expected_moment)
    assert result["cases"][0]["rotors"][0]["span_m"] == pytest.approx(
        math.sqrt(.25**2 + .25**2)
    )
    assert result["material_source"] == "analytic fixture"


def test_zero_load_does_not_get_an_infinite_json_margin_or_false_pass():
    result = eval_cases([("zero", [0, 0])])
    assert result["verdict"] == "NO_APPLIED_LOAD"
    assert result["governing"] is None
    assert not result["all_declared_cases_below_allowable"]
    assert all(r["margin"] is None for r in result["cases"][0]["rotors"])


def test_stress_scales_linearly_with_force():
    a = eval_cases([("a", [3, 0])])["governing"]["bending_stress_pa"]
    b = eval_cases([("b", [6, 0])])["governing"]["bending_stress_pa"]
    assert b == pytest.approx(2 * a)


@pytest.mark.parametrize("cases", [
    [], [("x", [1])], [("x", [-1, 0])],
    [("x", [float("nan"), 0])], [("x", [float("inf"), 0])],
    [("x", [0, 0]), ("x", [1, 0])],
    [("", [1, 0])],
])
def test_invalid_cases_fail_closed(cases):
    with pytest.raises(ValueError):
        eval_cases(cases)


def test_unknown_material_is_not_a_pass():
    with pytest.raises(ValueError, match="unknown structural material"):
        evaluate_load_envelope(design(), [("x", [1, 1])], {})


def test_declared_cases_do_not_claim_physical_validation():
    result = eval_cases([("hover", [1, 1])])
    assert "physical validation" in " ".join(result["limitations"])
    assert result["verdict"] in ("ANALYTICAL_STATIC_SCREEN_ONLY",
                                 "EXCEEDS_DECLARED_ALLOWABLE")
