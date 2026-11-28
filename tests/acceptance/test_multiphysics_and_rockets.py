"""Acceptance Tests: Aeroacoustics, VRS/Precession, Cavitation, RF/RCS, Microburst/GPS, Rockets & CFD/FEA."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from physics.aerodynamics.aeroacoustics_and_vrs import (
    evaluate_helicopter_vrs_and_asymmetry,
    evaluate_hydro_cavitation,
    evaluate_rf_and_rcs,
    evaluate_rotor_and_jet_aeroacoustics,
)
from physics.aerodynamics.rockets_and_cfd import evaluate_multistage_rocket, export_and_run_detailed_cfd_fea
from physics.autonomy.sitl_and_swarms import evaluate_gps_multipath_and_distortion
from physics.environment.adverse_weather import evaluate_microburst_wind_shear

ROOT = Path(__file__).resolve().parents[2]


def test_aeroacoustics_vrs_cavitation_and_rf_stealth() -> None:
    ac_drone = evaluate_rotor_and_jet_aeroacoustics(rotor_count=4, blade_count=2, rotor_rpm=4800.0)
    assert ac_drone["bpf_hz"] == 160.0 and 55.0 < ac_drone["total_spl_dba"] < 90.0
    ac_sup = evaluate_rotor_and_jet_aeroacoustics(is_jet=True, jet_mach=1.40, altitude_m=1500.0)
    assert ac_sup["sonic_boom_pa"] > 0.0 and ac_sup["sonic_boom_psf"] > 0.0

    vrs = evaluate_helicopter_vrs_and_asymmetry(horizontal_speed_m_s=1.2, vertical_speed_m_s=-2.1)
    assert vrs["vrs_entered"] is True and vrs["verdict"] == "FAIL"
    ok_heli = evaluate_helicopter_vrs_and_asymmetry(horizontal_speed_m_s=15.0, vertical_speed_m_s=0.0)
    assert ok_heli["verdict"] == "NO_MODELED_LIMIT_BREACHED" and ok_heli["gyro_precession_torque_nm"] > 0.0

    cav = evaluate_hydro_cavitation(prop_rpm=16000.0)
    assert cav["cavitating"] is True and cav["verdict"] == "FAIL"

    rf_plain = evaluate_rf_and_rcs(sweep_deg=5.0, stealth_shaping=False)
    rf_stealth = evaluate_rf_and_rcs(sweep_deg=42.0, stealth_shaping=True)
    assert rf_plain["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert rf_stealth["rcs_dbsm"] < rf_plain["rcs_dbsm"]


def test_microburst_gps_multipath_rockets_and_cfd_cli(tmp_path: Path) -> None:
    mb = evaluate_microburst_wind_shear(radial_dist_m=100.0, altitude_m=20.0, peak_outflow_m_s=20.0)
    assert mb["severe_shear_alert"] is True and mb["verdict"] == "FAIL"
    gps = evaluate_gps_multipath_and_distortion(urban_obstruction_ratio=0.90)
    assert gps["verdict"] == "FAIL" and gps["channel_provenance"] == "SYNTHETIC"

    rocket = evaluate_multistage_rocket()
    assert rocket["orbit_capable"] is True and rocket["verdict"] == "NO_MODELED_LIMIT_BREACHED"
    assert rocket["tps_wall_temp_c"] < 1850.0 and rocket["knudsen_number"] > 0.0

    cfd = export_and_run_detailed_cfd_fea(
        project_name="TestJet", airspeed_m_s=45.0, wingspan_m=1.6, root_chord_m=0.3, mass_kg=3.0, output_dir=tmp_path
    )
    assert Path(cfd["calculix_deck"]).is_file() and (tmp_path / "openfoam_case" / "system" / "controlDict").is_file()

    for cmd in ("multiphysics-audit", "rocket-sim", "cfd-fea-export"):
        inp = tmp_path / f"{cmd}.json"
        out = tmp_path / f"{cmd}_out.json"
        inp.write_text(json.dumps({"name": "AuditCraft", "export_dir": str(tmp_path / cmd)}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "lab_project.py"), cmd, str(inp), str(out)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert out.is_file()
