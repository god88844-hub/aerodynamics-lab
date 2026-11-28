"""Seaplane / Floatplane Hydrodynamics: Savitsky (1964) Planing, ITTC-57 Friction, & NACA Hump Drag.

Covers buoyancy reserve, pre-hump wave resistance, planing lift/drag equilibrium, and water takeoff gate.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_DIR = ROOT / "data" / "benchmarks" / "public"
G = 9.80665


def evaluate_savitsky_planing_point(
    *,
    speed_m_s: float,
    beam_m: float,
    deadrise_deg: float,
    trim_deg: float,
    lambda_wetted_ratio: float,
    water_rho_kg_m3: float = 1025.0,
    kinematic_viscosity_m2_s: float = 1.19e-6,
) -> dict[str, float]:
    """Savitsky (1964) prismatic hull planing lift, induced pressure drag, and ITTC-57 friction drag."""
    if speed_m_s <= 0.1 or beam_m <= 0.02 or lambda_wetted_ratio <= 0.05 or trim_deg <= 0.1:
        raise ValueError("Savitsky planing requires positive speed, beam, wetted ratio, and trim angle")
    cv = speed_m_s / math.sqrt(G * beam_m)
    cl0 = (trim_deg ** 1.1) * (0.012 * math.sqrt(lambda_wetted_ratio) + (0.0055 * (lambda_wetted_ratio ** 2.5)) / (cv * cv))
    cl_beta = max(0.0, cl0 - 0.0065 * deadrise_deg * (cl0 ** 0.60))
    lift_n = 0.5 * water_rho_kg_m3 * (speed_m_s ** 2) * (beam_m ** 2) * cl_beta

    l_m = lambda_wetted_ratio * beam_m
    re_w = max(1e4, speed_m_s * l_m / kinematic_viscosity_m2_s)
    cf = 0.075 / ((math.log10(re_w) - 2.0) ** 2)
    wetted_area_m2 = (l_m * beam_m) / max(0.3, math.cos(math.radians(deadrise_deg)))
    drag_friction_n = 0.5 * water_rho_kg_m3 * (speed_m_s ** 2) * wetted_area_m2 * cf
    drag_pressure_n = lift_n * math.tan(math.radians(trim_deg))
    drag_total_n = drag_pressure_n + drag_friction_n
    return {
        "cv": cv,
        "cl0": cl0,
        "cl_beta": cl_beta,
        "lift_n": lift_n,
        "drag_friction_n": drag_friction_n,
        "drag_pressure_n": drag_pressure_n,
        "drag_total_n": drag_total_n,
    }


def evaluate_seaplane_water_takeoff(
    *,
    mass_kg: float,
    installed_thrust_n: float,
    float_count: int = 2,
    float_beam_m: float = 0.16,
    float_length_m: float = 1.15,
    float_volume_each_m3: float = 0.012,
    deadrise_deg: float = 18.0,
    wing_area_m2: float = 0.42,
    wing_cl_takeoff: float = 1.15,
    water_chop_m: float = 0.05,
    water_rho_kg_m3: float = 1000.0,
) -> dict[str, Any]:
    """Evaluate Archimedes buoyancy, NACA displacement-to-planing hump resistance, and takeoff clearance."""
    weight_n = mass_kg * G
    max_buoyancy_n = float_count * float_volume_each_m3 * water_rho_kg_m3 * G
    reserve_buoyancy_ratio = max_buoyancy_n / max(0.1, weight_n)

    # Aero liftoff speed at CL_takeoff
    v_liftoff = math.sqrt((2.0 * weight_n) / (1.225 * max(0.05, wing_area_m2) * max(0.3, wing_cl_takeoff)))
    # NACA hump speed Fn_L ~ 0.45
    v_hump = 0.45 * math.sqrt(G * max(0.2, float_length_m))
    # Peak hump wave+spray+trim resistance near Fn_L = 0.45; rough chop adds spray drag
    chop_penalty = 1.0 + 1.8 * max(0.0, water_chop_m / max(0.05, float_beam_m))
    aero_lift_at_hump = 0.5 * 1.225 * (v_hump ** 2) * wing_area_m2 * (0.55 * wing_cl_takeoff)
    water_load_at_hump = max(0.0, weight_n - aero_lift_at_hump)
    # Typical stepped float hump resistance-to-load ~ 0.22..0.28 for good deadrise step
    r_hump_n = water_load_at_hump * (0.24 + 0.002 * deadrise_deg) * chop_penalty

    # Approximate average net accelerating force across [0, v_liftoff]
    avg_drag_n = 0.55 * r_hump_n + 0.25 * (0.5 * 1.225 * v_liftoff * v_liftoff * wing_area_m2 * 0.06)
    buoyancy_ok = reserve_buoyancy_ratio >= 1.80
    hump_ok = installed_thrust_n > 1.15 * r_hump_n
    takeoff_distance_m = (0.5 * mass_kg * v_liftoff * v_liftoff) / max(0.2, installed_thrust_n - avg_drag_n) if hump_ok else None

    verdict = "NO_MODELED_LIMIT_BREACHED" if (buoyancy_ok and hump_ok) else "FAIL"
    return {
        "reserve_buoyancy_ratio": reserve_buoyancy_ratio,
        "v_hump_m_s": v_hump,
        "v_liftoff_m_s": v_liftoff,
        "hump_resistance_n": r_hump_n,
        "thrust_to_hump_ratio": installed_thrust_n / max(0.1, r_hump_n),
        "takeoff_run_m": takeoff_distance_m,
        "buoyancy_ok": buoyancy_ok,
        "hump_ok": hump_ok,
        "verdict": verdict,
        "physical_validation_status": "DEVELOPMENT",
    }


def verify_savitsky_benchmark() -> dict[str, Any]:
    """Compare Savitsky calculation against exact 1964 SNAME worked example."""
    bm = json.loads((PUBLIC_DIR / "savitsky_1964_planing" / "savitsky_worked_benchmark.json").read_text(encoding="utf-8"))
    w = bm["worked_case"]
    res = evaluate_savitsky_planing_point(
        speed_m_s=w["speed_m_s"],
        beam_m=w["beam_m"],
        deadrise_deg=w["deadrise_deg"],
        trim_deg=w["trim_deg"],
        lambda_wetted_ratio=w["lambda_wetted_ratio"],
        water_rho_kg_m3=w["water_rho_kg_m3"],
    )
    return {
        "cv_err": abs(res["cv"] - w["expected_cv"]),
        "cl0_err": abs(res["cl0"] - w["expected_cl0"]),
        "cl_beta_err": abs(res["cl_beta"] - w["expected_cl_beta"]),
        "lift_rel_err": abs(res["lift_n"] - w["expected_lift_n"]) / w["expected_lift_n"],
    }
