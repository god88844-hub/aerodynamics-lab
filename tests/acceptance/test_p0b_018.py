"""P0B-018: Teach fixed-wing design and reproducible comparative experiments."""

from __future__ import annotations

import json

from desktop_worker.learning_experiments import EQUATIONS_AND_ASSUMPTIONS, create_fixed_wing_lesson_bundle
from geometry.fixed_wing_cad import ParametricWingSpec


def test_p0b_018_fixed_wing_lesson_bundle_and_unvalidated_disclosure(tmp_path):
    wing = ParametricWingSpec(name="LessonWing", wingspan_m=1.6, root_chord_m=0.25, tip_chord_m=0.15, airfoil_code="2412")
    bundle = create_fixed_wing_lesson_bundle(
        wing,
        hypothesis="Stretching span at constant wing area lowers induced drag and raises L/D and mission range.",
    )
    assert bundle["modified_cruise_ld"] > bundle["baseline_cruise_ld"]
    assert bundle["modified_range_m"] > 100.0
    assert bundle["physical_validation_status"] == "UNVALIDATED"
    assert any("lifting-line" in eq["topic"].lower() for eq in EQUATIONS_AND_ASSUMPTIONS)

    out = tmp_path / "lesson_bundle.json"
    out.write_text(json.dumps(bundle), encoding="utf-8")
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded["bundle_sha256"] == bundle["bundle_sha256"]
