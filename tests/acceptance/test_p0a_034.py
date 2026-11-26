"""P0A-034: Guided learning workflow, equations/assumptions view, and reproducible saved experiments."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from aeroforge_schemas.project import import_legacy_project
from desktop_worker.learning_experiments import create_guided_experiment_bundle, save_and_reproduce_experiment

ROOT = Path(__file__).resolve().parents[2]
LEGACY_DESIGN = ROOT / "data" / "designs" / "quad_mn3508_6s.json"


def test_guided_experiment_save_reopen_reproduces_identical_telemetry(tmp_path):
    raw = json.loads(LEGACY_DESIGN.read_text(encoding="utf-8"))
    proj = import_legacy_project(raw)

    bundle = create_guided_experiment_bundle(
        proj,
        hypothesis="Adding a 3 m/s headwind and raising target altitude increases peak altitude and shifts horizontal trajectory.",
        target_altitude_m=3.2,
        hover_duration_s=0.3,
        wind_world_m_s=(3.0, 0.0, 0.0),
        seed=101,
    )
    assert len(bundle["equations_and_assumptions"]) >= 3
    assert bundle["comparison_summary"]["delta_max_altitude_m"] > 0.0
    assert bundle["physical_validation_status"] == "UNVALIDATED"

    saved_file = tmp_path / "guided_exp.json"
    receipt = save_and_reproduce_experiment(bundle, saved_file)
    assert receipt["exact_reproduction"] is True
    assert receipt["reproduced_telemetry_sha256"] == bundle["modified_telemetry_sha256"]


def test_blank_hypothesis_refused_and_cli_plus_ui_wired(tmp_path):
    raw = json.loads(LEGACY_DESIGN.read_text(encoding="utf-8"))
    proj = import_legacy_project(raw)

    with pytest.raises(ValueError, match="hypothesis"):
        create_guided_experiment_bundle(proj, hypothesis="   ")

    in_path = tmp_path / "learn_in.json"
    out_path = tmp_path / "learn_out.json"
    bundle_path = tmp_path / "saved_bundle.json"
    in_path.write_text(
        json.dumps(
            {
                "project": proj.model_dump(mode="json"),
                "hypothesis": "Higher target altitude increases peak altitude.",
                "target_altitude_m": 3.0,
                "save_bundle_path": str(bundle_path),
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "guided-experiment", str(in_path), str(out_path)],
        check=True,
        cwd=ROOT,
    )
    out = json.loads(out_path.read_text(encoding="utf-8"))
    assert out["reproduction_check"]["exact_reproduction"] is True

    gd = (ROOT / "apps/desktop/main.gd").read_text(encoding="utf-8")
    for token in ('"Learn / Invent"', "_open_learning_dialog", "_run_guided_experiment", "guided-experiment"):
        assert token in gd, token
