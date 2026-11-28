"""P3-006 Acceptance Tests: CLI Failure Atlas & Electrophysics PowerPack Import."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_p3_006_cli_failure_atlas_and_powerpack(tmp_path: Path) -> None:
    dummy_in = tmp_path / "dummy.json"
    dummy_in.write_text("{}", encoding="utf-8")
    atlas_out = tmp_path / "atlas_out.json"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lab_project.py"), "failure-atlas", str(dummy_in), str(atlas_out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    atlas = json.loads(atlas_out.read_text(encoding="utf-8"))
    assert atlas["catalog_case_count"] == 10
    assert all(atlas["verified_fail_closed_checks"].values())

    pack_path = tmp_path / "powerpack.json"
    pack_path.write_text(
        json.dumps(
            {
                "component_id": "ep_lab_4s_5000",
                "cells_series": 4,
                "capacity_ah": 5.0,
                "internal_resistance_ohm": 0.014,
                "mass_kg": 0.48,
                "max_continuous_current_a": 95.0,
                "cutoff_cell_voltage_v": 3.25,
                "max_temperature_c": 65.0,
                "ocv_curve": [
                    {"soc_pct": 0.0, "cell_voltage_v": 3.25},
                    {"soc_pct": 100.0, "cell_voltage_v": 4.20},
                ],
                "validation_origin": "electrophysics_lab_v1",
            }
        ),
        encoding="utf-8",
    )
    pack_out = tmp_path / "powerpack_out.json"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "lab_project.py"), "load-powerpack", str(pack_path), str(pack_out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    pack = json.loads(pack_out.read_text(encoding="utf-8"))
    assert pack["id"] == "ep_lab_4s_5000" and pack["source"]["estimated"] is True
