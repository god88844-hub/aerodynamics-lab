"""M10.4 physical geometry model: dimensions, inertia and API design snapshot.

Uniform-density primitive inertias are analytical approximations, not measured
component inertia or evidence of aerodynamic/structural validity.
"""
import numpy as np
import pytest
from pydantic import ValidationError

from aeroforge_schemas.design import DroneDesign, PartInstance, PrimitiveGeometry
from geometry.primitives import box_inertia, cylinder_inertia_z
from physics.dynamics.design_adapter import build_multirotor


def example(part):
    return DroneDesign.model_validate({
        "name": "parametric_test",
        "parts": [part],
        "rotors": [{"position_m": [0.25, 0.25, 0.0]}],
    })


def test_box_dimensions_produce_own_cog_inertia():
    design = example({
        "name": "payload_1",
        "mass_kg": 2.0,
        "position_m": [0.0, 0.0, 0.0],
        "geometry": {"shape": "box", "dimensions_m": [0.4, 0.2, 0.1]},
    })
    _, props = build_multirotor(design)
    np.testing.assert_allclose(
        props.inertia_about_cog,
        box_inertia(2.0, 0.4, 0.2, 0.1),
        atol=1e-14,
    )


def test_cylinder_has_correct_axis_and_radius():
    design = example({
        "name": "payload_1",
        "mass_kg": 2.0,
        "position_m": [0, 0, 0],
        "geometry": {"shape": "cylinder", "dimensions_m": [0.2, 0.2, 0.6]},
    })
    _, props = build_multirotor(design)
    np.testing.assert_allclose(props.inertia_about_cog, cylinder_inertia_z(2, .1, .6))


@pytest.mark.parametrize("geometry", [
    {"shape": "box", "dimensions_m": [0, .1, .1]},
    {"shape": "box", "dimensions_m": [float("nan"), .1, .1]},
    {"shape": "cylinder", "dimensions_m": [.1, .2, .3]},
    {"shape": "sphere", "dimensions_m": [.1, .1, .1]},
    {"shape": "box", "dimensions_m": [-.1, .1, .1]},
])
def test_invalid_primitive_refused_by_pydantic(geometry):
    with pytest.raises(ValidationError):
        PrimitiveGeometry.model_validate(geometry)


def test_measured_inertia_not_overridden_by_primitive():
    known = [[.021, 0, 0], [0, .025, 0], [0, 0, .029]]
    design = example({
        "name": "battery", "mass_kg": 1.2, "position_m": [0, 0, 0],
        "geometry": {"shape": "box", "dimensions_m": [.5, .5, .5]},
        "inertia_about_own_cog_kg_m2": known,
    })
    _, props = build_multirotor(design)
    np.testing.assert_allclose(props.inertia_about_cog, known)


def test_geometry_roundtrips_through_snapshot_schema():
    payload = PartInstance(
        name="payload_1", mass_kg=.25, position_m=(0, 0, 0),
        geometry=PrimitiveGeometry(shape="cylinder", dimensions_m=(.1, .1, .3)),
    )
    recovered = PartInstance.model_validate_json(payload.model_dump_json())
    assert recovered.geometry == payload.geometry


def test_legacy_snapshot_remains_point_mass_when_geometry_missing():
    part = PartInstance(name="battery", mass_kg=.4, position_m=(.1, .1, 0))
    assert part.geometry is None
