"""P0D-004: Repeatable terrain, obstacle, landing surface contact, and world authoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeroforge_schemas.project import import_legacy_project
from desktop_worker.environment_authoring import author_test_ground

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def test_p0d_004_world_terrain_obstacles_and_frame_enforcement():
    base = import_legacy_project(json.loads(LEGACY_DESIGN.read_text(encoding="utf-8")))
    authored = author_test_ground(
        base,
        {
            "units": "SI",
            "world_frame": "local_right_handed_z_up",
            "terrain_kind": "graded_pad",
            "landing_surfaces": [{"id": "pad_a", "center_m": [0.0, 0.0, 0.0], "size_m": [3.0, 3.0], "friction_coeff": 0.9}],
            "obstacles": [{"id": "pylon_1", "center_m": [5.0, 2.0, 1.5], "size_m": [1.0, 1.0, 3.0]}],
        },
    )
    ground = authored.experiment.parameters["test_ground"]
    assert ground["terrain_kind"] == "graded_pad"
    assert len(ground["obstacles"]) == 1

    with pytest.raises(ValueError):
        author_test_ground(base, {"world_frame": "ned_unsupported"})
