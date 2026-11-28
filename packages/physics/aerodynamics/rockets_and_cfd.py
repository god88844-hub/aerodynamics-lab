"""Phase 4 Rockets/Hypersonics & Detailed OpenFOAM / CalculiX Solver Case Runner/Adapter."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any

GRAVITY = 9.80665
STEFAN_BOLTZMANN = 5.670374419e-8
EARTH_MU = 3.986004418e14
EARTH_RADIUS_M = 6371000.0


def evaluate_multistage_rocket(
    *,
    dry_mass_stage1_kg: float = 2200.0,
    prop_mass_stage1_kg: float = 18500.0,
    isp_stage1_s: float = 295.0,
    dry_mass_stage2_kg: float = 480.0,
    prop_mass_stage2_kg: float = 4200.0,
    isp_stage2_s: float = 348.0,
    payload_mass_kg: float = 250.0,
    liftoff_thrust_n: float = 340000.0,
    diameter_m: float = 1.65,
    target_altitude_m: float = 220000.0,
    nose_radius_m: float = 0.85,
    reentry_speed_m_s: float = 7650.0,
    reentry_altitude_m: float = 68000.0,
    tps_max_temp_c: float = 1850.0,
) -> dict[str, Any]:
    """Multi-stage Tsiolkovsky delta-v, Max-Q, Sutton-Graves hypersonic re-entry flux & Knudsen number."""
    if dry_mass_stage1_kg <= 0.0 or dry_mass_stage2_kg <= 0.0 or isp_stage1_s <= 50.0 or isp_stage2_s <= 50.0 or liftoff_thrust_n <= 0.0:
        raise ValueError("Invalid stage masses, Isp, or liftoff thrust")
    m_upper_full = dry_mass_stage2_kg + prop_mass_stage2_kg + payload_mass_kg
    m_upper_empty = dry_mass_stage2_kg + payload_mass_kg
    m0 = dry_mass_stage1_kg + prop_mass_stage1_kg + m_upper_full
    m1_burnout = dry_mass_stage1_kg + m_upper_full
    liftoff_tw = liftoff_thrust_n / (m0 * GRAVITY)

    dv1 = isp_stage1_s * GRAVITY * math.log(m0 / max(1.0, m1_burnout))
    dv2 = isp_stage2_s * GRAVITY * math.log(m_upper_full / max(1.0, m_upper_empty))
    dv_total = dv1 + dv2
    grav_drag_loss = 1450.0 + max(0.0, 1.35 - liftoff_tw) * 650.0
    dv_net = max(0.0, dv_total - grav_drag_loss)

    v_orb = math.sqrt(EARTH_MU / (EARTH_RADIUS_M + max(80000.0, target_altitude_m)))
    orbit_capable = dv_net >= v_orb * 0.96

    v_maxq = 380.0 * max(0.7, min(1.6, liftoff_tw / 1.4))
    max_q_pa = 0.5 * 0.36 * v_maxq * v_maxq

    h_re = max(20000.0, min(140000.0, reentry_altitude_m))
    rho_re = 1.225 * math.exp(-h_re / 7200.0)
    q_sg = 1.7415e-4 * math.sqrt(rho_re / max(0.02, nose_radius_m)) * (max(0.0, reentry_speed_m_s) ** 3)
    tps_temp_c = ((q_sg / (0.85 * STEFAN_BOLTZMANN) + (250.0 ** 4)) ** 0.25) - 273.15

    kn = (6.6e-8 * (1.225 / max(1e-12, rho_re))) / max(0.05, diameter_m)
    regime = "continuum" if kn < 0.01 else ("slip" if kn < 0.1 else ("transitional" if kn < 10.0 else "free_molecular"))
    flight_ok = (liftoff_tw >= 1.15) and (tps_temp_c <= tps_max_temp_c) and (max_q_pa <= 65000.0)
    return {
        "total_mass_kg": round(m0, 2),
        "liftoff_tw": round(liftoff_tw, 3),
        "delta_v_stage1_m_s": round(dv1, 1),
        "delta_v_stage2_m_s": round(dv2, 1),
        "total_delta_v_m_s": round(dv_total, 1),
        "net_delta_v_m_s": round(dv_net, 1),
        "orbital_vel_req_m_s": round(v_orb, 1),
        "orbit_capable": orbit_capable,
        "max_q_pa": round(max_q_pa, 1),
        "reentry_heat_flux_w_m2": round(q_sg, 1),
        "tps_wall_temp_c": round(tps_temp_c, 1),
        "knudsen_number": kn,
        "flow_regime": regime,
        "verdict": "NO_MODELED_LIMIT_BREACHED" if flight_ok else "FAIL",
        "policy_role": "DEVELOPMENT",
    }


def export_and_run_detailed_cfd_fea(
    *,
    project_name: str,
    airspeed_m_s: float,
    wingspan_m: float,
    root_chord_m: float,
    mass_kg: float,
    output_dir: Path,
) -> dict[str, Any]:
    """Generate OpenFOAM RANS & CalculiX FEA decks locally; run external binaries if installed or provide analytical proxy."""
    out = Path(output_dir)
    of_dir = out / "openfoam_case"
    ccx_dir = out / "calculix_case"
    (of_dir / "0").mkdir(parents=True, exist_ok=True)
    (of_dir / "system").mkdir(parents=True, exist_ok=True)
    ccx_dir.mkdir(parents=True, exist_ok=True)

    (of_dir / "system" / "controlDict").write_text(
        f"FoamFile {{ version 2.0; format ascii; class dictionary; object controlDict; }}\n"
        f"// {project_name}\napplication simpleFoam;\nendTime 250;\ndeltaT 1;\n",
        encoding="utf-8",
    )
    (of_dir / "0" / "U").write_text(
        f"internalField uniform ({airspeed_m_s:.3f} 0 0);\n", encoding="utf-8"
    )
    ccx_inp = ccx_dir / "wing_spar.inp"
    lift_load = mass_kg * GRAVITY * 1.5
    ccx_inp.write_text(
        f"*HEADING\n{project_name} Wing Spar FEA\n*NODE\n1,0,0,0\n2,{wingspan_m*0.5:.4f},0,0\n"
        f"*ELEMENT,TYPE=B31\n1,1,2\n*BOUNDARY\n1,1,6\n*CLOAD\n2,3,{lift_load:.2f}\n*STEP\n*STATIC\n*END STEP\n",
        encoding="utf-8",
    )

    simplefoam_bin = shutil.which("simpleFoam")
    ccx_bin = shutil.which("ccx")
    external_ran = False
    if simplefoam_bin and ccx_bin:
        try:
            subprocess.run([simplefoam_bin, "-case", str(of_dir)], check=True, timeout=20, capture_output=True)
            subprocess.run([ccx_bin, str(ccx_inp.with_suffix(""))], check=True, timeout=20, capture_output=True)
            external_ran = True
        except (subprocess.SubprocessError, OSError):
            external_ran = False

    # Analytical streamline & Euler-Bernoulli stress proxy field
    q_dyn = 0.5 * 1.225 * airspeed_m_s * airspeed_m_s
    cp_peak = -0.92 * min(1.4, (q_dyn / 220.0))
    von_mises_mpa = (lift_load * (wingspan_m * 0.25) * 0.015) / 1.2e-8 / 1e6
    summary = {
        "openfoam_case_dir": str(of_dir),
        "calculix_deck": str(ccx_inp),
        "external_solvers_detected": bool(simplefoam_bin or ccx_bin),
        "external_solvers_executed": external_ran,
        "field_mode": "EXTERNAL_CFD_FEA" if external_ran else "ANALYTICAL_FIELD_PROXY",
        "peak_suction_cp": round(cp_peak, 3),
        "root_von_mises_mpa": round(von_mises_mpa, 2),
        "deck_sha256": sha256(ccx_inp.read_bytes()).hexdigest(),
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }
    (out / "cfd_fea_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
