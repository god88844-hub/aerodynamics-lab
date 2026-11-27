"""P0B-020: Versioned fixed-wing reference projects, mission presets, and honest UNVALIDATED provenance."""

from __future__ import annotations

from desktop_worker.learning_experiments import build_fixed_wing_reference_library
from geometry.fixed_wing_cad import ParametricWingSpec
from physics.aerodynamics.fixed_wing import run_fixed_wing_mission


def test_p0b_020_fixed_wing_reference_library_versioned_and_never_physically_accepted():
    lib = build_fixed_wing_reference_library()
    assert lib["library_version"] == "0B.1"
    assert lib["physical_acceptance_ready"] is False
    assert len(lib["presets"]) >= 2

    for preset in lib["presets"]:
        assert preset["physical_validation_status"] == "UNVALIDATED"
        assert preset["source_license"]
        wing = ParametricWingSpec(
            name=preset["name"],
            wingspan_m=preset["wingspan_m"],
            root_chord_m=preset["root_chord_m"],
            tip_chord_m=preset["tip_chord_m"],
            airfoil_code=preset["airfoil_code"],
        )
        res = run_fixed_wing_mission(wing, mass_kg=preset["mass_kg"], duration_s=3.0)
        assert res["physical_validation_status"] == "UNVALIDATED"
