"""P0B-004: Versioned CAD exchange, unit safety, SVG/DXF drawings, and STL-vs-exact protection."""

from __future__ import annotations

import pytest

from geometry.fixed_wing_cad import (
    ParametricWingSpec,
    export_2d_engineering_drawing_svg_dxf,
    export_cad_exchange_manifest,
    import_cad_exchange_manifest,
)


def test_p0b_004_cad_exchange_roundtrip_and_2d_drawing(tmp_path):
    wing = ParametricWingSpec(
        name="ExchangeWing",
        wingspan_m=1.6,
        root_chord_m=0.24,
        tip_chord_m=0.14,
        material_density_kg_m3=115.0,
        density_source="BALSA_SPAR",
    )
    step_manifest = export_cad_exchange_manifest(wing, unit_system="SI_METERS", exchange_format="STEP_AP214")
    imported = import_cad_exchange_manifest(step_manifest, require_exact=True)
    assert imported["wingspan_m"] == pytest.approx(1.6)
    assert step_manifest["authoritative_exact"] is True

    iges_manifest = export_cad_exchange_manifest(wing, unit_system="SI_METERS", exchange_format="IGES")
    assert import_cad_exchange_manifest(iges_manifest)["solid_volume_m3"] == pytest.approx(imported["solid_volume_m3"])

    drawing = export_2d_engineering_drawing_svg_dxf(
        wing,
        svg_path=tmp_path / "wing.svg",
        dxf_path=tmp_path / "wing.dxf",
    )
    assert len(drawing["outputs"]["svg"]["sha256"]) == 64
    assert len(drawing["outputs"]["dxf"]["sha256"]) == 64


def test_p0b_004_unit_mismatch_tamper_and_stl_exact_substitution_rejected():
    wing = ParametricWingSpec(name="GuardWing", wingspan_m=1.5, root_chord_m=0.22, tip_chord_m=0.12)
    with pytest.raises(ValueError, match="SI_METERS required"):
        export_cad_exchange_manifest(wing, unit_system="MM")

    with pytest.raises(ValueError, match="display meshes cannot replace authoritative exact"):
        export_cad_exchange_manifest(wing, exchange_format="STL", source_role="exact_geometry")

    stl_display = export_cad_exchange_manifest(wing, exchange_format="STL", source_role="display_mesh")
    with pytest.raises(ValueError, match="STL/display mesh cannot silently substitute"):
        import_cad_exchange_manifest(stl_display, require_exact=True)

    valid = export_cad_exchange_manifest(wing, exchange_format="STEP")
    valid["payload"]["wingspan_m"] = 9.9
    with pytest.raises(ValueError, match="SHA256 digest mismatch"):
        import_cad_exchange_manifest(valid)
