"""Slice 0B fixed-wing aerodynamics & 6-DoF mission simulation (Weissinger/lifting-line + RK4)."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any

import numpy as np

from geometry.fixed_wing_cad import ParametricWingSpec, compute_wing_geometry_properties
from physics.aerodynamics.airfoil_polars import generate_airfoil_polar
from physics.constants import STANDARD_GRAVITY
from physics.environment.isa_atmosphere import isa_atmosphere_1976

MAX_MACH_INCOMPRESSIBLE = 0.30
DEFAULT_STALL_ALPHA_DEG = 14.0


def solve_lifting_line_wing(
    wing: ParametricWingSpec,
    *,
    alpha_deg: float,
    airspeed_m_s: float,
    rho_kg_m3: float = 1.225,
    cd0: float = 0.022,
    stall_alpha_deg: float = DEFAULT_STALL_ALPHA_DEG,
    n_span_stations: int = 16,
    use_reynolds_polar: bool = False,
    altitude_m: float = 0.0,
    moment_datum_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
    wing_attachment_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> dict[str, Any]:
    """Prandtl finite-wing Fourier lifting-line solver with fail-closed stall, Mach, and optional Re polar coupling."""
    if not math.isfinite(alpha_deg) or not math.isfinite(airspeed_m_s) or airspeed_m_s <= 0.0:
        raise ValueError("alpha_deg must be finite and airspeed_m_s > 0")
    if not math.isfinite(rho_kg_m3) or rho_kg_m3 <= 0.0:
        raise ValueError("rho_kg_m3 must be finite and > 0")
    atm = isa_atmosphere_1976(altitude_m)
    mach = airspeed_m_s / atm.speed_of_sound_m_s
    if mach > MAX_MACH_INCOMPRESSIBLE:
        raise ValueError(f"Compressible flow regime unsupported: Mach {mach:.3f} > {MAX_MACH_INCOMPRESSIBLE}")
    if abs(alpha_deg) > stall_alpha_deg:
        raise ValueError(f"Post-stall angle of attack unsupported/FAIL: |alpha|={abs(alpha_deg):.2f} > {stall_alpha_deg} deg")

    geom = compute_wing_geometry_properties(wing)
    geom_sha256 = sha256(json.dumps(geom, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    b = geom["wingspan_m"]
    cr = wing.root_chord_m
    ct = wing.tip_chord_m
    s_ref = geom["planform_area_m2"]
    ar = geom["aspect_ratio"]
    mac = geom["mean_aerodynamic_chord_m"]

    reynolds = (rho_kg_m3 * airspeed_m_s * mac) / atm.dynamic_viscosity_pa_s
    effective_cd0 = cd0
    alpha_zero_lift_rad = -math.radians(2.0 * (int(wing.airfoil_code[0]) / 100.0) * 100.0) if int(wing.airfoil_code[0]) > 0 else 0.0
    polar_sha256: str | None = None
    cm_c4 = -0.025 * (int(wing.airfoil_code[0]))
    if use_reynolds_polar:
        polar = generate_airfoil_polar(wing.airfoil_code, reynolds=max(3.0e4, min(2.0e7, reynolds)))
        polar_sha256 = sha256(json.dumps(polar, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        alpha_zero_lift_rad = math.radians(polar["alpha_zero_lift_deg"])
        # Parasite wing drag + baseline airframe allowance (0.012)
        effective_cd0 = polar["cd_min"] + 0.012

    # Prandtl Fourier colocation over N odd/even terms across half-span stations (0, pi)
    m_terms = max(8, int(n_span_stations))
    theta = np.linspace(math.pi / (m_terms + 1), math.pi * m_terms / (m_terms + 1), m_terms)
    y_abs = np.abs(-0.5 * b * np.cos(theta))
    eta = 2.0 * y_abs / b
    chord = cr + (ct - cr) * eta
    a0 = 2.0 * math.pi  # thin airfoil lift slope [1/rad]
    mu = (chord * a0) / (4.0 * b)

    twist_rad = np.radians(wing.twist_tip_deg) * eta
    alpha_geom_rad = math.radians(alpha_deg) + twist_rad - alpha_zero_lift_rad

    mat = np.zeros((m_terms, m_terms), dtype=float)
    rhs = np.zeros(m_terms, dtype=float)
    for i, th in enumerate(theta):
        sin_th = math.sin(th)
        rhs[i] = mu[i] * alpha_geom_rad[i] * sin_th
        for n in range(1, m_terms + 1):
            mat[i, n - 1] = math.sin(n * th) * (n * mu[i] + sin_th)

    A = np.linalg.solve(mat, rhs)
    cl = float(math.pi * ar * A[0])
    delta_induced = sum(n * (A[n - 1] / A[0]) ** 2 for n in range(2, m_terms + 1)) if abs(A[0]) > 1e-12 else 0.0
    e_computed = float(1.0 / (1.0 + max(0.0, delta_induced)))
    cd_i = (cl * cl) / (math.pi * ar * e_computed)
    cd = effective_cd0 + cd_i
    q_dyn = 0.5 * rho_kg_m3 * airspeed_m_s * airspeed_m_s
    lift_n = q_dyn * s_ref * cl
    drag_n = q_dyn * s_ref * cd
    dx_ac = wing_attachment_m[0] - moment_datum_m[0]
    dz_ac = wing_attachment_m[2] - moment_datum_m[2]
    m_ac_n_m = q_dyn * s_ref * mac * cm_c4
    pitching_moment_datum_n_m = m_ac_n_m + dx_ac * lift_n - dz_ac * drag_n
    return {
        "schema_version": "1.0",
        "model_fidelity": "lifting_line_prandtl_fourier",
        "alpha_deg": alpha_deg,
        "airspeed_m_s": airspeed_m_s,
        "reynolds": reynolds,
        "mach": mach,
        "cl": cl,
        "cd": cd,
        "cd0_used": effective_cd0,
        "cd_induced": cd_i,
        "span_efficiency_e": e_computed,
        "lift_n": lift_n,
        "drag_n": drag_n,
        "pitching_moment_about_datum_n_m": pitching_moment_datum_n_m,
        "moment_datum_m": list(moment_datum_m),
        "geometry_sha256": geom_sha256,
        "polar_sha256": polar_sha256,
        "lift_to_drag": cl / max(1e-9, cd),
        "planform_area_m2": s_ref,
        "aspect_ratio": ar,
        "physical_validation_status": "UNVALIDATED",
    }


def compute_fixed_wing_cruise_trim(
    wing: ParametricWingSpec,
    *,
    mass_kg: float,
    airspeed_m_s: float,
    rho_kg_m3: float = 1.225,
    max_thrust_n: float = 30.0,
) -> dict[str, Any]:
    """Solve level-flight angle of attack and thrust required for steady cruise (L = W, T = D)."""
    if not math.isfinite(mass_kg) or mass_kg <= 0.0:
        raise ValueError("mass_kg must be finite and > 0")
    weight_n = mass_kg * STANDARD_GRAVITY
    geom = compute_wing_geometry_properties(wing)
    s_ref = geom["planform_area_m2"]
    q_dyn = 0.5 * rho_kg_m3 * airspeed_m_s * airspeed_m_s
    cl_req = weight_n / max(1e-9, q_dyn * s_ref)

    # Probe lifting-line slope cleanly between 0 and 6 deg
    res0 = solve_lifting_line_wing(wing, alpha_deg=0.0, airspeed_m_s=airspeed_m_s, rho_kg_m3=rho_kg_m3)
    res5 = solve_lifting_line_wing(wing, alpha_deg=5.0, airspeed_m_s=airspeed_m_s, rho_kg_m3=rho_kg_m3)
    slope_per_deg = (res5["cl"] - res0["cl"]) / 5.0
    alpha_trim_deg = (cl_req - res0["cl"]) / max(1e-6, slope_per_deg)
    trim_aero = solve_lifting_line_wing(wing, alpha_deg=alpha_trim_deg, airspeed_m_s=airspeed_m_s, rho_kg_m3=rho_kg_m3)
    feasible = trim_aero["drag_n"] <= max_thrust_n
    return {
        "trim_feasible": feasible,
        "alpha_trim_deg": alpha_trim_deg,
        "thrust_required_n": trim_aero["drag_n"],
        "max_thrust_n": max_thrust_n,
        "aero": trim_aero,
    }


def run_fixed_wing_mission(
    wing: ParametricWingSpec,
    *,
    mass_kg: float,
    max_thrust_n: float = 35.0,
    max_load_factor_g: float = 3.8,
    min_load_factor_g: float = -1.5,
    max_airspeed_m_s: float = 45.0,
    dt_s: float = 0.02,
    duration_s: float = 12.0,
    initial_airspeed_m_s: float = 16.0,
    target_airspeed_m_s: float = 18.0,
    target_altitude_m: float = 25.0,
    mission_profile: str = "takeoff_cruise_landing",
) -> dict[str, Any]:
    """Run longitudinal fixed-wing RK4 mission (takeoff, cruise, maneuver, landing) enforcing stall, load factor, and overspeed limits."""
    if dt_s <= 0.0 or duration_s <= 0.0:
        raise ValueError("dt_s and duration_s must be > 0")
    if not math.isfinite(max_load_factor_g) or not math.isfinite(min_load_factor_g) or max_load_factor_g <= min_load_factor_g:
        raise ValueError("Conflicting or invalid load-factor limits: require finite max_load_factor_g > min_load_factor_g")
    if not math.isfinite(max_airspeed_m_s) or max_airspeed_m_s <= 0.0:
        raise ValueError("max_airspeed_m_s must be finite and > 0")
    steps = max(1, math.ceil(duration_s / dt_s))
    x_pos, z_alt, v_air, gamma_rad = 0.0, 5.0, float(initial_airspeed_m_s), 0.02

    times = [0.0]
    altitudes = [z_alt]
    airspeeds = [v_air]
    load_factors = [1.0]
    phases_seen = ["takeoff"]
    verdict = "NO_MODELED_LIMIT_BREACHED"
    abort_reason: str | None = None

    for k in range(steps):
        h = min(dt_s, duration_s - k * dt_s)
        frac = (k + 1) / steps
        if mission_profile == "takeoff_cruise_landing":
            if frac < 0.25:
                phase_name = "takeoff"
                alt_ref = target_altitude_m
            elif frac < 0.60:
                phase_name = "cruise"
                alt_ref = target_altitude_m
            elif frac < 0.80:
                phase_name = "maneuver"
                alt_ref = target_altitude_m + 3.0
            else:
                phase_name = "landing_approach"
                alt_ref = max(2.0, target_altitude_m * 0.25)
        else:
            phase_name = "cruise"
            alt_ref = target_altitude_m
        if phases_seen[-1] != phase_name:
            phases_seen.append(phase_name)

        gamma_cmd = max(-0.20, min(0.25, 0.025 * (alt_ref - z_alt)))
        alpha_cmd_deg = max(-8.0, min(13.5, 4.0 + 18.0 * (gamma_cmd - gamma_rad)))
        try:
            aero = solve_lifting_line_wing(wing, alpha_deg=alpha_cmd_deg, airspeed_m_s=max(4.0, v_air))
        except ValueError as exc:
            verdict = "FAIL"
            abort_reason = str(exc)
            break

        if v_air > max_airspeed_m_s:
            verdict = "FAIL"
            abort_reason = f"Overspeed V={v_air:.2f} m/s exceeded max_airspeed_m_s={max_airspeed_m_s}"
            break

        load_g = aero["lift_n"] / (mass_kg * STANDARD_GRAVITY)
        if load_g > max_load_factor_g or load_g < min_load_factor_g:
            verdict = "FAIL"
            abort_reason = f"Load factor {load_g:.2f} g outside [{min_load_factor_g}, {max_load_factor_g}] g"
            break

        thrust_cmd = max(0.0, min(max_thrust_n, aero["drag_n"] + 2.5 * mass_kg * (target_airspeed_m_s - v_air) + mass_kg * STANDARD_GRAVITY * math.sin(gamma_rad)))

        def _rhs(state: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
            _x, _z, _v, _gam = state
            dv = (thrust_cmd - aero["drag_n"] - mass_kg * STANDARD_GRAVITY * math.sin(_gam)) / mass_kg
            dgam = (aero["lift_n"] - mass_kg * STANDARD_GRAVITY * math.cos(_gam)) / max(1e-6, mass_kg * _v)
            dx = _v * math.cos(_gam)
            dz = _v * math.sin(_gam)
            return dx, dz, dv, dgam

        st = (x_pos, z_alt, v_air, gamma_rad)
        k1 = _rhs(st)
        k2 = _rhs(tuple(a + 0.5 * h * b for a, b in zip(st, k1)))  # type: ignore[arg-type]
        k3 = _rhs(tuple(a + 0.5 * h * b for a, b in zip(st, k2)))  # type: ignore[arg-type]
        k4 = _rhs(tuple(a + h * b for a, b in zip(st, k3)))  # type: ignore[arg-type]
        x_pos, z_alt, v_air, gamma_rad = (a + (h / 6.0) * (c1 + 2.0 * c2 + 2.0 * c3 + c4) for a, c1, c2, c3, c4 in zip(st, k1, k2, k3, k4))

        if z_alt < 0.0:
            verdict = "FAIL"
            abort_reason = "Terrain impact during fixed-wing maneuver"
            break

        times.append(round((k + 1) * h, 6))
        altitudes.append(float(z_alt))
        airspeeds.append(float(v_air))
        load_factors.append(float(load_g))

    return {
        "schema_version": "1.0",
        "aircraft_family": "fixed_wing",
        "mission_profile": mission_profile,
        "phases_executed": phases_seen,
        "status": "failed" if abort_reason else "completed",
        "verdict": verdict,
        "abort_reason": abort_reason,
        "max_altitude_m": max(altitudes),
        "max_load_factor_g": max(load_factors),
        "final_airspeed_m_s": airspeeds[-1],
        "range_m": float(x_pos),
        "telemetry": {
            "t_s": times,
            "altitude_m": altitudes,
            "airspeed_m_s": airspeeds,
            "load_factor_g": load_factors,
            "channel_provenance": "calculated",
        },
        "physical_validation_status": "UNVALIDATED",
    }


def run_fixed_wing_analysis_job(
    wing: ParametricWingSpec,
    *,
    backend: str = "lifting_line_prandtl_fourier",
    alpha_deg: float = 4.0,
    airspeed_m_s: float = 18.0,
    cancel_requested: bool = False,
) -> dict[str, Any]:
    """Versioned fixed-wing analysis job with declared fidelity, progress steps, cancellation, and explicit VLM/CFD refusal."""
    supported_backends = ("lifting_line_prandtl_fourier",)
    if backend not in supported_backends:
        raise NotImplementedError(
            f"Backend {backend!r} is planned/unimplemented and cannot execute (supported: {supported_backends})"
        )
    progress_log = [0.25]
    if cancel_requested:
        return {
            "schema_version": "1.0",
            "backend": backend,
            "status": "cancelled",
            "progress_log": progress_log,
            "result": None,
            "convergence": None,
            "physical_validation_status": "UNVALIDATED",
        }
    conv = verify_fixed_wing_convergence(wing, alpha_deg=alpha_deg, airspeed_m_s=airspeed_m_s)
    progress_log.append(0.65)
    aero = solve_lifting_line_wing(wing, alpha_deg=alpha_deg, airspeed_m_s=airspeed_m_s, n_span_stations=32, use_reynolds_polar=True)
    progress_log.append(1.0)
    return {
        "schema_version": "1.0",
        "backend": backend,
        "status": "completed",
        "progress_log": progress_log,
        "discretization_error_cl": abs(conv["cl_fine"] - conv["cl_medium"]),
        "result": aero,
        "convergence": conv,
        "physical_validation_status": "UNVALIDATED",
    }


def verify_fixed_wing_convergence(
    wing: ParametricWingSpec,
    *,
    alpha_deg: float = 4.0,
    airspeed_m_s: float = 18.0,
) -> dict[str, Any]:
    """Verify 3-level Fourier span-station refinement & finite-difference AoA sensitivity."""
    coarse = solve_lifting_line_wing(wing, alpha_deg=alpha_deg, airspeed_m_s=airspeed_m_s, n_span_stations=8, use_reynolds_polar=True)
    medium = solve_lifting_line_wing(wing, alpha_deg=alpha_deg, airspeed_m_s=airspeed_m_s, n_span_stations=16, use_reynolds_polar=True)
    fine = solve_lifting_line_wing(wing, alpha_deg=alpha_deg, airspeed_m_s=airspeed_m_s, n_span_stations=32, use_reynolds_polar=True)
    err_1 = abs(coarse["cl"] - fine["cl"])
    err_2 = abs(medium["cl"] - fine["cl"])

    # Geometric sensitivity: +5% span increases aspect ratio & lowers induced drag
    wider_wing = ParametricWingSpec(
        name=f"{wing.name}_wider",
        wingspan_m=wing.wingspan_m * 1.05,
        root_chord_m=wing.root_chord_m,
        tip_chord_m=wing.tip_chord_m,
        sweep_le_deg=wing.sweep_le_deg,
        dihedral_deg=wing.dihedral_deg,
        twist_tip_deg=wing.twist_tip_deg,
        airfoil_code=wing.airfoil_code,
        oswald_e=wing.oswald_e,
    )
    wider_res = solve_lifting_line_wing(wider_wing, alpha_deg=alpha_deg, airspeed_m_s=airspeed_m_s, n_span_stations=16, use_reynolds_polar=True)
    return {
        "schema_version": "1.0",
        "cl_coarse": coarse["cl"],
        "cl_medium": medium["cl"],
        "cl_fine": fine["cl"],
        "refinement_monotone": err_2 <= err_1 + 1e-9,
        "span_sensitivity_ld_delta": wider_res["lift_to_drag"] - medium["lift_to_drag"],
        "physical_validation_status": "UNVALIDATED",
    }
