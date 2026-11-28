"""Jets, compressible transonic/supersonic aerodynamics, Modified Korn wave drag, and Brayton thrust lapse.

Benchmarked as DEVELOPMENT against NASA TMBWG Mach 1.63 Heated Jet and NASA TM-4074 NACA 0012.
Hardware engines/EDFs are selected from preloaded catalog specs (never invented electrochemistry).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_DIR = ROOT / "data" / "benchmarks" / "public"


@dataclass(frozen=True)
class PreloadedJetPropulsor:
    """Real catalog turbojet or EDF unit — selected by designers rather than invented."""

    id: str
    name: str
    kind: str  # "micro_turbojet" | "edf_electric"
    static_thrust_n: float
    mass_kg: float
    max_egt_c: float
    tsfc_kg_per_n_s: float  # 0.0 for electric EDF
    max_mach: float
    source: str


JET_PROPULSOR_CATALOG: dict[str, PreloadedJetPropulsor] = {
    "kingtech_k45g4": PreloadedJetPropulsor(
        id="kingtech_k45g4",
        name="KingTech K-45G4 Micro-Turbojet (45 N)",
        kind="micro_turbojet",
        static_thrust_n=45.0,
        mass_kg=0.72,
        max_egt_c=750.0,
        tsfc_kg_per_n_s=4.2e-5,
        max_mach=0.88,
        source="KingTech K-45G4 datasheet spec (UNVERIFIED_ESTIMATE for lapse)",
    ),
    "jetcat_p100rx": PreloadedJetPropulsor(
        id="jetcat_p100rx",
        name="JetCat P100-RX Micro-Turbojet (100 N)",
        kind="micro_turbojet",
        static_thrust_n=100.0,
        mass_kg=1.08,
        max_egt_c=780.0,
        tsfc_kg_per_n_s=3.9e-5,
        max_mach=0.95,
        source="JetCat P100-RX datasheet spec (UNVERIFIED_ESTIMATE for lapse)",
    ),
    "edf_70mm_12b_6s": PreloadedJetPropulsor(
        id="edf_70mm_12b_6s",
        name="70mm 12-Blade 6S Electric Ducted Fan (24 N)",
        kind="edf_electric",
        static_thrust_n=24.0,
        mass_kg=0.31,
        max_egt_c=95.0,
        tsfc_kg_per_n_s=0.0,
        max_mach=0.55,
        source="Freewing/FMS 70mm 6S EDF bench curve (UNVERIFIED_ESTIMATE for lapse)",
    ),
}


def compute_isa_atmosphere(altitude_m: float, oat_offset_c: float = 0.0) -> dict[str, float]:
    """Standard ISA troposphere/lower-stratosphere state [0..20,000 m]."""
    if not math.isfinite(altitude_m) or altitude_m < -500.0 or altitude_m > 20000.0:
        raise ValueError("altitude_m must be within [-500, 20000] m")
    if altitude_m <= 11000.0:
        t_k = 288.15 - 0.0065 * altitude_m + oat_offset_c
        p_pa = 101325.0 * ((288.15 - 0.0065 * altitude_m) / 288.15) ** 5.25588
    else:
        t_k = 216.65 + oat_offset_c
        p11 = 22632.1
        p_pa = p11 * math.exp(-9.80665 * (altitude_m - 11000.0) / (287.058 * 216.65))
    t_k = max(180.0, t_k)
    rho = p_pa / (287.058 * t_k)
    a_sound = math.sqrt(1.4 * 287.058 * t_k)
    return {"temperature_k": t_k, "pressure_pa": p_pa, "rho_kg_m3": rho, "speed_of_sound_m_s": a_sound}


def evaluate_compressible_wing(
    *,
    mach: float,
    cl_incompressible: float,
    cd0: float,
    aspect_ratio: float,
    sweep_deg: float,
    thickness_to_chord: float = 0.10,
    supercritical: bool = False,
) -> dict[str, Any]:
    """Karman-Tsien compressible lift + Modified Korn drag-divergence M_DD and cubic wave drag."""
    if not math.isfinite(mach) or mach < 0.0 or mach > 1.8:
        raise ValueError(f"Mach {mach:.3f} outside supported Phase 3 jet envelope [0.0, 1.8]")
    cos_sw = max(0.35, math.cos(math.radians(abs(sweep_deg))))
    m_perp = mach * cos_sw
    # Karman-Tsien capped safely below sonic singularity M_perp = 0.94
    m_sub = min(0.92, m_perp)
    beta = math.sqrt(max(0.08, 1.0 - m_sub * m_sub))
    kt_denom = beta + (m_sub * m_sub / (1.0 + beta)) * abs(cl_incompressible) * 0.5
    cl_comp = cl_incompressible / max(0.20, kt_denom)

    # Supersonic linear Ackeret blend above M > 1.05
    if mach > 1.05:
        beta_sup = math.sqrt(mach * mach - 1.0)
        cl_comp = min(abs(cl_comp), 4.0 * 0.12 / max(0.4, beta_sup)) * (1.0 if cl_incompressible >= 0 else -1.0)

    kappa_a = 0.95 if supercritical else 0.87
    m_dd = (kappa_a / cos_sw) - (thickness_to_chord / (cos_sw ** 2)) - (abs(cl_comp) / (10.0 * (cos_sw ** 3)))
    m_cr = max(0.40, m_dd - 0.108)
    cd_wave = 20.0 * ((mach - m_cr) ** 4) if mach > m_cr else 0.0
    if mach > 1.05:
        # Cap wave drag rise smoothly across sonic boom trough
        cd_wave = min(0.22, cd_wave)

    e_oswald = 0.82 * (0.90 if mach > m_cr else 1.0)
    cd_induced = (cl_comp * cl_comp) / (math.pi * max(1.5, aspect_ratio) * e_oswald)
    cd_total = cd0 + cd_induced + cd_wave
    return {
        "mach": mach,
        "m_perp": m_perp,
        "m_dd": m_dd,
        "m_cr": m_cr,
        "cl_compressible": cl_comp,
        "cd_wave": cd_wave,
        "cd_total": cd_total,
        "lift_to_drag": cl_comp / max(1e-5, cd_total),
    }


def evaluate_jet_flight_point(
    *,
    propulsor_id: str,
    mass_kg: float,
    wing_area_m2: float,
    aspect_ratio: float,
    sweep_deg: float,
    mach: float,
    altitude_m: float,
    alpha_deg: float,
    throttle_pct: float = 100.0,
    oat_offset_c: float = 0.0,
    thickness_to_chord: float = 0.09,
    q_flutter_limit_pa: float = 45000.0,
) -> dict[str, Any]:
    """Evaluate coupled compressible airframe + catalog Brayton turbine or EDF performance."""
    if propulsor_id not in JET_PROPULSOR_CATALOG:
        raise ValueError(f"Unknown preloaded jet propulsor {propulsor_id!r}; designers select from catalog")
    prop = JET_PROPULSOR_CATALOG[propulsor_id]
    isa = compute_isa_atmosphere(altitude_m, oat_offset_c=oat_offset_c)
    v_ms = mach * isa["speed_of_sound_m_s"]
    q_pa = 0.5 * isa["rho_kg_m3"] * v_ms * v_ms

    cl0 = 0.08 + ((2.0 * math.pi * aspect_ratio) / (aspect_ratio + 2.0)) * math.radians(alpha_deg) * 0.92
    aero = evaluate_compressible_wing(
        mach=mach,
        cl_incompressible=cl0,
        cd0=0.020,
        aspect_ratio=aspect_ratio,
        sweep_deg=sweep_deg,
        thickness_to_chord=thickness_to_chord,
    )
    lift_n = q_pa * wing_area_m2 * aero["cl_compressible"]
    drag_n = q_pa * wing_area_m2 * aero["cd_total"]

    # Brayton thrust lapse & temperature rise
    sigma = isa["rho_kg_m3"] / 1.225
    th_frac = max(0.0, min(1.05, throttle_pct / 100.0))
    if prop.kind == "micro_turbojet":
        # Micro-turbojet net thrust slightly recovers with ram below M=0.9, lapses strongly with density sigma^0.85
        ram_factor = 1.0 + 0.14 * mach * mach - 0.18 * max(0.0, mach - 0.85)
        thrust_n = prop.static_thrust_n * (sigma ** 0.85) * ram_factor * th_frac
        egt_c = 280.0 + 440.0 * (th_frac ** 1.25) + 0.5 * oat_offset_c + 65.0 * max(0.0, altitude_m / 8000.0)
    else:
        # EDF loses net thrust with forward flight speed as jet-to-airspeed momentum delta drops
        v_eff = max(0.0, 1.0 - 0.55 * mach)
        thrust_n = prop.static_thrust_n * sigma * v_eff * (th_frac ** 1.35)
        egt_c = 25.0 + oat_offset_c + 62.0 * (th_frac ** 1.6)

    mach_fail = mach > prop.max_mach
    egt_fail = egt_c > prop.max_egt_c
    flutter_fail = q_pa > q_flutter_limit_pa
    stall_fail = abs(alpha_deg) > 13.5
    verdict = "FAIL" if (mach_fail or egt_fail or flutter_fail or stall_fail) else "NO_MODELED_LIMIT_BREACHED"
    return {
        "propulsor_id": prop.id,
        "propulsor_name": prop.name,
        "mach": mach,
        "airspeed_m_s": v_ms,
        "dynamic_pressure_pa": q_pa,
        "rho_kg_m3": isa["rho_kg_m3"],
        "lift_n": lift_n,
        "drag_n": drag_n,
        "net_thrust_n": thrust_n,
        "thrust_to_drag": thrust_n / max(0.1, drag_n),
        "thrust_to_weight": thrust_n / max(0.5, mass_kg * 9.80665),
        "m_dd": aero["m_dd"],
        "cd_wave": aero["cd_wave"],
        "egt_or_temp_c": egt_c,
        "verdict": verdict,
        "cycle_evidence_status": "CALCULATED_CYCLE_DEVELOPMENT",
    }


def evaluate_jet_benchmarks() -> dict[str, Any]:
    """Verify ingested NASA M1.63 Heated Jet Nozzle and NASA TM-4074 Ladson NACA 0012 benchmarks."""
    jet = json.loads((PUBLIC_DIR / "nasa_jet_m1p63_heated" / "jet_nozzle_benchmark.json").read_text(encoding="utf-8"))
    lad = json.loads((PUBLIC_DIR / "nasa_tm4074_ladson_naca0012" / "ladson_naca0012_benchmark.json").read_text(encoding="utf-8"))
    decay_rows = jet["heated_centerline_decay"]
    monotone_decay = decay_rows[0]["norm_temp_decay"] > decay_rows[-1]["norm_temp_decay"]

    # Check NACA 0012 attached slope (alpha in [0, 10 deg]) against Prandtl-Glauert M=0.15
    sub_rows = [r for r in lad["rows_80grit"] if 0.0 <= r["alpha_deg"] <= 10.5]
    sq_errs = []
    for r in sub_rows:
        cl_inc = 2.0 * math.pi * math.radians(r["alpha_deg"]) * 0.99
        pred = evaluate_compressible_wing(mach=0.15, cl_incompressible=cl_inc, cd0=0.0081, aspect_ratio=100.0, sweep_deg=0.0)
        e = pred["cl_compressible"] - r["cl"]
        sq_errs.append(e * e)
    return {
        "nasa_jet_m1p63": {
            "rows_decay": len(decay_rows),
            "shock_rows": len(jet["offdesign_shock_cell_sample"]),
            "monotone_plume_decay": monotone_decay,
            "policy_role": "DEVELOPMENT",
        },
        "nasa_tm4074_ladson": {
            "n_attached": len(sub_rows),
            "rmse_cl": round(math.sqrt(sum(sq_errs) / len(sq_errs)), 4),
            "policy_role": "DEVELOPMENT",
        },
    }


def compute_mil_e_5008b_inlet_recovery(mach: float) -> float:
    """Return MIL-E-5008B inlet total-pressure recovery factor eta_r(M)."""
    m = max(0.0, float(mach))
    if m <= 1.0:
        return 0.985 - 0.015 * m * m
    return max(0.45, 1.0 - 0.075 * ((m - 1.0) ** 1.35))


def compute_isentropic_cd_nozzle(
    pt_pa: float,
    tt_k: float,
    throat_area_m2: float,
    exit_area_m2: float,
    ambient_p_pa: float,
    mach_flight: float = 0.0,
    gamma: float = 1.4,
    gas_r: float = 287.058,
) -> dict[str, float | bool]:
    """Compute choked/isentropic convergent-divergent nozzle mass flow & thrust factor."""
    if pt_pa <= 0.0 or tt_k <= 0.0 or throat_area_m2 <= 0.0 or exit_area_m2 <= 0.0 or ambient_p_pa <= 0.0:
        raise ValueError("Nozzle inputs must be strictly positive")
    choked_crit_ratio = ((gamma + 1.0) / 2.0) ** (gamma / (gamma - 1.0))
    npr = pt_pa / ambient_p_pa
    choked = npr >= choked_crit_ratio
    if choked:
        mass_flow_coeff = math.sqrt(gamma / gas_r) * (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (2.0 * (gamma - 1.0)))
        mdot_kg_s = (pt_pa * throat_area_m2 / math.sqrt(tt_k)) * mass_flow_coeff
    else:
        pr = min(0.9999, ambient_p_pa / pt_pa)
        term = max(0.0, pr ** (2.0 / gamma) - pr ** ((gamma + 1.0) / gamma))
        mdot_kg_s = (pt_pa * throat_area_m2 / math.sqrt(tt_k)) * math.sqrt((2.0 * gamma) / (gas_r * (gamma - 1.0)) * term)
    area_ratio = exit_area_m2 / throat_area_m2
    ideal_ratio = 1.0 + 0.35 * max(0.0, mach_flight)
    expansion_eff = max(0.55, 1.0 - 0.18 * ((area_ratio - ideal_ratio) ** 2))
    return {
        "npr": round(npr, 4),
        "choked": choked,
        "mdot_kg_s": round(mdot_kg_s, 5),
        "area_ratio": round(area_ratio, 4),
        "expansion_efficiency": round(expansion_eff, 4),
    }


def evaluate_coupled_jet_cycle(
    mach: float = 0.30,
    altitude_m: float = 0.0,
    oat_c: float = 25.0,
    wing_area_m2: float = 0.35,
    sweep_deg: float = 26.0,
    wing_tc_ratio: float = 0.09,
    cl_incomp: float = 0.25,
    intake_area_m2: float = 0.0032,
    nozzle_area_ratio: float = 1.15,
    throttle_frac: float = 0.85,
    static_thrust_n: float = 44.15,
    max_egt_c: float = 720.0,
    max_mach: float = 1.65,
    fuel_mass_kg: float = 0.85,
    fuel_flow_max_kg_min: float = 0.150,
    cooling_grade: int = 1,
    mfg_tolerance_frac: float = 0.05,
    is_turbine: bool = True,
) -> dict[str, float | bool | str]:
    """Evaluate coupled intake + Brayton/EDF nozzle + Korn wave drag jet state."""
    if mach < 0.0 or wing_area_m2 <= 0.0 or intake_area_m2 <= 0.0 or static_thrust_n <= 0.0:
        raise ValueError("Invalid coupled jet parameters")
    alt = max(0.0, min(20000.0, float(altitude_m)))
    t_k = max(216.65, 273.15 + oat_c - 0.0065 * alt)
    p_atm = 101325.0 * ((1.0 - (0.0065 * alt) / 288.15) ** 5.25588)
    rho = p_atm / (287.058 * t_k)
    a_sound = math.sqrt(1.4 * 287.058 * t_k)
    v0 = mach * a_sound
    q = 0.5 * rho * v0 * v0
    tol_factor = max(0.65, min(1.0, 1.0 - mfg_tolerance_frac))

    eta_r = compute_mil_e_5008b_inlet_recovery(mach)
    capture_ratio = max(0.35, min(3.0, intake_area_m2 / 0.0032))
    spillage_cd = 0.004 * (capture_ratio - 1.25) if capture_ratio > 1.25 else 0.0
    throat_choke_factor = min(1.0, capture_ratio / 0.65)

    cos_sw = max(0.35, math.cos(abs(sweep_deg) * math.pi / 180.0))
    mach_dd = (0.87 / cos_sw) - (max(0.04, min(0.18, wing_tc_ratio)) / (cos_sw * cos_sw)) - (
        abs(cl_incomp) / (10.0 * (cos_sw ** 3))
    )
    m_cr = max(0.40, mach_dd - 0.108)
    if mach <= 1.0:
        cd_wave = min(0.18, 20.0 * ((mach - m_cr) ** 4)) if mach > m_cr else 0.0
    else:
        cd_wave = min(0.24, 0.085 / math.sqrt(max(0.15, mach * mach - 1.0 + 0.18)))
    mach_cone_deg = math.degrees(math.asin(1.0 / mach)) if mach > 1.001 else 90.0

    sigma = rho / 1.225
    th = max(0.0, min(1.08, throttle_frac))
    pt_pa = p_atm * (1.0 + 0.2 * mach * mach) ** 3.5 * eta_r * (1.0 + 2.2 * th)
    tt_k = t_k + (620.0 * th if is_turbine else 45.0 * th)
    throat_area = intake_area_m2 * 0.72
    nozzle = compute_isentropic_cd_nozzle(
        pt_pa=pt_pa,
        tt_k=tt_k,
        throat_area_m2=throat_area,
        exit_area_m2=throat_area * max(0.7, min(2.2, nozzle_area_ratio)),
        ambient_p_pa=p_atm,
        mach_flight=mach,
    )
    exp_eff = float(nozzle["expansion_efficiency"])

    if is_turbine:
        ram_mult = 1.0 + 0.14 * min(mach * mach, 1.8)
        thrust_n = static_thrust_n * (sigma ** 0.85) * eta_r * throat_choke_factor * ram_mult * exp_eff * th * tol_factor
        mdot_fuel = max(0.01, fuel_flow_max_kg_min * (0.20 + 0.80 * th) / max(0.55, eta_r))
        endurance_min = (fuel_mass_kg * tol_factor) / mdot_fuel
        egt_c = 280.0 + 435.0 * (th ** 1.25) + 0.5 * oat_c + 65.0 * alt / 8000.0 + (
            48.0 if cooling_grade == 0 else 0.0
        ) + (65.0 if throat_choke_factor < 0.90 else 0.0)
    else:
        thrust_n = static_thrust_n * sigma * eta_r * throat_choke_factor * max(0.05, 1.0 - 0.52 * mach) * exp_eff * (
            th ** 1.35
        ) * tol_factor
        endurance_min = 7.0 / max(0.15, th)
        egt_c = oat_c + 58.0 * (th ** 1.6) + (18.0 if cooling_grade == 0 else 0.0)

    cd_total = 0.020 + spillage_cd + cd_wave + (cl_incomp * cl_incomp) / (math.pi * 5.2 * 0.82)
    total_drag_n = q * wing_area_m2 * cd_total
    egt_ok = egt_c <= max_egt_c
    mach_ok = mach <= max_mach
    thrust_ok = thrust_n >= total_drag_n * 0.95
    verdict = "NO_MODELED_LIMIT_BREACHED" if (egt_ok and mach_ok and thrust_ok) else "FAIL"
    return {
        "inlet_recovery_eta": round(eta_r, 4),
        "spillage_cd": round(spillage_cd, 5),
        "nozzle_thrust_n": round(thrust_n, 3),
        "nozzle_npr": nozzle["npr"],
        "nozzle_choked": nozzle["choked"],
        "mdot_kg_s": nozzle["mdot_kg_s"],
        "egt_c": round(egt_c, 2),
        "mach_dd": round(mach_dd, 4),
        "cd_wave": round(cd_wave, 5),
        "mach_cone_half_angle_deg": round(mach_cone_deg, 2),
        "fuel_endurance_min": round(endurance_min, 2),
        "total_drag_n": round(total_drag_n, 3),
        "egt_ok": egt_ok,
        "mach_ok": mach_ok,
        "thrust_ok": thrust_ok,
        "verdict": verdict,
        "policy_role": "UNVALIDATED_CUSTOM",
    }

