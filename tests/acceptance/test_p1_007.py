"""P1-007 Acceptance Tests: Joint Uncertainty Band & Honest UNVALIDATED_BIOINSPIRED Scoring."""

from __future__ import annotations

from physics.validation.phase1_dataset_eval import evaluate_all_phase1_datasets


def test_p1_007_dataset_eval_surfaces_uncertainty_and_honest_badges() -> None:
    report = evaluate_all_phase1_datasets()
    assert report["badge"] == "UNVALIDATED_BIOINSPIRED"
    assert report["physical_acceptance_granted"] is False
    assert report["joint_model_uncertainty_band_pct"] > 5.0
    assert report["compliant_flex_eval"]["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert report["pigeonbot_morph_eval"]["effective_span_m"] < 1.15
    assert report["savitsky_1964_planing"]["lift_rel_err"] < 0.02
