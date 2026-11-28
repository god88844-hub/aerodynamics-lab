"""Coupled Cargo Slung-Load, VTOL Tailsitter, Flying-Wing, Micro-Ducted, Fasteners, Electrophysics Bridge & Failure Atlas."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from aeroforge_schemas.component import BatterySpec

ROOT = Path(__file__).resolve().parents[3]
GRAVITY = 9.80665


def evaluate_cargo_slung_load(
    *,
    carrier_mass_kg: float,
    cargo_mass_kg: float,
    cable_length_m: float,
    box_area_m2: float = 0.09,
    box_cd: float = 1.35,
    cg_offset_m: float = 0.02,
    airspeed_m_s: float = 12.0,
    rho_kg_m3: float = 1.225,
    max_thrust_n: float = 92.0,
    payload_released: bool = False,
) -> dict[str, Any]:
    """Model under-slung cargo pendulum natural frequency, bluff-body blowback drag, and CG tether torque."""
    if carrier_mass_kg <= 0.0 or cable_length_m <= 0.05 or max_thrust_n <= 0.0:
        raise ValueError("carrier_mass_kg, cable_length_m (>0.05), and max_thrust_n must be positive")
    active_cargo = 0.0 if payload_released else max(0.0, cargo_mass_kg)
    effective_mass = carrier_mass_kg + active_cargo
    omega_p = math.sqrt(GRAVITY / cable_length_m)
    pend_hz = omega_p / (2.0 * math.pi)
    q = 0.5 * rho_kg_m3 * airspeed_m_s * airspeed_m_s
    blowback_n = 0.0 if payload_released else (q * max(0.0, box_area_m2) * max(0.1, box_cd))
    w_cargo = active_cargo * GRAVITY
    trail_deg = math.degrees(math.atan2(blowback_n, w_cargo)) if w_cargo > 1e-3 else 0.0
    tension_n = math.hypot(w_cargo, blowback_n)
    cg_torque_nm = tension_n * abs(cg_offset_m)
    req_thrust = math.hypot(effective_mass * GRAVITY, blowback_n)
    residual_tw = max_thrust_n / max(0.1, req_thrust)
    stable = residual_tw >= 1.15 and trail_deg <= 38.0 and cg_torque_nm <= 4.5
    return {
        "effective_mass_kg": effective_mass,
        "pendulum_freq_hz": pend_hz,
        "blowback_drag_n": blowback_n,
        "trail_angle_deg": trail_deg,
        "cg_offset_torque_nm": cg_torque_nm,
        "residual_tw": residual_tw,
        "verdict": "NO_MODELED_LIMIT_BREACHED" if stable else "FAIL",
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }


def evaluate_tailsitter_transition(
    *,
    mass_kg: float,
    wing_area_m2: float,
    wingspan_m: float,
    max_thrust_n: float,
    airspeed_m_s: float,
    transition_pitch_deg: float,
    elevon_deflect_deg: float = 12.0,
    duct_area_ratio: float = 1.0,
    rho_kg_m3: float = 1.225,
) -> dict[str, Any]:
    """Nicholas Rehm dRehmFlight-style VTOL tailsitter transition propwash slipstream & elevon authority."""
    if mass_kg <= 0.0 or wing_area_m2 <= 0.0 or max_thrust_n <= 0.0:
        raise ValueError("mass_kg, wing_area_m2, and max_thrust_n must be positive")
    a_disk = max(0.015, 0.22 * wing_area_m2)
    sigma_d = min(1.65, max(1.0, duct_area_ratio))
    duct_gain = math.sqrt(2.0 * sigma_d * 0.68) if sigma_d > 1.01 else 1.0
    t_eff = max_thrust_n * duct_gain
    v_slip = math.sqrt(airspeed_m_s * airspeed_m_s + (2.0 * t_eff) / (rho_kg_m3 * a_disk))
    q_slip = 0.5 * rho_kg_m3 * v_slip * v_slip
    c_bar = wing_area_m2 / max(0.25, wingspan_m)
    ctrl_moment = q_slip * (0.28 * wing_area_m2) * (0.5 * c_bar) * (1.8 * math.radians(abs(elevon_deflect_deg)))
    theta = math.radians(min(90.0, max(0.0, transition_pitch_deg)))
    q_air = 0.5 * rho_kg_m3 * airspeed_m_s * airspeed_m_s
    aero_lift = q_air * wing_area_m2 * (1.25 * math.sin(2.0 * theta) * 0.45 + 0.55 * math.cos(theta))
    eff_lift = t_eff * math.sin(theta) + aero_lift
    authority_ok = eff_lift >= mass_kg * GRAVITY * 1.05 and ctrl_moment >= 0.12
    return {
        "duct_thrust_gain": duct_gain,
        "propwash_slip_m_s": v_slip,
        "control_moment_nm": ctrl_moment,
        "effective_lift_n": eff_lift,
        "verdict": "NO_MODELED_LIMIT_BREACHED" if authority_ok else "FAIL",
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }


def evaluate_flying_wing_reflex(
    *,
    mass_kg: float,
    wing_area_m2: float,
    sweep_deg: float,
    airspeed_m_s: float,
    rho_kg_m3: float = 1.225,
) -> dict[str, Any]:
    """Swept flying-wing / BWB static margin & reflex pitch stability check."""
    static_margin_pct = -4.0 + 0.55 * abs(sweep_deg)
    q = 0.5 * rho_kg_m3 * airspeed_m_s * airspeed_m_s
    lift_n = q * wing_area_m2 * 0.62
    stable = static_margin_pct >= 2.5 and lift_n >= mass_kg * GRAVITY * 0.95
    return {
        "static_margin_pct": static_margin_pct,
        "lift_n": lift_n,
        "verdict": "NO_MODELED_LIMIT_BREACHED" if stable else "FAIL",
        "physical_validation_status": "UNVALIDATED_CUSTOM",
    }


def verify_iso_fastener_and_awg_harness(
    *,
    screw_id: str,
    fasteners_per_joint: int,
    joint_shear_load_n: float,
    wire_awg: int,
    continuous_current_a: float,
    harness_length_m: float = 0.6,
) -> dict[str, Any]:
    """Validate joint against ISO 4762 screw shear table and AWG 10-22 ampacity/voltage drop table."""
    screw_doc = json.loads((ROOT / "data" / "components" / "fasteners" / "iso_4762_metric_screws.json").read_text(encoding="utf-8"))
    wire_doc = json.loads((ROOT / "data" / "components" / "standards" / "silicone_wire_awg.json").read_text(encoding="utf-8"))
    screw = next(s for s in screw_doc["screws"] if s["id"] == screw_id)
    wire = next(w for w in wire_doc["silicone_copper_awg"] if w["awg"] == int(wire_awg))
    bolt_fos = (screw["shear_capacity_n"] * max(1, fasteners_per_joint)) / max(0.5, abs(joint_shear_load_n))
    v_drop = abs(continuous_current_a) * wire["resistance_ohm_per_m"] * harness_length_m * 2.0
    bolt_ok = bolt_fos >= 1.50
    wire_ok = abs(continuous_current_a) <= wire["rec_ampacity_a"] * 1.10 and v_drop <= 0.80
    return {
        "screw_id": screw_id,
        "bolt_shear_fos": bolt_fos,
        "wire_drop_v": v_drop,
        "wire_ampacity_a": wire["rec_ampacity_a"],
        "bolt_ok": bolt_ok,
        "wire_ok": wire_ok,
        "verdict": "NO_MODELED_LIMIT_BREACHED" if (bolt_ok and wire_ok) else "FAIL",
    }


def import_electrophysics_powerpack(payload: dict[str, Any]) -> BatterySpec:
    """Validate Electrophysics Lab PowerPack bridge JSON into Aerodynamics Lab BatterySpec."""
    contract = json.loads((ROOT / "data" / "research" / "electrophysics_powerpack_contract.json").read_text(encoding="utf-8"))
    missing = [k for k in contract["required_fields"] if k not in payload]
    if missing:
        raise ValueError(f"Electrophysics PowerPack missing required fields: {missing}")
    return BatterySpec(
        id=str(payload["component_id"]),
        name=f"Electrophysics Custom Pack ({payload['component_id']})",
        chemistry="LiPo",
        cells_series=int(payload["cells_series"]),
        capacity_ah=float(payload["capacity_ah"]),
        internal_resistance_ohm=float(payload["internal_resistance_ohm"]),
        mass_kg=float(payload["mass_kg"]),
        cutoff_cell_voltage_v=float(payload["cutoff_cell_voltage_v"]),
        ocv_curve=payload["ocv_curve"],
        operating_limits={"max_continuous_current_a": float(payload["max_continuous_current_a"]), "max_temperature_c": float(payload["max_temperature_c"])},
        source={"source": f"Electrophysics Lab bridge ({payload['validation_origin']})", "estimated": True, "status": "UNVERIFIED_ESTIMATE"},
    )


def evaluate_failure_atlas_cases() -> dict[str, Any]:
    """Load Failure Atlas and cross-verify physical failure detectors across core benchmarks."""
    atlas = json.loads((ROOT / "data" / "failure_examples" / "failure_atlas.json").read_text(encoding="utf-8"))
    cases = atlas["failure_cases"]
    cargo_fail = evaluate_cargo_slung_load(
        carrier_mass_kg=4.2, cargo_mass_kg=7.5, cable_length_m=1.2, box_area_m2=0.14, airspeed_m_s=18.0, max_thrust_n=85.0
    )
    tailsitter_fail = evaluate_tailsitter_transition(
        mass_kg=1.8, wing_area_m2=0.28, wingspan_m=1.1, max_thrust_n=12.0, airspeed_m_s=3.0, transition_pitch_deg=45.0
    )
    wire_fail = verify_iso_fastener_and_awg_harness(
        screw_id="m2x8_12_9", fasteners_per_joint=4, joint_shear_load_n=120.0, wire_awg=22, continuous_current_a=40.0
    )
    return {
        "schema_version": "1.0",
        "policy_role": "DEVELOPMENT",
        "catalog_case_count": len(cases),
        "case_ids": [c["id"] for c in cases],
        "verified_fail_closed_checks": {
            "cargo_blowback_fail": cargo_fail["verdict"] == "FAIL",
            "tailsitter_stall_fail": tailsitter_fail["verdict"] == "FAIL",
            "thin_wire_overload_fail": wire_fail["verdict"] == "FAIL",
        },
    }
