"""P0C-001: Articulated helicopter rotor hubs, blades, swashplate constraints, mass/inertia & singular mechanism rejection."""

from __future__ import annotations

import pytest

from physics.aerodynamics.rotorcraft_vtol import HelicopterRotorAssemblySpec, author_helicopter_rotor_assembly


def test_p0c_001_articulated_rotor_assembly_inertia_and_provenance():
    spec = HelicopterRotorAssemblySpec(
        name="Articulated-2B",
        radius_m=0.72,
        root_cutout_m=0.10,
        chord_m=0.055,
        n_blades=2,
        hinge_offset_m=0.04,
        blade_mass_kg=0.18,
        density_source="CFRP_ROTOR_BLADE_SPEC",
    )
    out = author_helicopter_rotor_assembly(spec)
    assert out["blade_flapping_inertia_kg_m2"] > 0.0
    assert out["rotor_polar_inertia_kg_m2"] > out["blade_flapping_inertia_kg_m2"]
    assert len(out["assembly_sha256"]) == 64
    assert out["physical_validation_status"] == "UNVALIDATED"


def test_p0c_001_singular_and_missing_density_mechanisms_rejected():
    with pytest.raises(ValueError, match="blade count"):
        HelicopterRotorAssemblySpec(name="OneBlade", radius_m=0.7, root_cutout_m=0.1, chord_m=0.05, n_blades=1, blade_mass_kg=0.15, density_source="SPEC")
    with pytest.raises(ValueError, match="Singular/unsupported articulation"):
        HelicopterRotorAssemblySpec(name="BadHinge", radius_m=0.7, root_cutout_m=0.1, chord_m=0.05, hinge_offset_m=0.30, blade_mass_kg=0.15, density_source="SPEC")
    with pytest.raises(ValueError, match="Fail-closed"):
        HelicopterRotorAssemblySpec(name="NoDens", radius_m=0.7, root_cutout_m=0.1, chord_m=0.05)
