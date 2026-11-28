"""Open public external benchmark evaluators across Fixed-Wing, Helicopter Rotor, VTOL, and Icing (DEVELOPMENT)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from physics.aerodynamics.airfoil_polars import generate_airfoil_polar
from physics.aerodynamics.rotorcraft_vtol import run_vtol_transition_corridor, solve_helicopter_bemt_rotor
from physics.environment.adverse_weather import evaluate_icing_and_shedding

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_DIR = ROOT / "data" / "benchmarks" / "public"


def evaluate_airfoil360_benchmark() -> dict[str, Any]:
    """Compare clean-room NACA 0012 / 2412 Re=100k polars against Mendeley Airfoil 360 wind-tunnel data."""
    payload = json.loads((PUBLIC_DIR / "airfoil360_2022" / "airfoil360_naca_0012_2412.json").read_text(encoding="utf-8"))
    results: dict[str, Any] = {}
    all_cl_sq, all_cd_sq = [], []
    for code, key in (("0012", "NACA 0012 Re=100K"), ("2412", "NACA 2412 Re=100K")):
        pts = [r for r in payload["polars"][key] if 0.0 <= float(r["alpha_deg"]) <= 10.0]
        cl_errs, cd_errs = [], []
        for row in pts:
            aoa = float(row["alpha_deg"])
            pol = generate_airfoil_polar(code, reynolds=100_000.0, alpha_range_deg=(aoa - 0.1, aoa + 0.1), step_deg=0.1)
            pred = min(pol["rows"], key=lambda x: abs(x["alpha_deg"] - aoa))
            e_cl = pred["cl"] - float(row["cl"])
            e_cd = pred["cd"] - float(row["cd"])
            cl_errs.append(e_cl * e_cl)
            cd_errs.append(e_cd * e_cd)
        rmse_cl = math.sqrt(sum(cl_errs) / len(cl_errs))
        rmse_cd = math.sqrt(sum(cd_errs) / len(cd_errs))
        all_cl_sq.extend(cl_errs)
        all_cd_sq.extend(cd_errs)
        results[key] = {"n_points": len(pts), "rmse_cl": round(rmse_cl, 4), "rmse_cd": round(rmse_cd, 4)}
    overall_rmse_cl = math.sqrt(sum(all_cl_sq) / len(all_cl_sq))
    return {
        "benchmark_id": "mendeley_airfoil360_2022",
        "license": payload["license"],
        "policy_role": "DEVELOPMENT",
        "overall_rmse_cl": round(overall_rmse_cl, 4),
        "sections": results,
    }


def evaluate_caradonna_tung_rotor_benchmark() -> dict[str, Any]:
    """Compare subsonic BEMT + Prandtl tip-loss predictions against NASA TM-81232 Caradonna & Tung hover rotor."""
    payload = json.loads((PUBLIC_DIR / "caradonna_tung_1981" / "hover_performance.json").read_text(encoding="utf-8"))
    g = payload["geometry"]
    r_m = float(g["radius_m"])
    c_m = float(g["chord_m"])
    n_b = int(g["n_blades"])
    rho = 1.225
    area = math.pi * r_m * r_m
    comparisons = []
    for row in payload["rows"]:
        # Subsonic collective >= 5 deg rows inside BEMT envelope (skip M_tip > 0.70 transonic shock rows)
        if row["tip_mach"] <= 0.70 and row["collective_deg"] > 0.0:
            omega = row["rpm"] * 2.0 * math.pi / 60.0
            vtip = omega * r_m
            bemt = solve_helicopter_bemt_rotor(
                radius_m=r_m,
                root_cutout_m=0.10 * r_m,
                chord_m=c_m,
                n_blades=n_b,
                omega_rad_s=omega,
                collective_deg=row["collective_deg"],
                altitude_agl_m=20.0,
                rho_kg_m3=rho,
            )
            ct_pred = bemt["thrust_n"] / (rho * area * vtip * vtip)
            cp_pred = bemt["shaft_power_w"] / (rho * area * (vtip ** 3))
            comparisons.append(
                {
                    "collective_deg": row["collective_deg"],
                    "measured_ct": row["ct"],
                    "predicted_ct": round(ct_pred, 5),
                    "measured_cp": row["cp"],
                    "predicted_cp": round(cp_pred, 5),
                    "ct_rel_err": round(abs(ct_pred - row["ct"]) / row["ct"], 4),
                }
            )
    monotonic_ct = all(comparisons[i]["predicted_ct"] < comparisons[i + 1]["predicted_ct"] for i in range(len(comparisons) - 1))
    return {
        "benchmark_id": "nasa_caradonna_tung_1981",
        "license": payload["license"],
        "policy_role": "DEVELOPMENT",
        "monotonic_collective_ct_trend": monotonic_ct,
        "subsonic_points": comparisons,
    }


def evaluate_px4_vtol_transition_benchmark() -> dict[str, Any]:
    """Compare VTOL transition airspeed and bus voltage bounds against public PX4 Flight Review log 2572d282."""
    payload = json.loads((PUBLIC_DIR / "px4_vtol_2572d282" / "vtol_transition_summary.json").read_text(encoding="utf-8"))
    samples = payload["samples_1hz"]
    fw_samples = [s for s in samples if s["rw_mode"] == 0]
    trans_samples = [s for s in samples if s["in_transition"] == 1]
    meas_fw_max_v = max(s["true_airspeed_m_s"] for s in fw_samples)
    meas_v_min = min(s["voltage_v"] for s in samples if s["voltage_v"] > 0.0)
    corridor = run_vtol_transition_corridor(mass_kg=3.0, wing_area_m2=0.45, max_rotor_thrust_n=50.0, max_cruise_thrust_n=25.0)
    return {
        "benchmark_id": "px4_vtol_2572d282",
        "license": payload["license"],
        "policy_role": "DEVELOPMENT",
        "measured_transition_samples": len(trans_samples),
        "measured_fw_samples": len(fw_samples),
        "measured_fw_max_airspeed_m_s": round(meas_fw_max_v, 3),
        "measured_min_bus_voltage_v": round(meas_v_min, 3),
        "modeled_corridor_verdict": corridor["verdict"],
        "modeled_cruise_end_airspeed_m_s": corridor["samples"][-1]["airspeed_m_s"],
    }


def evaluate_nasa_crm_icing_benchmark() -> dict[str, Any]:
    """Compare glaze vs rime icing mass-scaling trend against NASA Glenn CRM IRT experimental runs."""
    payload = json.loads((PUBLIC_DIR / "nasa_crm_irt_icing" / "irt_midspan_ice_mass.json").read_text(encoding="utf-8"))
    comparisons = []
    for run in payload["runs"]:
        res = evaluate_icing_and_shedding(
            oat_c=run["oat_c"],
            lwc_g_m3=run["lwc_g_m3"],
            exposure_s=run["spray_time_min"] * 60.0,
            chord_m=0.80,
            airspeed_m_s=run["velocity_m_s"],
        )
        comparisons.append(
            {
                "run_id": run["run_id"],
                "oat_c": run["oat_c"],
                "measured_ice_mass_kg": run["measured_ice_mass_kg"],
                "modeled_uav_scale_ice_kg": round(res["accreted_mass_kg"], 4),
            }
        )
    by_id = {c["run_id"]: c for c in comparisons}
    # Warmer -1.4 C glaze run TH2464 accretes less ice than colder -23.8 C rime run TH2459 in both experiment & model
    glaze_below_rime_meas = by_id["TH2464"]["measured_ice_mass_kg"] < by_id["TH2459"]["measured_ice_mass_kg"]
    glaze_below_rime_model = by_id["TH2464"]["modeled_uav_scale_ice_kg"] < by_id["TH2459"]["modeled_uav_scale_ice_kg"]
    return {
        "benchmark_id": "nasa_crm_irt_icing",
        "license": payload["license"],
        "policy_role": "DEVELOPMENT",
        "glaze_below_rime_trend_match": glaze_below_rime_meas and glaze_below_rime_model,
        "runs": comparisons,
    }


def evaluate_all_public_open_benchmarks() -> dict[str, Any]:
    """Run all 4 real external public open benchmarks (DEVELOPMENT provenance only)."""
    return {
        "schema_version": "1.0",
        "policy_role": "DEVELOPMENT",
        "physical_acceptance_granted": False,
        "airfoil360": evaluate_airfoil360_benchmark(),
        "caradonna_tung": evaluate_caradonna_tung_rotor_benchmark(),
        "px4_vtol": evaluate_px4_vtol_transition_benchmark(),
        "nasa_crm_icing": evaluate_nasa_crm_icing_benchmark(),
    }
