"""P0D-003: Guided and advanced invention/optimization sweeps preserving failed candidates across families."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from desktop_worker.learning_experiments import create_fixed_wing_lesson_bundle, create_rotorcraft_vtol_lesson_bundle
from geometry.fixed_wing_cad import ParametricWingSpec

ROOT = Path(__file__).resolve().parents[2]


def test_p0d_003_bounded_optimization_sweep_and_multi_family_invention(tmp_path):
    in_p = tmp_path / "sweep_in.json"
    out_p = tmp_path / "sweep_out.json"
    in_p.write_text(
        json.dumps(
            {
                "grid_spec": {
                    "battery_capacity_ah": [4.0, 12.0],
                    "rotor_count": [4],
                    "arm_length_m": [0.24, 0.32],
                    "payload_kg": [0.0, 5.0],
                }
            }
        ),
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "bounded-sweep", str(in_p), str(out_p)], check=True, cwd=ROOT)
    sweep = json.loads(out_p.read_text(encoding="utf-8"))
    # All candidates including failures/out-of-envelope remain visible
    assert sweep["total_candidates"] == 8
    assert sweep["infeasible_count"] >= 1
    assert sweep["feasible_count"] >= 1
    assert sweep["feasible_count"] + sweep["infeasible_count"] == 8

    fw = create_fixed_wing_lesson_bundle(
        ParametricWingSpec(name="OptWing", wingspan_m=1.7, root_chord_m=0.25, tip_chord_m=0.14),
        hypothesis="Higher aspect ratio raises fixed-wing cruise L/D.",
    )
    assert fw["modified_cruise_ld"] > fw["baseline_cruise_ld"]
    rc = create_rotorcraft_vtol_lesson_bundle(hypothesis="IGE boosts rotor thrust and flare arrests sink.")
    assert rc["ige_thrust_gain_pct"] > 0.0
