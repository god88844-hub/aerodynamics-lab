"""P3-002 Acceptance Tests: Standard Fasteners, Micro-Turbines, Failure Atlas & Electrophysics Lab Bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from physics.dynamics.slung_load_and_tailsitter import (
    evaluate_failure_atlas_cases,
    import_electrophysics_powerpack,
    verify_iso_fastener_and_awg_harness,
)

ROOT = Path(__file__).resolve().parents[2]


def test_p3_002_standards_fasteners_turbines_and_awg_checks() -> None:
    screws = json.loads((ROOT / "data" / "components" / "fasteners" / "iso_4762_metric_screws.json").read_text(encoding="utf-8"))
    assert len(screws["screws"]) >= 8
    turbines = json.loads((ROOT / "data" / "components" / "turbines" / "micro_turbines_and_edfs.json").read_text(encoding="utf-8"))
    ids = {p["id"] for p in turbines["propulsors"]}
    assert {"kingtech_k45g4_plus", "jetcat_p100_rx", "fms_70mm_12b_6s_edf"} <= ids

    ok_joint = verify_iso_fastener_and_awg_harness(
        screw_id="m4x16_12_9", fasteners_per_joint=4, joint_shear_load_n=180.0, wire_awg=12, continuous_current_a=28.0
    )
    assert ok_joint["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    bad_wire = verify_iso_fastener_and_awg_harness(
        screw_id="m3x12_12_9", fasteners_per_joint=4, joint_shear_load_n=90.0, wire_awg=22, continuous_current_a=45.0
    )
    assert bad_wire["wire_ok"] is False and bad_wire["verdict"] == "FAIL"


def test_p3_002_electrophysics_bridge_and_failure_atlas() -> None:
    bat = import_electrophysics_powerpack(
        {
            "component_id": "ep_custom_6s_6000",
            "cells_series": 6,
            "capacity_ah": 6.0,
            "internal_resistance_ohm": 0.018,
            "mass_kg": 0.82,
            "max_continuous_current_a": 120.0,
            "cutoff_cell_voltage_v": 3.25,
            "max_temperature_c": 65.0,
            "ocv_curve": [{"soc_pct": 0.0, "cell_voltage_v": 3.25}, {"soc_pct": 100.0, "cell_voltage_v": 4.20}],
            "validation_origin": "electrophysics_lab_v1",
        }
    )
    assert bat.cells_series == 6 and bat.source.estimated is True

    with pytest.raises(ValueError, match="missing required fields"):
        import_electrophysics_powerpack({"component_id": "incomplete"})

    atlas = evaluate_failure_atlas_cases()
    assert atlas["catalog_case_count"] == 10
    assert all(atlas["verified_fail_closed_checks"].values())
