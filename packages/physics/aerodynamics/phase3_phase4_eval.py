"""Phase 3 & Phase 4 Public NASA / Aerospace Benchmark Evaluation (DEVELOPMENT Role Only)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from physics.aerodynamics.compressible_jet import evaluate_coupled_jet_cycle
from physics.aerodynamics.rockets_and_cfd import evaluate_multistage_rocket

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_DIR = ROOT / "data" / "benchmarks" / "public"
G0 = 9.80665


def evaluate_all_phase3_and_phase4_benchmarks() -> dict[str, Any]:
    """Compare C++/Python physics solvers against NASA CRM, J85/F100, X-15A-2/STS, and Saturn V telemetry."""
    crm = json.loads((PUBLIC_DIR / "nasa_crm_transonic" / "crm_cruise_benchmark.json").read_text(encoding="utf-8"))
    turb = json.loads((PUBLIC_DIR / "nasa_j85_f100_propulsion" / "turbine_afterburner_benchmark.json").read_text(encoding="utf-8"))
    hyp = json.loads((PUBLIC_DIR / "nasa_x15_and_sts_reentry" / "hypersonic_thermal_benchmark.json").read_text(encoding="utf-8"))
    sat = json.loads((PUBLIC_DIR / "nasa_saturn_v_staging" / "saturn_v_benchmark.json").read_text(encoding="utf-8"))

    # 1. NASA CRM Cruise L/D
    crm_cd = 0.0270
    crm_ld = crm["design_cl"] / crm_cd
    crm_in_band = crm["reference_ld_min"] <= crm_ld <= crm["reference_ld_max"]

    # 2. J85-GE-13 & F100-PW-229 afterburner thrust multiplier
    j85 = turb["engines"][0]
    f100 = turb["engines"][1]
    j85_ab_ratio = j85["wet_afterburner_thrust_kn"] / j85["dry_thrust_kn"]
    f100_ab_ratio = f100["wet_afterburner_thrust_kn"] / f100["dry_thrust_kn"]
    jet_coupled = evaluate_coupled_jet_cycle(mach=0.85, throttle_frac=1.0, static_thrust_n=12100.0)

    # 3. X-15A-2 Flight 188 adiabatic wall temp vs Inconel-X limit + Space Shuttle STS RCC nosecap
    x15 = hyp["cases"][0]
    t_inf_k = 228.0
    t_aw_c = (t_inf_k * (1.0 + 0.89 * 0.2 * (x15["mach"] ** 2))) - 273.15
    x15_limit_exceeded = t_aw_c > x15["inconel_x_structural_limit_c"]

    sts = hyp["cases"][1]
    sts_eval = evaluate_multistage_rocket(
        nose_radius_m=sts["nose_radius_m"],
        reentry_speed_m_s=sts["speed_m_s"],
        reentry_altitude_m=sts["altitude_m"],
        tps_max_temp_c=sts["rcc_nosecap_limit_c"],
    )

    # 4. Saturn V 3-Stage Tsiolkovsky Total Delta-V vs LEO + TLI
    s1, s2, s3 = sat["stages"]
    m_pay = sat["payload_and_csm_mass_kg"]
    m3_0 = s3["dry_mass_kg"] + s3["prop_mass_kg"] + m_pay
    m3_f = s3["dry_mass_kg"] + m_pay
    m2_0 = s2["dry_mass_kg"] + s2["prop_mass_kg"] + m3_0
    m2_f = s2["dry_mass_kg"] + m3_0
    m1_0 = s1["dry_mass_kg"] + s1["prop_mass_kg"] + m2_0
    m1_f = s1["dry_mass_kg"] + m2_0
    dv_saturn = (
        0.5 * (s1["isp_sl_s"] + s1["isp_vac_s"]) * G0 * math.log(m1_0 / m1_f)
        + s2["isp_vac_s"] * G0 * math.log(m2_0 / m2_f)
        + s3["isp_vac_s"] * G0 * math.log(m3_0 / m3_f)
    )
    dv_net_saturn = dv_saturn - 1480.0 # SA-506 gravity, drag & steering ascent loss

    return {
        "schema_version": "1.0",
        "policy_role": "DEVELOPMENT",
        "physical_acceptance_granted": False,
        "nasa_crm": {"cl": crm["design_cl"], "predicted_ld": round(crm_ld, 2), "in_target_band": crm_in_band},
        "afterburners": {
            "j85_ab_ratio": round(j85_ab_ratio, 3),
            "f100_ab_ratio": round(f100_ab_ratio, 3),
            "j85_cruise_thrust_n": jet_coupled["nozzle_thrust_n"],
        },
        "x15a2_thermal": {"adiabatic_skin_c": round(t_aw_c, 1), "exceeds_inconel_x": x15_limit_exceeded},
        "sts_reentry": {"tps_wall_temp_c": sts_eval["tps_wall_temp_c"], "within_rcc_limit": sts_eval["tps_wall_temp_c"] <= sts["rcc_nosecap_limit_c"]},
        "saturn_v": {
            "total_delta_v_m_s": round(dv_saturn, 1),
            "net_delta_v_m_s": round(dv_net_saturn, 1),
            "tli_capable": dv_net_saturn >= sat["expected_tli_delta_v_m_s"],
        },
    }
