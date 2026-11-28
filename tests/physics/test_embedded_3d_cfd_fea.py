"""Tests for Embedded 3D Surface/Volume Mesher, 3D Panel CFD & 3D Sparse C3D8 FEM Solver."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from physics.aerodynamics.embedded_3d_cfd_fea import run_embedded_3d_cfd_fea

ROOT = Path(__file__).resolve().parents[2]


def test_embedded_3d_cfd_fea_wing_pressure_stress_and_exports(tmp_path: Path) -> None:
    res = run_embedded_3d_cfd_fea(
        {
            "wingspan_m": 1.65,
            "root_chord_m": 0.28,
            "tip_chord_m": 0.16,
            "sweep_deg": 12.0,
            "airfoil_code": "2412",
            "airspeed_m_s": 24.0,
            "alpha_deg": 6.0,
            "total_mass_kg": 3.0,
            "mesh_resolution": "medium",
        },
        export_dir=tmp_path / "cfd_fea",
    )
    assert res["field_mode"] == "EMBEDDED_3D_PANEL_FVM_FEM"
    assert res["physical_validation_status"] == "UNVALIDATED_CUSTOM"
    assert res["n_fluid_cells"] == 22 * 16 * 14
    assert res["n_solid_elems"] == 64
    assert res["integrated_cl"] > 0.05
    assert res["peak_suction_cp"] < 0.0
    assert res["peak_von_mises_mpa"] > 0.0
    assert res["max_disp_mm"] >= 0.0
    assert res["structural_fos"] > 1.0
    assert len(res["panel_cp"]) == res["n_surface_tris"]
    assert len(res["panel_von_mises_mpa"]) == res["n_surface_tris"]
    assert len(res["streamlines_3d"]) == 9
    assert Path(res["exports"]["calculix_inp"]).is_file()
    assert Path(res["exports"]["vtk_polydata"]).is_file()
    assert (Path(res["exports"]["openfoam_dir"]) / "constant" / "polyMesh" / "points").is_file()


def test_embedded_3d_cfd_fea_compressibility_and_cli_roundtrip(tmp_path: Path) -> None:
    # Arbitrary tetrahedralized box + high-speed compressibility amplification + CLI check
    sub = run_embedded_3d_cfd_fea({"airspeed_m_s": 50.0, "mach": 0.15, "alpha_deg": 5.0})
    trans = run_embedded_3d_cfd_fea({"airspeed_m_s": 280.0, "mach": 0.82, "alpha_deg": 5.0})
    assert abs(trans["peak_suction_cp"]) > abs(sub["peak_suction_cp"])
    assert trans["peak_von_mises_mpa"] > sub["peak_von_mises_mpa"]

    in_p = tmp_path / "in.json"
    out_p = tmp_path / "out.json"
    field_p = tmp_path / "field.json"
    in_p.write_text(
        json.dumps(
            {
                "airspeed_m_s": 20.0,
                "alpha_deg": 5.5,
                "total_mass_kg": 2.4,
                "field_out_path": str(field_p),
                "export_dir": str(tmp_path / "exp"),
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/lab_project.py"), "embedded-cfd-fea", str(in_p), str(out_p)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
    assert field_p.is_file()
    data = json.loads(field_p.read_text(encoding="utf-8"))
    assert data["n_solid_elems"] == 64
