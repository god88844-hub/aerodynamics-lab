"""Verify real downloaded external public open benchmarks across Fixed-Wing, Helicopter, VTOL, and Icing (DEVELOPMENT)."""

from __future__ import annotations

from physics.validation.public_benchmark_eval import evaluate_all_public_open_benchmarks


def test_public_open_benchmarks_across_all_families():
    report = evaluate_all_public_open_benchmarks()
    assert report["policy_role"] == "DEVELOPMENT"
    assert report["physical_acceptance_granted"] is False

    fw = report["airfoil360"]
    assert fw["sections"]["NACA 0012 Re=100K"]["n_points"] >= 10
    assert fw["overall_rmse_cl"] < 0.25

    ct = report["caradonna_tung"]
    assert ct["monotonic_collective_ct_trend"] is True
    assert len(ct["subsonic_points"]) == 3

    vtol = report["px4_vtol"]
    assert vtol["measured_transition_samples"] > 0
    assert vtol["measured_fw_max_airspeed_m_s"] > 20.0
    assert vtol["modeled_corridor_verdict"] == "NO_MODELED_LIMIT_BREACHED"

    ice = report["nasa_crm_icing"]
    assert ice["glaze_below_rime_trend_match"] is True
    assert len(ice["runs"]) == 3
