"""Verification suite for production physics algorithms, NACA airfoils, ISA-1976, Pitt-Peters, 6-DoF JSBSim, Thevenin 2-RC, ES-EKF, and SBOM."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from physics.aerodynamics.airfoil_polars import generate_airfoil_polar
from physics.aerodynamics.pitt_peters_inflow import run_pitt_peters_step_response
from physics.aerodynamics.sixdof_fixed_wing import (
    FixedWingAeroDerivatives,
    compute_fixed_wing_wrench_body,
    simulate_6dof_fixed_wing,
)
from physics.autonomy.ekf_estimator import run_ekf_fusion_verification
from physics.environment.isa_atmosphere import isa_atmosphere_1976
from physics.propulsion.thevenin_battery import Thevenin2RcParams, simulate_thevenin_2rc_discharge

ROOT = Path(__file__).resolve().parents[2]


def test_isa_1976_sea_level_tropopause_and_humidity_physics():
    sl = isa_atmosphere_1976(0.0)
    assert sl.temperature_k == pytest.approx(288.15, abs=1e-6)
    assert sl.pressure_pa == pytest.approx(101325.0, abs=1e-3)
    assert sl.density_kg_m3 == pytest.approx(1.225, abs=1e-3)
    assert sl.speed_of_sound_m_s == pytest.approx(340.294, abs=0.05)

    trop = isa_atmosphere_1976(11000.0)
    assert trop.temperature_k == pytest.approx(216.65, abs=1e-4)
    assert trop.pressure_pa == pytest.approx(22632.06, abs=5.0)

    # Moist air is slightly less dense than dry air at equal T and P
    humid = isa_atmosphere_1976(0.0, relative_humidity=0.9)
    assert humid.density_kg_m3 < sl.density_kg_m3


def test_clean_room_airfoil_polars_and_installed_airfoil_dat_catalog():
    sym = generate_airfoil_polar("0012", reynolds=5.0e5, alpha_range_deg=(-4.0, 8.0), step_deg=4.0)
    zero_row = [r for r in sym["rows"] if r["alpha_deg"] == 0.0][0]
    assert abs(zero_row["cl"]) < 1e-6

    cambered = generate_airfoil_polar("2412", reynolds=5.0e5, alpha_range_deg=(-4.0, 8.0), step_deg=4.0)
    cam_zero = [r for r in cambered["rows"] if r["alpha_deg"] == 0.0][0]
    assert cam_zero["cl"] > 0.15

    manifest_path = ROOT / "data/airfoils/airfoil_manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["airfoils"]) >= 3
    for item in manifest["airfoils"]:
        assert (ROOT / "data/airfoils" / item["filename"]).is_file()


def test_pitt_peters_inflow_6dof_fixed_wing_thevenin_2rc_and_ekf():
    pp_hover = run_pitt_peters_step_response(ct_step=0.008, advance_ratio_mu=0.0, omega_rad_s=160.0, duration_s=0.25)
    # In hover steady limit lambda_0 -> sqrt(CT / 2) ~ 0.0632
    assert pp_hover["final_inflow"][0] == pytest.approx(math.sqrt(0.008 / 2.0), abs=0.005)
    pp_fwd = run_pitt_peters_step_response(ct_step=0.008, advance_ratio_mu=0.12, omega_rad_s=160.0, duration_s=0.25)
    # Glauert forward-flight reduction decreases induced inflow lambda_0 (~0.0324)
    assert pp_fwd["final_inflow"][0] < pp_hover["final_inflow"][0]
    assert pp_fwd["step_count"] == 250

    fw = simulate_6dof_fixed_wing(duration_s=0.5, dt_s=0.01)
    assert fw["status"] == "completed"
    assert fw["final_position_m"][0] > 5.0

    # Post-stall (sinking at steep AoA w_zup = -8.0 -> alpha ~ +38.6 deg) fails closed
    aero = FixedWingAeroDerivatives(wing_area_m2=0.40, wingspan_m=1.8, mean_chord_m=0.22)
    with pytest.raises(ValueError, match="Post-stall"):
        compute_fixed_wing_wrench_body(
            aero, vel_body_m_s=np.array([10.0, 0.0, -8.0]), omega_body_rad_s=np.zeros(3), rho_kg_m3=1.225, controls={}
        )

    # 2-RC polarization shows immediate ohmic drop + progressive relaxation sag
    batt = simulate_thevenin_2rc_discharge(Thevenin2RcParams(), current_profile_a=[40.0] * 30, dt_s=0.5)
    assert batt["voltages_v"][0] > batt["voltages_v"][-1]
    assert batt["final_temp_c"] > 25.0

    # Thermal runaway limit triggers FAIL
    hot_batt = simulate_thevenin_2rc_discharge(
        Thevenin2RcParams(max_temp_c=40.0), current_profile_a=[120.0] * 60, dt_s=1.0, ambient_temp_c=39.5
    )
    assert hot_batt["status"] == "failed" and hot_batt["verdict"] == "FAIL"

    # EKF reduces mean position error well below raw GPS noise
    ekf_res = run_ekf_fusion_verification(seed=7, duration_s=3.0, dt_s=0.01)
    assert ekf_res["mean_ekf_err_m"] < ekf_res["mean_raw_gps_err_m"]


def test_sbom_exporter_covers_all_lockfiles(tmp_path):
    out = tmp_path / "sbom.json"
    subprocess.run([sys.executable, str(ROOT / "scripts/export_sbom.py"), "--output", str(out)], check=True, cwd=ROOT)
    sbom = json.loads(out.read_text(encoding="utf-8"))
    assert sbom["project_license"] == "Apache-2.0"
    assert sbom["counts"]["pypi_backend"] > 10
    assert sbom["counts"]["pypi_cad"] > 10
    assert sbom["counts"]["npm_web"] > 50
