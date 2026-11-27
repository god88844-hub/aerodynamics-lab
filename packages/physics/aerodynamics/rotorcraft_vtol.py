"""Slice 0C rotorcraft/VTOL software core: BEMT inflow, ground effect, autorotation, VTOL transition, and detailed solver contracts."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any

import numpy as np

from physics.aerodynamics.pitt_peters_inflow import run_pitt_peters_step_response
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


def run_helicopter_autorotation_mission(
    *,
    mass_kg: float = 3.2,
    rotor_radius_m: float = 0.72,
    rotor_inertia_kg_m2: float = 0.14,
    initial_altitude_m: float = 32.0,
    initial_rpm: float = 1650.0,
    min_safe_rpm: float = 950.0,
    flare_altitude_m: float = 7.0,
    max_touchdown_sink_m_s: float = 2.6,
    dt_s: float = 0.05,
    duration_s: float = 12.0,
) -> dict[str, Any]:
    """Simulate unpowered helicopter autorotation descent + collective flare with RPM stall and sink limits."""
    if mass_kg <= 0.0 or rotor_radius_m <= 0.0 or rotor_inertia_kg_m2 <= 0.0 or dt_s <= 0.0:
        raise ValueError("Autorotation helicopter parameters must be positive")
    z = float(initial_altitude_m)
    vz = -5.2
    omega = initial_rpm * 2.0 * math.pi / 60.0
    disk_area = math.pi * rotor_radius_m * rotor_radius_m
    steps = max(2, math.ceil(duration_s / dt_s))

    times, xs, ys, zs, qs, rpms, sinks = [], [], [], [], [], [], []
    verdict = "NO_MODELED_LIMIT_BREACHED"
    abort_reason: str | None = None
    touchdown_sink = 0.0

    for idx in range(steps + 1):
        t = round(idx * dt_s, 4)
        rpm = omega * 60.0 / (2.0 * math.pi)
        times.append(t)
        xs.append(round(4.5 * t, 4))  # gentle forward autorotative glide
        ys.append(0.0)
        zs.append(round(max(0.0, z), 4))
        qs.append([1.0, 0.0, -0.04, 0.0] if z > flare_altitude_m else [1.0, 0.0, 0.08, 0.0])
        rpms.append(round(rpm, 2))
        sinks.append(round(-vz, 3))

        if rpm < min_safe_rpm:
            verdict = "FAIL"
            abort_reason = f"Rotor RPM decayed below safe stall bound ({rpm:.1f} < {min_safe_rpm:.1f} RPM)"
            break
        if z <= 0.0 and idx > 0:
            touchdown_sink = abs(vz)
            if touchdown_sink > max_touchdown_sink_m_s:
                verdict = "FAIL"
                abort_reason = f"Hard autorotation landing sink={touchdown_sink:.2f} > {max_touchdown_sink_m_s:.2f} m/s"
            break

        # Collective increases in flare below flare_altitude_m; autorotative windmill torque recovers/drains omega
        in_flare = z <= flare_altitude_m
        v_tip = omega * rotor_radius_m
        solidity = 0.032
        cd0_eff = 0.020 if in_flare else 0.010
        thrust_coeff = 0.0038 if in_flare else 0.00175
        thrust_n = min(1.85 * mass_kg * STANDARD_GRAVITY, 0.5 * 1.225 * disk_area * (v_tip ** 2) * thrust_coeff * (1.0 + 0.05 * max(0.0, -vz)))
        az = (thrust_n - mass_kg * STANDARD_GRAVITY) / mass_kg
        # Physical momentum energy extraction vs profile drag torque
        windmill_power = max(0.0, -vz) * thrust_n * 0.88
        profile_power = 0.125 * 1.225 * solidity * cd0_eff * disk_area * (v_tip ** 3)
        domega = (windmill_power - profile_power) / (rotor_inertia_kg_m2 * max(1.0, omega))
        omega = max(1.0, omega + domega * dt_s)
        vz = vz + az * dt_s
        z = z + vz * dt_s

    return {
        "schema_version": "1.0",
        "aircraft_family": "helicopter",
        "status": "failed" if abort_reason else "completed",
        "verdict": verdict,
        "abort_reason": abort_reason,
        "touchdown_sink_m_s": round(touchdown_sink, 3),
        "min_observed_rpm": min(rpms),
        "telemetry": {
            "t": times,
            "x": xs,
            "y": ys,
            "z": zs,
            "q_wxyz": qs,
            "rotor_rpm": rpms,
            "sink_rate_m_s": sinks,
            "channel_provenance": "calculated",
        },
        "physical_validation_status": "UNVALIDATED",
    }


def run_coupled_aero_thermo_structural(
    *,
    vtol_architecture: str = "tilt_rotor",
    mass_kg: float = 3.2,
    wing_area_m2: float = 0.45,
    max_rotor_thrust_n: float = 48.0,
    max_cruise_thrust_n: float = 28.0,
    boom_length_m: float = 0.55,
    youngs_modulus_pa: float = 6.5e10,
    area_moment_m4: float = 1.6e-9,
    linear_density_kg_m: float = 0.35,
    max_tip_deflection_mm: float = 22.0,
) -> dict[str, Any]:
    """Coupled VTOL transition aerodynamics + Euler-Bernoulli boom bending + transient motor thermal loop."""
    if vtol_architecture not in ("tilt_rotor", "lift_plus_cruise"):
        raise ValueError("vtol_architecture must be 'tilt_rotor' or 'lift_plus_cruise'")
    trans = run_vtol_transition_corridor(
        mass_kg=mass_kg,
        wing_area_m2=wing_area_m2,
        max_rotor_thrust_n=max_rotor_thrust_n,
        max_cruise_thrust_n=max_cruise_thrust_n,
    )
    modes = compute_beam_modal_frequencies_hz(
        length_m=boom_length_m,
        youngs_modulus_pa=youngs_modulus_pa,
        area_moment_m4=area_moment_m4,
        linear_density_kg_m=linear_density_kg_m,
    )
    peak_rotor_n = max((s["rotor_thrust_n"] for s in trans["samples"]), default=0.0)
    # Tip load per symmetric boom/rotor
    tip_load_n = 0.5 * peak_rotor_n
    tip_deflection_mm = 1000.0 * (tip_load_n * (boom_length_m ** 3)) / (3.0 * youngs_modulus_pa * area_moment_m4)
    verdict = trans["verdict"]
    abort = trans["abort_reason"]
    if tip_deflection_mm > max_tip_deflection_mm:
        verdict = "FAIL"
        abort = f"Boom tip deflection {tip_deflection_mm:.2f} mm > limit {max_tip_deflection_mm:.2f} mm"
    return {
        "schema_version": "1.0",
        "aircraft_family": "vtol",
        "vtol_architecture": vtol_architecture,
        "verdict": verdict,
        "abort_reason": abort,
        "peak_motor_temp_c": trans["peak_motor_temp_c"],
        "peak_rotor_thrust_n": peak_rotor_n,
        "boom_tip_deflection_mm": round(tip_deflection_mm, 3),
        "mode_1_hz": round(modes["mode_1_hz"], 2),
        "samples": trans["samples"],
        "physical_validation_status": "UNVALIDATED",
    }


def verify_rotorcraft_convergence_and_inflow() -> dict[str, Any]:
    """Verify 3-grid annular BEMT refinement and Pitt-Peters dynamic inflow coupling."""
    r10 = solve_helicopter_bemt_rotor(radius_m=0.72, root_cutout_m=0.10, chord_m=0.055, n_blades=2, omega_rad_s=170.0, collective_deg=8.0, n_elements=10)
    r20 = solve_helicopter_bemt_rotor(radius_m=0.72, root_cutout_m=0.10, chord_m=0.055, n_blades=2, omega_rad_s=170.0, collective_deg=8.0, n_elements=20)
    r40 = solve_helicopter_bemt_rotor(radius_m=0.72, root_cutout_m=0.10, chord_m=0.055, n_blades=2, omega_rad_s=170.0, collective_deg=8.0, n_elements=40)
    inflow = run_pitt_peters_step_response(ct_step=0.008, omega_rad_s=170.0, duration_s=0.15)
    e1 = abs(r10["thrust_n"] - r40["thrust_n"])
    e2 = abs(r20["thrust_n"] - r40["thrust_n"])
    return {
        "schema_version": "1.0",
        "bemt_thrust_10": r10["thrust_n"],
        "bemt_thrust_20": r20["thrust_n"],
        "bemt_thrust_40": r40["thrust_n"],
        "refinement_monotone": e2 <= e1 + 1e-6,
        "pitt_peters_final_lambda0": inflow["final_inflow"][0],
        "physical_validation_status": "UNVALIDATED",
    }
