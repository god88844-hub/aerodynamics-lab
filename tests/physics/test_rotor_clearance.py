"""M28.1 synthetic planar geometry checks, not measured assembly validation."""
from pathlib import Path
import copy

import pytest

from aeroforge_schemas.design import DroneDesign
from physics.structures.rotor_clearance import evaluate_rotor_sweep_clearance

ROOT = Path(__file__).resolve().parents[2]


def reference():
    return DroneDesign.model_validate_json(
        (ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8")
    )


def run(design=None, diameters=None, tip_clearance=0):
    return evaluate_rotor_sweep_clearance(
        design or reference(),
        diameters if diameters is not None else [0.381] * 4,
        geometry_and_diameter_source="Synthetic geometry and installed diameter assumption, not measured",
        minimum_declared_tip_clearance_m=tip_clearance,
    )


def test_reference_quad_projected_clearance_is_analytical_only():
    d = reference()
    original = copy.deepcopy(d.model_dump())
    result = run(d)
    assert result["status"] == "ANALYTIC_PROJECTED_TIP_CLEARANCE_ONLY"
    assert result["screen_passed"] is True
    assert result["independently_measured_geometry_validated"] is False
    assert result["physical_interference_or_flightworthiness_established"] is False
    assert len(result["pairs"]) == 6
    # Adjacent rotors are 0.50 m apart in the reference, 15 in assumed diameter.
    assert result["minimum_observed_projected_tip_clearance_m"] == pytest.approx(0.119)
    assert d.model_dump() == original


def test_declared_minimum_clearance_enforced():
    result = run(tip_clearance=0.12)
    assert result["status"] == "INSUFFICIENT_DECLARED_PROJECTED_TIP_CLEARANCE"
    assert result["screen_passed"] is False


def test_overlap_and_contact_are_not_approved():
    result = run(diameters=[0.55] * 4)
    assert result["status"] == "PROJECTED_DISK_TOUCH_OR_OVERLAP_POTENTIAL"
    assert result["screen_passed"] is False
    assert any(p["projected_disk_touch_or_overlap"] for p in result["pairs"])
    result = run(diameters=[.5] * 4)
    assert result["screen_passed"] is False


def test_height_offset_does_not_silently_waive_projected_interference():
    d = reference()
    d.rotors[1].position_m = [d.rotors[1].position_m[0], d.rotors[1].position_m[1], 1.]
    report = run(d, diameters=[0.55] * 4)
    assert report["screen_passed"] is False
    assert any(pair["center_vertical_separation_m"] > 0 for pair in report["pairs"])


@pytest.mark.parametrize("bad", [0., -1., float("nan"), float("inf"), True, 1e308])
def test_invalid_or_overflowed_diameter_cannot_pass(bad):
    with pytest.raises(ValueError, match="diameter|overflow"):
        run(diameters=[bad] * 4)


def test_missing_geometry_and_dimensions_are_not_success():
    d = reference()
    with pytest.raises(ValueError, match="per rotor"):
        run(d, diameters=[0.381])
    with pytest.raises(ValueError, match="required"):
        evaluate_rotor_sweep_clearance(
            d, [0.381] * 4, geometry_and_diameter_source="",
        )


def test_bad_clearance_and_positions_rejected():
    with pytest.raises(ValueError, match="negative"):
        run(tip_clearance=-0.01)
    d = reference()
    d.rotors[0].position_m = [float("nan"), 0., 0.]
    with pytest.raises(ValueError, match="position"):
        run(d)
