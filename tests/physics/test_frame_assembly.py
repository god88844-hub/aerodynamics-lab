"""M10.5 schema and mass-property tests for anchored parts."""
import copy

import numpy as np
import pytest
from pydantic import ValidationError

from aeroforge_schemas.design import DroneDesign
from physics.dynamics.design_adapter import build_multirotor


BASE = {
    "name": "mount_test",
    "parts": [
        {"name": "frame", "mass_kg": 2.0, "position_m": [0, 0, 0],
         "inertia_about_own_cog_kg_m2": [[.02, 0, 0], [0, .03, 0], [0, 0, .04]]},
        {"name": "battery", "mass_kg": .5, "position_m": [0, 0, -.02]},
    ],
    "rotors": [{"position_m": [.2, .2, 0], "spin_direction": 1}],
    "frame": {
        "arm_length_m": .3, "tube_od_m": .012,
        "tube_id_m": .009, "material_id": "cfrp_quasi_iso",
        "plate_dimensions_m": [.2, .15, .025],
        "mount_points": [{"id": "mount_1", "position_m": [0, 0, -.02]}],
    },
}


def payload():
    return copy.deepcopy(BASE)


def test_mount_and_plate_roundtrip():
    data = payload()
    data["parts"][1]["mount_id"] = "mount_1"
    design = DroneDesign.model_validate(data)
    recovered = DroneDesign.model_validate_json(design.model_dump_json())
    assert recovered.parts[1].mount_id == "mount_1"
    assert recovered.frame.plate_dimensions_m == (.2, .15, .025)
    assert recovered.frame.mount_points[0].position_m == (0, 0, -.02)


@pytest.mark.parametrize("change", [
    lambda x: x["parts"][1].update({"mount_id": "missing"}),
    lambda x: x["parts"][1].update({"mount_id": "mount_1", "position_m": [0, 0, 0]}),
    lambda x: x["frame"]["mount_points"].append({"id": "mount_1", "position_m": [0, 0, 0]}),
    lambda x: x["frame"].update({"plate_dimensions_m": [0, .1, .1]}),
    lambda x: x["frame"].update({"tube_id_m": .015}),
])
def test_bad_mounts_and_invalid_tubes_rejected(change):
    data = payload()
    change(data)
    with pytest.raises(ValidationError):
        DroneDesign.model_validate(data)


def test_legacy_frame_without_mounts_remains_compatible():
    data = payload()
    data["frame"].pop("plate_dimensions_m")
    data["frame"].pop("mount_points")
    design = DroneDesign.model_validate(data)
    assert design.frame.mount_points == []
    assert design.frame.plate_dimensions_m is None


def test_moving_mount_and_attached_part_together_changes_assembly_cog():
    data = payload()
    data["parts"][1]["mount_id"] = "mount_1"
    _, old = build_multirotor(DroneDesign.model_validate(data))
    data["frame"]["mount_points"][0]["position_m"] = [.1, 0, -.02]
    data["parts"][1]["position_m"] = [.1, 0, -.02]
    _, new = build_multirotor(DroneDesign.model_validate(data))
    assert new.cog_m[0] - old.cog_m[0] == pytest.approx(.02)
    assert new.mass_kg == pytest.approx(old.mass_kg)


def test_visual_plate_does_not_replace_explicit_frame_inertia():
    data = payload()
    _, a = build_multirotor(DroneDesign.model_validate(data))
    data["frame"]["plate_dimensions_m"] = [.6, .6, .1]
    _, b = build_multirotor(DroneDesign.model_validate(data))
    np.testing.assert_allclose(a.inertia_about_cog, b.inertia_about_cog)
