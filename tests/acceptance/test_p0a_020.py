"""P0A-020 acceptance tests: exact CAD datum-transform clearance checks,
LOD independence, revision re-evaluation, and analytical vs physical screening status.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from aeroforge_schemas.design import DroneDesign
from aeroforge_schemas.project import EngineeringProject
from geometry.clearance_checks import evaluate_assembly_clearance_and_loads

ROOT = Path(__file__).resolve().parents[2]
LAB_CAD_ANALYSIS = ROOT / "scripts" / "lab_cad_analysis.py"
ASSEMBLY_200 = ROOT / "data" / "benchmarks" / "assembly-200"


def test_known_clear_and_known_overlap_with_datum_transforms_and_lod_independence(tmp_path):
    proj_dir = tmp_path / "proj"
    shutil.copytree(ASSEMBLY_200, proj_dir)
    doc = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))
    node_id = doc["vehicle"]["nodes"][0]["id"]

    # Rotate first node 90 degrees about Z and translate to [1.0, 0.0, 0.0]
    s = math.sqrt(0.5)
    doc["vehicle"]["nodes"][0]["position_m"] = [1.0, 0.0, 0.0]
    doc["vehicle"]["nodes"][0]["orientation_wxyz"] = [s, 0.0, 0.0, s]
    project_path = proj_dir / "project.json"
    project_path.write_text(json.dumps(doc), encoding="utf-8")

    design = DroneDesign.model_validate_json((ROOT / "data/designs/quad_mn3508_6s.json").read_text(encoding="utf-8"))
    design.frame.material_id = "alu_6061_t6"

    # Known clear fixture through scripts/lab_cad_analysis.py --clearance
    clear_req = {
        "project": doc,
        "rotors": [
            {"node_id": node_id, "position_m": [0.25, 0.0, 0.0], "radius_m": 0.15},
            {"node_id": node_id, "position_m": [-0.25, 0.0, 0.0], "radius_m": 0.15},
        ],
        "obstacles": [{"id": "mast", "center_m": [1.0, 0.0, 0.0], "size_m": [0.1, 0.1, 0.4]}],
        "minimum_clearance_m": 0.02,
        "structural_design": design.model_dump(mode="json"),
        "load_cases": [["hover", [5.0, 5.0, 5.0, 5.0], [0.1, 0.1, 0.1, 0.1]]],
    }
    in_clear = tmp_path / "clear_req.json"
    out_clear = tmp_path / "clear_out.json"
    in_clear.write_text(json.dumps(clear_req), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(LAB_CAD_ANALYSIS), str(in_clear), str(out_clear), "--clearance", "--asset-root", str(proj_dir)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stderr
    res_clear = json.loads(out_clear.read_text(encoding="utf-8"))
    assert res_clear["clearance_passed"] is True
    assert res_clear["clearance_status"] == "CLEAR"
    assert res_clear["display_lod_used"] is False
    assert res_clear["minimum_observed_clearance_m"] == pytest.approx(0.05, abs=1e-9)
    assert res_clear["analytical_load_screen"]["independent_structural_validation_established"] is False
    assert res_clear["physical_validation_status"] == "ANALYTICAL_SCREEN_ONLY_NOT_PHYSICALLY_QUALIFIED"

    # Known overlap fixture (rotors moved closer) -> OVERLAP_OR_BELOW_MINIMUM
    overlap_req = {
        **clear_req,
        "rotors": [
            {"node_id": node_id, "position_m": [0.12, 0.0, 0.0], "radius_m": 0.15},
            {"node_id": node_id, "position_m": [-0.12, 0.0, 0.0], "radius_m": 0.15},
        ],
    }
    in_ov = tmp_path / "ov_req.json"
    out_ov = tmp_path / "ov_out.json"
    in_ov.write_text(json.dumps(overlap_req), encoding="utf-8")
    proc_ov = subprocess.run(
        [sys.executable, str(LAB_CAD_ANALYSIS), str(in_ov), str(out_ov), "--clearance", "--asset-root", str(proj_dir)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc_ov.returncode == 0, proc_ov.stderr
    res_ov = json.loads(out_ov.read_text(encoding="utf-8"))
    assert res_ov["clearance_passed"] is False
    assert res_ov["clearance_status"] == "OVERLAP_OR_BELOW_MINIMUM"
    assert res_ov["minimum_observed_clearance_m"] < 0.0

    # Display LOD / tessellation cannot alter clearance or load checks
    project_obj = EngineeringProject.model_validate(doc)
    display_asset = next(a for a in project_obj.assets if a.role == "display_mesh")
    (proj_dir / display_asset.path).write_text('{"corrupted_display_lod": true}', encoding="utf-8")
    direct = evaluate_assembly_clearance_and_loads(
        project_obj, proj_dir, rotors=clear_req["rotors"], obstacles=clear_req["obstacles"], minimum_clearance_m=0.02
    )
    assert direct["minimum_observed_clearance_m"] == pytest.approx(res_clear["minimum_observed_clearance_m"], abs=1e-12)
    assert direct["display_lod_used"] is False


def test_desktop_wires_clearance_check_entry_point():
    main_gd = (ROOT / "apps" / "desktop" / "main.gd").read_text(encoding="utf-8")
    assert "_run_clearance_check" in main_gd
    assert "--clearance" in main_gd
