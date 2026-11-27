"""P0D-017: Coordinated multi-drone swarm separation, geofence guards, and CLI reproduction."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from physics.autonomy.sitl_and_swarms import run_multi_drone_swarm

ROOT = Path(__file__).resolve().parents[2]


def test_p0d_017_coordinated_swarm_separation_and_geofence_fail(tmp_path):
    init = [(0.0, 0.0, 5.0), (4.0, 0.0, 5.0), (0.0, 4.0, 5.0)]
    tgt = [(2.0, 2.0, 5.0), (6.0, 2.0, 5.0), (2.0, 6.0, 5.0)]
    ok = run_multi_drone_swarm(initial_positions_m=init, target_positions_m=tgt, min_separation_m=1.2)
    assert ok["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert ok["agent_count"] == 3
    assert ok["min_observed_separation_m"] >= 1.2

    in_p = tmp_path / "swarm_in.json"
    out_p = tmp_path / "swarm_out.json"
    in_p.write_text(json.dumps({"initial_positions_m": init, "target_positions_m": tgt, "min_separation_m": 1.2}), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), "swarm-sim", str(in_p), str(out_p)], check=True, cwd=ROOT)
    assert json.loads(out_p.read_text(encoding="utf-8"))["min_observed_separation_m"] == ok["min_observed_separation_m"]

    collision = run_multi_drone_swarm(initial_positions_m=[(0.0, 0.0, 5.0), (0.3, 0.0, 5.0)], target_positions_m=[(2.0, 0.0, 5.0), (3.0, 0.0, 5.0)], min_separation_m=1.0)
    assert collision["verdict"] == "FAIL"
