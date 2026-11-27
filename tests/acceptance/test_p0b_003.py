"""P0B-003: Assemble fixed joints, datum transforms, distributed mass/inertia, and missing-material refusal."""

from __future__ import annotations

import json

import pytest

from geometry.fixed_wing_cad import ParametricWingSpec, assemble_fixed_wing_vehicle


def test_p0b_003_parallel_axis_datum_assembly_and_round_trip(tmp_path):
    wing_fwd = ParametricWingSpec(
        name="MainWing",
        wingspan_m=1.8,
        root_chord_m=0.26,
        tip_chord_m=0.14,
        material_density_kg_m3=110.0,
        density_source="EPS_CARBON_SPAR",
    )
    a1 = assemble_fixed_wing_vehicle(wing_fwd, fuselage_mass_kg=1.2, wing_attachment_m=(0.05, 0.0, 0.02))
    a2 = assemble_fixed_wing_vehicle(wing_fwd, fuselage_mass_kg=1.2, wing_attachment_m=(0.25, 0.0, 0.02))
    assert a2["center_of_mass_m"][0] > a1["center_of_mass_m"][0]
    assert a2["inertia_about_cog_kg_m2"][2][2] > a1["inertia_about_cog_kg_m2"][2][2]
    assert a1["mass_provenance_status"] == "DERIVED_FROM_DECLARED_DENSITY"

    saved = tmp_path / "assembly.json"
    saved.write_text(json.dumps(a1), encoding="utf-8")
    reloaded = json.loads(saved.read_text(encoding="utf-8"))
    assert reloaded["total_mass_kg"] == pytest.approx(a1["total_mass_kg"])


def test_p0b_003_missing_material_refusal():
    wing = ParametricWingSpec(name="NoDens", wingspan_m=1.5, root_chord_m=0.2, tip_chord_m=0.1)
    with pytest.raises(ValueError, match="Fail-closed"):
        assemble_fixed_wing_vehicle(wing, fuselage_mass_kg=1.0)
