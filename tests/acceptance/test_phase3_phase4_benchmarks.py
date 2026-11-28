"""Phase 3 & Phase 4 NASA Benchmark Verification Tests (NASA CRM, J85/F100, X-15A-2/STS, Saturn V)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from physics.aerodynamics.phase3_phase4_eval import evaluate_all_phase3_and_phase4_benchmarks

ROOT = Path(__file__).resolve().parents[2]


def test_phase3_phase4_nasa_benchmarks_match_and_gate_honestly() -> None:
    rep = evaluate_all_phase3_and_phase4_benchmarks()
    assert rep["policy_role"] == "DEVELOPMENT"
    assert rep["physical_acceptance_granted"] is False
    assert rep["nasa_crm"]["in_target_band"] is True
    assert 1.40 < rep["afterburners"]["j85_ab_ratio"] < 1.70
    assert 1.50 < rep["afterburners"]["f100_ab_ratio"] < 1.80
    assert rep["x15a2_thermal"]["exceeds_inconel_x"] is True
    assert rep["sts_reentry"]["within_rcc_limit"] is True
    assert rep["saturn_v"]["tli_capable"] is True


def test_cli_phase3_4_eval_command(tmp_path: Path) -> None:
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text("{}", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "lab_project.py"), "phase3-4-eval", str(inp), str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["saturn_v"]["net_delta_v_m_s"] > 11200.0
