"""Slice 0C rotorcraft/VTOL software core: BEMT inflow, ground effect, autorotation, VTOL transition, and detailed solver contracts."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any

import numpy as np

from physics.constants import STANDARD_GRAVITY


def solve_helicopter_bemt_rotor(
    *,
    radius_m: float,
    root_cutout_m: float,
    chord_m: float,
    n_blades: int,
    omega_rad_s: float,
    collective_deg: float,
    climb_speed_m_s: float = 0.0,
    altitude_agl_m: float = 50.0,
    rho_kg_m3: float = 1.225,
    n_elements: int = 20,
) -> dict[str, Any]:
    """Annular Blade Element Momentum Theory (BEMT) rotor solver + Cheeseman-Bennett ground effect."""
    if radius_m <= root_cutout_m or root_cutout_m < 0.0 or chord_m <= 0.0 or n_blades < 2 or omega_rad_s <= 0.0:
        raise ValueError("Invalid helicopter rotor geometry or angular rate")
    if climb_speed_m_s < -8.0:
        raise ValueError("Deep descending vortex-ring state outside supported BEMT momentum annulus")
    if altitude_agl_m <= 0.35 * radius_m:
        raise ValueError("Ground clearance z/R <= 0.35 outside Cheeseman-Bennett ground effect domain")

    a_slope = 5.73  # 2*pi lift curve slope corrected
    cd0 = 0.011
    theta0 = math.radians(collective_deg)
    dr = (radius_m - root_cutout_m) / n_elements
    r_mid = np.linspace(root_cutout_m + 0.5 * dr, radius_m - 0.5 * dr, n_elements)
    sigma_local = (n_blades * chord_m) / (2.0 * math.pi * r_mid)

    total_thrust_ige = 0.0
    total_torque = 0.0
    mean_vi = 0.0
    # Cheeseman-Bennett in-ground-effect ratio T_ige / T_oge at constant power
    ige_factor = 1.0 / max(0.2, 1.0 - (radius_m / (4.0 * altitude_agl_m)) ** 2)

    for r_i, sig_i in zip(r_mid, sigma_local):
        ut = omega_rad_s * float(r_i)
        # Local momentum-BEMT inflow velocity vi
        # Quadratic solve for vi in climb/hover annulus
        b_coef = climb_speed_m_s + 0.25 * a_slope * sig_i * ut
        c_coef = 0.25 * a_slope * sig_i * ut * (climb_speed_m_s - theta0 * ut)
        disc = max(0.0, b_coef * b_coef - 4.0 * c_coef)
        vi = max(0.1, 0.5 * (-b_coef + math.sqrt(disc)))
        up = climb_speed_m_s + vi
        phi = math.atan2(up, ut)
        alpha = theta0 - phi
        if abs(math.degrees(alpha)) > 15.0:
            raise ValueError(f"Rotor blade element stall detected at r={r_i:.3f} m (alpha={math.degrees(alpha):.2f} deg)")
        cl = a_slope * alpha
        cd = cd0 + 0.02 * cl * cl
        q_loc = 0.5 * rho_kg_m3 * (ut * ut + up * up) * chord_m * n_blades * dr
        dL = q_loc * cl
        dD = q_loc * cd
        dT = dL * math.cos(phi) - dD * math.sin(phi)
        dQ = float(r_i) * (dL * math.sin(phi) + dD * math.cos(phi))
        total_thrust_ige += dT * ige_factor
        total_torque += dQ
        mean_vi += vi / n_elements

    power_w = total_torque * omega_rad_s
    return {
        "schema_version": "1.0",
        "model": "annular_bemt_with_ige",
        "thrust_n": float(total_thrust_ige),
        "torque_nm": float(total_torque),
        "shaft_power_w": float(power_w),
        "mean_induced_velocity_m_s": float(mean_vi),
        "ige_factor": float(ige_factor),
        "tip_mach": (omega_rad_s * radius_m) / 340.3,
        "physical_validation_status": "UNVALIDATED",
    }


def compute_tail_rotor_balance(
    *,
    main_torque_nm: float,
    tail_arm_m: float,
    max_tail_thrust_n: float,
) -> dict[str, Any]:
    """Compute required anti-torque tail rotor thrust and yaw authority margin."""
    if tail_arm_m <= 0.0:
        raise ValueError("tail_arm_m must be > 0")
    req_thrust_n = abs(main_torque_nm) / tail_arm_m
    sufficient = req_thrust_n <= max_tail_thrust_n
    return {
        "required_tail_thrust_n": float(req_thrust_n),
        "max_tail_thrust_n": float(max_tail_thrust_n),
        "yaw_authority_margin": float(max_tail_thrust_n / max(1e-9, req_thrust_n)),
        "verdict": "NO_MODELED_LIMIT_BREACHED" if sufficient else "FAIL",
    }


def run_vtol_transition_corridor(
    *,
    mass_kg: float,
    wing_area_m2: float,
    max_rotor_thrust_n: float,
    max_cruise_thrust_n: float,
    stall_speed_m_s: float = 12.0,
    ambient_temp_c: float = 25.0,
    motor_max_temp_c: float = 95.0,
    duration_s: float = 8.0,
    dt_s: float = 0.05,
) -> dict[str, Any]:
    """Simulate coupled hover->cruise VTOL transition with thermal derating and stall corridor check."""
    if mass_kg <= 0.0 or wing_area_m2 <= 0.0 or duration_s <= 0.0 or dt_s <= 0.0:
        raise ValueError("VTOL parameters must be positive and finite")
    steps = max(2, math.ceil(duration_s / dt_s))
    weight_n = mass_kg * STANDARD_GRAVITY
    motor_temp_c = ambient_temp_c
    verdict = "NO_MODELED_LIMIT_BREACHED"
    abort_reason: str | None = None
    trajectory = []

    for idx in range(steps + 1):
        frac = idx / steps
        tilt_deg = 90.0 * (1.0 - frac)  # 90=hover, 0=forward cruise
        v_air = 22.0 * frac
        q_dyn = 0.5 * 1.225 * v_air * v_air
        wing_lift_n = min(weight_n, q_dyn * wing_area_m2 * 1.15)
        lift_deficit = max(0.0, weight_n - wing_lift_n)
        sin_t = max(0.05, math.sin(math.radians(tilt_deg))) if tilt_deg > 1.0 else 0.0

        rotor_lift_req = lift_deficit / sin_t if tilt_deg > 5.0 else 0.0
        if tilt_deg <= 5.0 and v_air < stall_speed_m_s:
            verdict = "FAIL"
            abort_reason = f"VTOL transitioned below wing stall speed ({v_air:.2f} < {stall_speed_m_s:.2f} m/s)"
            break
        if rotor_lift_req > max_rotor_thrust_n:
            verdict = "FAIL"
            abort_reason = f"Required transition rotor thrust {rotor_lift_req:.1f} N > limit {max_rotor_thrust_n:.1f} N"
            break

        # Coupled transient thermal RC update
        power_frac = max(0.15, (rotor_lift_req / max(1.0, max_rotor_thrust_n)) ** 1.5)
        heat_w = 180.0 * power_frac + 40.0 * (1.0 - sin_t)
        dtemp_dt = (heat_w - 3.5 * (motor_temp_c - ambient_temp_c)) / 240.0
        motor_temp_c += dtemp_dt * dt_s
        if motor_temp_c > motor_max_temp_c:
            verdict = "FAIL"
            abort_reason = f"Motor thermal limit exceeded ({motor_temp_c:.1f} C > {motor_max_temp_c:.1f} C)"
            break

        trajectory.append(
            {
                "t_s": round(idx * dt_s, 4),
                "tilt_deg": round(tilt_deg, 2),
                "airspeed_m_s": round(v_air, 3),
                "wing_lift_n": round(wing_lift_n, 2),
                "rotor_thrust_n": round(rotor_lift_req, 2),
                "motor_temp_c": round(motor_temp_c, 2),
            }
        )

    return {
        "schema_version": "1.0",
        "aircraft_family": "vtol",
        "status": "failed" if abort_reason else "completed",
        "verdict": verdict,
        "abort_reason": abort_reason,
        "peak_motor_temp_c": max((r["motor_temp_c"] for r in trajectory), default=ambient_temp_c),
        "samples": trajectory,
        "physical_validation_status": "UNVALIDATED",
    }


def compute_beam_modal_frequencies_hz(
    *,
    length_m: float,
    youngs_modulus_pa: float,
    area_moment_m4: float,
    linear_density_kg_m: float,
) -> dict[str, Any]:
    """Cantilever Euler-Bernoulli 1st and 2nd structural bending natural frequencies."""
    if min(length_m, youngs_modulus_pa, area_moment_m4, linear_density_kg_m) <= 0.0:
        raise ValueError("All structural beam modal parameters must be positive")
    coeff = math.sqrt((youngs_modulus_pa * area_moment_m4) / linear_density_kg_m) / (2.0 * math.pi * length_m * length_m)
    return {
        "mode_1_hz": 3.5160 * coeff,
        "mode_2_hz": 22.0345 * coeff,
        "model": "euler_bernoulli_cantilever",
    }


def build_detailed_solver_contract(
    *,
    solver_kind: str,
    mesh_cell_count: int,
    estimated_ram_mb: int,
    available_ram_mb: int,
    execution_target: str = "local",
) -> dict[str, Any]:
    """Prepare a fail-closed local or remote CFD/FEA/XFLR5 detailed-worker request contract."""
    supported = {"openfoam_rans", "calculix_fea", "xflr5_polar"}
    if solver_kind not in supported:
        raise ValueError(f"Unsupported detailed solver {solver_kind!r}; choose from {sorted(supported)}")
    if execution_target not in ("local", "remote"):
        raise ValueError("execution_target must be 'local' or 'remote'")
    admitted = estimated_ram_mb <= int(0.70 * available_ram_mb)
    payload = {
        "schema_version": "1.0",
        "solver_kind": solver_kind,
        "execution_target": execution_target,
        "mesh_cell_count": int(mesh_cell_count),
        "estimated_ram_mb": int(estimated_ram_mb),
        "available_ram_mb": int(available_ram_mb),
        "admission_status": "admitted" if admitted else "refused_offer_remote_or_smaller_mesh",
        "physical_validation_status": "UNVALIDATED",
    }
    payload["contract_sha256"] = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return payload
