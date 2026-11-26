"""P0A-024: Frozen run vs source measurement comparison, provenance export, and Dual Digital-Twin percentages."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from aeroforge_schemas.project import import_legacy_project
from desktop_worker.twin_comparison import (
    compare_frozen_run_and_source,
    compute_dual_digital_twin_metrics,
    export_labeled_comparison,
)
from physics.scenarios.desktop_runner import run_authoritative_desktop_simulation
from physics.scenarios.mission_authoring import author_mission

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def _frozen_hover_run():
    raw = json.loads(LEGACY_DESIGN.read_text(encoding="utf-8"))
    proj = import_legacy_project(raw)
    proj = author_mission(
        proj,
        {
            "controller_dt_s": 0.004,
            "seed": 7,
            "phases": [{"phase": "hover", "duration_s": 0.2, "target_altitude_m": 2.0}],
        },
    )
    return run_authoritative_desktop_simulation(proj)


def test_frozen_run_source_comparison_and_labeled_export(tmp_path):
    run = _frozen_hover_run()
    sim_t = run["result"]["telemetry"]["t"]
    # Source record uses exact tick timestamps for first 2 and an intermediate timestamp for the 3rd
    source_record = {
        "t_s": [sim_t[0], sim_t[10], 0.5 * (sim_t[10] + sim_t[11]), sim_t[20]],
        "values": [0.02, 0.25, 0.30, 0.55],
        "unit": "m",
        "frame": "NED",
        "measurement_uncertainty_abs": 0.02,
        "operating_envelope": {"altitude_m": [0.0, 5.0]},
    }
    comp = compare_frozen_run_and_source(run, source_record, channel="z", unit="m", tolerance_abs=1.0)
    assert comp["project_sha256"] == run["project_sha256"]
    assert comp["source_sha256"]
    assert comp["unit"] == "m"
    assert comp["frame"] == "NED"
    kinds = {s["calculated_channel_kind"] for s in comp["samples"]}
    assert "calculated" in kinds and "interpolated" in kinds
    assert all(s["measured_channel_kind"] == "measured" for s in comp["samples"])
    assert comp["dual_digital_twin"]["physical_evidence_match_pct"] is not None
    assert comp["dual_digital_twin"]["physical_validation_status"] == "DEVELOPMENT_COMPARISON_ONLY"

    out = export_labeled_comparison(comp, tmp_path / "comp.json", tmp_path / "comp.csv")
    assert Path(out["json_path"]).is_file() and Path(out["csv_path"]).is_file()
    with Path(out["csv_path"]).open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert {r["measured_channel_kind"] for r in rows} == {"measured"}
    assert "interpolated" in {r["sim_channel_kind"] for r in rows}


def test_dual_digital_twin_fail_and_unverified_gating():
    run = _frozen_hover_run()
    # Unmatched hardware without comparison surfaces UNVALIDATED physical evidence
    twin_no_src = compute_dual_digital_twin_metrics(run, comparison=None)
    assert twin_no_src["physical_evidence_match_pct"] is None
    assert twin_no_src["physical_validation_status"] == "UNVALIDATED"
    assert twin_no_src["design_pass_fail_probability_pct"] == 100.0

    # Any component limit breach latches PASS probability to 0.0%
    failed = dict(run, component_verdicts={"propulsion": "FAIL", "battery": "NO_MODELED_LIMIT_BREACHED"})
    twin_fail = compute_dual_digital_twin_metrics(failed)
    assert twin_fail["design_pass_fail_probability_pct"] == 0.0
    assert twin_fail["design_verdict"] == "FAIL"

    # Unverified parameter latches UNVERIFIED_ESTIMATE and None pass probability
    unver = dict(run, unverified_parameters=["custom_plate.density"])
    twin_unver = compute_dual_digital_twin_metrics(unver)
    assert twin_unver["design_pass_fail_probability_pct"] is None
    assert twin_unver["design_verdict"] == "UNVERIFIED_ESTIMATE"


def test_desktop_twin_ui_wiring():
    gd = (ROOT / "apps/desktop/main.gd").read_text(encoding="utf-8")
    for token in ('"Twin % / Compare"', "_open_twin_dialog", "dual_digital_twin", "UNVERIFIED_ESTIMATE"):
        assert token in gd, token
