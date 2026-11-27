"""P0D-023: Application accessibility, equations/assumptions at decision point, evidence scorecard & help."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from desktop_worker.learning_experiments import EQUATIONS_AND_ASSUMPTIONS, build_fixed_wing_reference_library
from physics.validation.virtual_evidence_scorecard import compute_virtual_evidence_scorecard

ROOT = Path(__file__).resolve().parents[2]


def test_p0d_023_equations_evidence_scorecard_and_native_help_surface(tmp_path):
    assert len(EQUATIONS_AND_ASSUMPTIONS) >= 5
    for eq in EQUATIONS_AND_ASSUMPTIONS:
        assert eq["topic"] and eq["equation"] and eq["assumptions"]

    lib = build_fixed_wing_reference_library()
    assert lib["physical_acceptance_ready"] is False

    score = compute_virtual_evidence_scorecard(
        vehicle_family="multirotor",
        cpp_mass_kg=1.80,
        python_mass_kg=1.80,
        clearance_ok=True,
        mach=0.05,
        alpha_deg=4.0,
        benchmark_twin_percent=89.5,
    )
    assert score["overall_status"] == "DEVELOPMENT"
    assert score["numerical_verification"]["parity_pass"] is True
    assert score["benchmark_twin_percent"] == 89.5

    in_p = tmp_path / "score_in.json"
    out_p = tmp_path / "score_out.json"
    in_p.write_text(
        json.dumps({"vehicle_family": "fixed_wing", "cpp_mass_kg": 1.8, "python_mass_kg": 1.8, "has_custom_modified_part": True}),
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "evidence-scorecard", str(in_p), str(out_p)], check=True, cwd=ROOT)
    cli_score = json.loads(out_p.read_text(encoding="utf-8"))
    assert cli_score["overall_status"] == "UNVALIDATED_CUSTOM"

    menus_cpp = (ROOT / "apps" / "native" / "src" / "menus_and_panels.cpp").read_text(encoding="utf-8")
    assert "Equations" in menus_cpp and "Help" in menus_cpp
