"""P0C-021: Rotorcraft and VTOL guided learning and comparison workflows."""

from __future__ import annotations

import json

from desktop_worker.learning_experiments import EQUATIONS_AND_ASSUMPTIONS, create_rotorcraft_vtol_lesson_bundle


def test_p0c_021_rotorcraft_vtol_lesson_bundle_and_provenance(tmp_path):
    lesson = create_rotorcraft_vtol_lesson_bundle(
        hypothesis="In-ground-effect cushion amplifies thrust and collective flare arrests autorotation descent sink."
    )
    assert lesson["ige_thrust_gain_pct"] > 0.0
    assert lesson["autorotation_verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert lesson["physical_validation_status"] == "UNVALIDATED"
    assert any("cheeseman-bennett" in eq["topic"].lower() for eq in EQUATIONS_AND_ASSUMPTIONS)

    out = tmp_path / "rc_lesson.json"
    out.write_text(json.dumps(lesson), encoding="utf-8")
    assert json.loads(out.read_text(encoding="utf-8"))["ige_thrust_n"] == lesson["ige_thrust_n"]
