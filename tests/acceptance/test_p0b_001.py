"""P0B-001: Constrained 2D sketch and feature-history editing, overconstraints, broken refs, undo/redo, regeneration."""

from __future__ import annotations

import pytest

from geometry.fixed_wing_cad import ConstrainedSketch2D, FeatureHistoryStack
from geometry.part_designer import CustomPartRecipe, build_custom_part


def test_p0b_001_constrained_sketch_overconstraint_and_open_contour_refusal():
    sketch = ConstrainedSketch2D(
        name="rib_spar",
        width_m=0.08,
        height_m=0.05,
        thickness_m=0.02,
        area_constraint_m2=0.004,
        diagonal_constraint_m=(0.08**2 + 0.05**2) ** 0.5,
    )
    assert sketch.volume_m3() == pytest.approx(0.00008)

    with pytest.raises(ValueError, match="Overconstrained 2D sketch"):
        ConstrainedSketch2D(name="bad_area", width_m=0.08, height_m=0.05, thickness_m=0.02, area_constraint_m2=0.01)

    with pytest.raises(ValueError, match="Overconstrained 2D sketch"):
        ConstrainedSketch2D(name="bad_diag", width_m=0.08, height_m=0.05, thickness_m=0.02, diagonal_constraint_m=0.25)

    with pytest.raises(ValueError, match="Open 2D sketch"):
        ConstrainedSketch2D(name="open_prof", width_m=0.08, height_m=0.05, thickness_m=0.02, is_closed=False)


def test_p0b_001_feature_history_dependencies_undo_redo_and_regeneration(tmp_path):
    stack = FeatureHistoryStack()
    s1 = stack.add_feature("extrude", name="wing_box", params_m={"width_m": 0.2, "height_m": 0.04, "depth_m": 1.2})
    stack.add_feature("boolean_cut", name="weight_pocket", depends_on="wing_box", params_m={"width_m": 0.05, "height_m": 0.02, "depth_m": 0.8})

    with pytest.raises(ValueError, match="Broken feature reference"):
        stack.add_feature("extrude", name="orphan", depends_on="missing_parent", params_m={"width_m": 0.1, "height_m": 0.1, "depth_m": 0.1})

    with pytest.raises(ValueError, match="Broken feature reference"):
        stack.delete_feature("wing_box")

    regen = stack.regenerate({"wing_box": {"depth_m": 1.5}})
    assert regen["net_volume_m3"] > s1["net_volume_m3"]

    undo_snap = stack.undo()
    assert undo_snap["feature_count"] == 1
    redo_snap = stack.redo()
    assert redo_snap["feature_count"] == 2

    part = build_custom_part(
        CustomPartRecipe(part_name="WingRib", sketch_kind="rounded_plate", width_m=0.06, length_m=0.22, thickness_m=0.008, density_kg_m3=1450.0, density_source="CFRP_SPEC"),
        tmp_path / "custom_part",
    )
    assert part["mass_kg"] > 0.0
