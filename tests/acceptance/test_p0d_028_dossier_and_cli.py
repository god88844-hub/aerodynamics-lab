"""P0D-028 & CLI verification: deterministic scientific dossier check + new 4-family/drawing/SITL CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_p0d_028_scientific_dossier_matches_repository():
    subprocess.run([sys.executable, str(ROOT / "scripts/build_scientific_dossier.py"), "--check"], check=True, cwd=ROOT)
    text = (ROOT / "docs" / "SCIENTIFIC_DOSSIER.md").read_text(encoding="utf-8")
    assert "P0B012-FIXEDWING-GLIDER-V1" in text
    assert "P0D019-AUTONOMY-SITL-V1" in text
    assert "UNVALIDATED / DEVELOPMENT" in text


def test_cli_extended_engineering_commands(tmp_path):
    svg = tmp_path / "plan.svg"
    dxf = tmp_path / "plan.dxf"
    jobs = [
        ("export-drawing", {"wingspan_m": 1.8, "svg_path": str(svg), "dxf_path": str(dxf)}, lambda d: svg.is_file() and dxf.is_file()),
        ("6dof-fixed-wing", {"wingspan_m": 1.8, "duration_s": 0.5}, lambda d: d["aircraft_family"] == "fixed_wing" and d["status"] == "completed"),
        ("autorotation-sim", {"flare_altitude_m": 8.0}, lambda d: d["aircraft_family"] == "helicopter" and d["verdict"] == "NO_MODELED_LIMIT_BREACHED"),
        ("sitl-mission", {"firmware_kind": "px4"}, lambda d: d["firmware_kind"] == "px4" and d["verdict"] == "NO_MODELED_LIMIT_BREACHED"),
    ]
    for cmd, body, check_fn in jobs:
        inp = tmp_path / f"{cmd}_in.json"
        out = tmp_path / f"{cmd}_out.json"
        inp.write_text(json.dumps(body), encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "scripts/lab_project.py"), cmd, str(inp), str(out)], check=True, cwd=ROOT)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert check_fn(data), f"Unexpected output for {cmd}: {data}"
