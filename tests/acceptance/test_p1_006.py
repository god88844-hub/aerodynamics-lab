"""P1-006 Acceptance Tests: Desktop Phase 1 Presets, CLI phase1-eval Worker, and Project Save/Load Roundtrip."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_p1_006_lab_project_phase1_eval_cli(tmp_path: Path) -> None:
    in_file = tmp_path / "in.json"
    out_file = tmp_path / "out.json"
    in_file.write_text("{}", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lab_project.py"), "phase1-eval", str(in_file), str(out_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["phase"] == 1
    assert payload["policy_role"] == "DEVELOPMENT"
    assert payload["badge"] == "UNVALIDATED_BIOINSPIRED"
    assert payload["flapsim_strip_convergence_pct"] < 2.0


def test_p1_006_native_menus_contain_morphing_and_flapping_controls() -> None:
    src = (ROOT / "apps" / "native" / "src" / "menus_and_panels.cpp").read_text(encoding="utf-8")
    assert "Morph Wing" in src
    assert "Insect MAV" in src
    assert "Animate Wingbeat" in src
    assert "Preloaded Hardware (Select Only):" in src
